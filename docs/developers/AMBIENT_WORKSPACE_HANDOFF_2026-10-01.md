# Ambient Workspace：云端实现与本机交接（2026-10-01）

本契约承接[原提案](../architecture/WORKSPACE_GATEWAY_PROPOSAL.md)和[审查结论](../architecture/WORKSPACE_GATEWAY_REVIEW_2026-10-01.md)。原交接分支已合入 `main` 并删除，Ambient 已完成下述适配及独立联调，见[验收记录](../verification/AMBIENT_WORKSPACE_ACCEPTANCE_2026-10-01.md)。Web 与云端支持默认独立注册域和显式临时子域部署；实际服务器状态见[发布记录](../releases/AMBIENT_WORKSPACE_DEPLOYMENT_2026-10-01.md)。以下协议与验收要求继续有效，隔离联调不能代替公网验收。

Agent、App、Provider 密钥、文件与 Run 由用户电脑上的 Ambient 持有和执行。云门户持有账户，Gateway 持有授权及审计元数据并中转有界 HTTP/WS。恢复连接后读取原 Run 的真实状态，网络错误不能自动变成再次执行请求。

## 获取源码

[部署仓库 main](https://github.com/BillShiyaoZhang/agent-collaboration-deploy/tree/main)固定 Web 提交 `4abb3f34331f2d26be411cf0af60bd3827b26314`（[Web 固定代码](https://github.com/BillShiyaoZhang/agent-collaboration-web/tree/4abb3f34331f2d26be411cf0af60bd3827b26314)）。Web 是独立仓库，不要通过 `submodule update --remote` 选择另一版本。

```sh
git clone --branch main --recurse-submodules \
  https://github.com/BillShiyaoZhang/agent-collaboration-deploy.git
cd agent-collaboration-deploy
git submodule update --init --recursive
```

## 新用户流程

1. 用户登录云门户，在 `/dashboard/workspaces` 或无 code 的 `/connect-workspace` 主动生成本机接入码。码有效期 300 秒，绑定登录账户，只能消费一次。
2. 用户在自己的 Ambient 远程设置中填写公开 Gateway 地址、门户地址和接入码，选择名称、权限与授权期限。Ambient 调用配对接口，保存返回的设备凭据。
3. Ambient 显示原来的配对码或门户领取链接；用户在同一账户领取。其他账户不能领取，也不能消耗该码。
4. Ambient 显示领取账户、权限与到期时间；用户在本机明确确认，提交匹配的 `account_id` 与 `grant_id`。接入码和云端领取均不代替本机确认。
5. 批准的 Connector 建立 Tunnel。用户从门户生成一次性打开链接，在节点域名进入工作区。撤销或到期关闭已有远程连接。

pending 节点已含可信账户 ID，但 `account_label` 为空；不能仅据账户 ID 显示已领取/已授权，必须依据 `status` 及本机确认结果。

## 必须适配的契约

Web 新增 `POST /api/workspace-nodes/enroll`，要求登录、同源 Origin 和空对象 `{}`；账户 ID 与 label 从服务端会话派生，返回 `{enrollment_token,expires_at,gateway_url}`。仅用户主动 POST 才生成，GET 不生成码。Web 调用内部 `POST /v1/accounts/{account_id}/enrollments`，使用服务 Bearer，输入 `{label}`、输出 `{enrollment_token,expires_at}`。Ambient 不调用内部账户接口，也不接收服务密钥。

Ambient 的公开配对接口增加必填 `enrollment_token`：

```http
POST /v1/connector/pairings
Content-Type: application/json

{"enrollment_token":"<用户取得的短期接入码>","name":"我的电脑","scopes":["workspace.control"],"expires_in":86400}
```

成功输出仍为 `node_id,connector_token,pairing_code,pairing_expires_at,expires_at,workspace_origin`；期限仍为 300 秒至 30 日。消费接入码和创建节点使用同一数据库事务，容量拒绝不消耗接入码。其他账户领取不消耗 pairing code。

| 结果 | Ambient 处理 |
| --- | --- |
| 422 | 缺少接入码或输入非法，提示修正，不输出请求正文 |
| 409 | 码失效、已用或配对状态冲突，提示从门户主动生成新码 |
| 410 | 账户删除或资源终止，停止远程转发并显示重新授权入口 |
| 429 | 遵守 Retry-After 并显示额度/暂时繁忙，避免立即循环提交 |
| 配对响应丢失 | 设备凭据只返回一次，不自动重复创建；待 pending 过期后由用户重新发起 |

同一账户默认最多 3 个有效接入码、3 个 pending/claimed 节点、10 个有效节点（包含待批准节点），另有全局上限。原设备 Bearer、state/approve/revoke/tunnel 路径、批准字段及 Tunnel 消息契约继续使用。状态查询独立限流，默认 120 次/分钟，兼容原 2 秒轮询；连续失败应指数退避并加随机抖动，遵守 Retry-After。其他设备动作默认 60 次/分钟、账户动作 20 次/分钟、公开配对每来源 10 次/分钟。生产 nginx 每 IP 另限配对 5 次/分钟、state 120 次/分钟、其他控制动作 30 次/分钟，并有 burst 和 32 并发门禁；以返回的 Retry-After 退避。

授权到期、撤销、无效设备凭据和账户删除必须停止本机转发，不能无限轮询过期许可。HTTP 正文 2 MiB、WS 单帧 256 KiB。413、429、504、断线和响应丢失不能自动重放写操作或 Run 创建。HTTPS 节点浏览器使用 `__Host-` Cookie，由 Gateway 设置；Connector 无须读取或传递 Cookie。

## Ambient 改动位置

以 Ambient 当前代码为准；审查时入口如下：

| 文件 | 修改 |
| --- | --- |
| `backend/remote_workspace_api.py` | `RemoteWorkspacePair` 增加必填码；安全映射 409/422/429 与 Retry-After，不回显秘密 |
| `backend/remote_workspace.py` | `RemoteWorkspaceConnector.pair` 临时发送码；完善退避和终止状态 |
| `frontend/src/services/remoteWorkspace.ts` | 配对类型增加码，呈现有界错误 |
| `frontend/src/components/RemoteWorkspace.tsx` | 增加接入码输入、门户链接、五分钟说明；保留本机确认 |
| `tests/backend/test_remote_workspace.py`、`tests/frontend/remote_workspace.test.tsx` | 更新配对 fixture，覆盖过期/重放/错账户、额度、退避、不重放、本机确认 |

接入码只保留到本次配对完成，不写 `node.json`、localStorage、URL、日志或异常正文。保留原设备身份、节点凭据、用户数据和 Run，不重新初始化。旧 Ambient 匿名配对会被新 Gateway 拒绝，必须先完成客户端适配。组合测试 fixture 应先用测试 Web 服务账户生成 enrollment，再调用公开 pair。

## 云端版本边界

Gateway 已补账户绑定接入码、配额/限流、分页、状态回收和审计保留、幂等撤销、正文读取前预留容量、完整超时、Tunnel/WS 背压与进程资源预算。Web 已补接入码 BFF/UI、活动/历史分页、响应大小及归属验证、公开 origin 和独立域名验证、有界账户删除响应。部署仓库增加可选生产入口、可信代理专网、TLS/离线 PSL 校验及 SQLite 在线备份。

保持同一 Gateway DOMAIN/SCHEME 时，旧 paired 节点保留凭据、账户、grant、期限和 origin；旧 pending/claimed 在迁移时作废，重新接入。不会自动扩大权限。已删除账户 tombstone 永久保留；恢复数据库不能复活已删除账户或被撤销许可。

账户列表返回 `{nodes,next_cursor}`，参数 `limit=50`（最大 100）、`view=active|history` 和不透明 cursor；游标绑定账户与视图。此接口归 Web，Ambient 不需新增列表调用。

## 联调与合并门禁

云端实际环境和结果见[本次验证记录](../verification/WORKSPACE_GATEWAY_CLOUD_2026-10-01.md)，入口见[跨仓验证](../../tests/README.md)，部署准备见[运维说明](../operations/WORKSPACE_GATEWAY.md)。由 Ambient 完成：

1. 临时账户/数据库/工作区走完「登录 → 接入码 → 配对 → 同账户领取 → 本机确认 → 真实 Tunnel → 门户打开」，跨账户领取失败且不消耗码。
2. 真浏览器核对登录 Cookie、节点 Cookie、iframe 固定资源、CSP、双向 WS 和子协议；默认要求任意工作区 JavaScript 与门户使用不同可注册域名；临时 same-site-subdomains 必须额外验证真实浏览器 __Host Cookie、Domain 注入拒绝、旧 Cookie 拒绝、同站 fetch/form/iframe 防护，规则见[运维说明](../operations/WORKSPACE_GATEWAY.md)。
3. 验证缺码/过期/重放、quota、429 退避、慢正文/超大帧、断线不重复执行；撤销、到期、删账户关闭已有 HTTP/WS。
4. 同设备身份及原数据库重启，paired 保留、旧未批准节点作废；记录备份完整性、清理、tombstone 和回滚兼容性。
5. 在默认预算下实测完整前端/Frame加载、多WS和实际RSS，再用独立测试域名/DNS-01 wildcard TLS 运行 nginx + Web + Gateway + Ambient，确认公网账户 API/健康/指标关闭、伪造代理头被覆盖、未知 Host 拒绝、票据不写代理日志。

完成后交回 Ambient 提交、固定云端提交、实际测试环境和结果，再按原目标评估合并及部署。源码或本地验证不表示生产发布完成。
