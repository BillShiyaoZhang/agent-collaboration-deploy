# Ambient 云入口 proposal 评审与上线讨论 — 2026-10-01

## 结论

**架构方向符合目标，但当前实现存在公开上线的重大可用性问题。本轮保留 proposal，暂不合入 main，也不部署云服务器。** 需要先修复匿名准入、节点与审计的生命周期，以及请求读取阶段的资源预算，再完成生产入口和容量验收。这不是要求推翻 Ambient Connector，也不需要把本机执行迁到云端。

评审依据为目标对话「比较网页远程访问方案」：用户希望运营远程连接平台，Ambient 提供用户电脑上的 Agent、App、工作区和 Run，Agent Collaboration 提供账户、云入口和中转。云项目改动原先作为独立建议提交，本次由部署项目侧决定是否采用。

本次固定评审版本：

| 仓库 | 版本与范围 |
| --- | --- |
| Deploy main | `e607a3ea72657b7d0eb861a04e4a09f1421f7a8b` |
| [Deploy proposal](https://github.com/BillShiyaoZhang/agent-collaboration-deploy/tree/94aeccbbf82aa855a2d430b6e34193789a99bff1) | `94aeccbbf82aa855a2d430b6e34193789a99bff1`，新增 Gateway 与可选 Compose overlay |
| [Web proposal](https://github.com/BillShiyaoZhang/agent-collaboration-web/tree/fc271b6b4093fa23b334869d22c0edee11b27da4) | `fc271b6b4093fa23b334869d22c0edee11b27da4`，账户 BFF 与工作区入口 |
| Platform / SDK | proposal 未改动，分别固定 `407ed72b4fdf1c42f25e3afe56e0de9308813c25` / `e2f6fce544f8dcf8523fcacb70184d51c3749a14` |

原方案见 [Gateway 设计](https://github.com/BillShiyaoZhang/agent-collaboration-deploy/blob/94aeccbbf82aa855a2d430b6e34193789a99bff1/docs/architecture/WORKSPACE_GATEWAY_PROPOSAL.md)、[服务 README](https://github.com/BillShiyaoZhang/agent-collaboration-deploy/blob/94aeccbbf82aa855a2d430b6e34193789a99bff1/workspace-gateway/README.md)和 [Web 设计](https://github.com/BillShiyaoZhang/agent-collaboration-web/blob/fc271b6b4093fa23b334869d22c0edee11b27da4/docs/architecture/REMOTE_WORKSPACE.md)。这些分支中的用户文档和历史验收不代表现网已经提供该服务。

## 可以保留的设计

本机主动建立出站通道适合没有公网 IP 的用户；本机继续拥有执行与持久状态，云端不建立第二套 Run 队列。断线不自动重放写请求，避免把丢失回执当成执行失败。

云端领取后仍需本机核对账户、范围、期限并确认；设备凭据与 Web 服务凭据分开。Web BFF 从服务端会话取得账户 ID，校验修改请求的 Origin，并验证 Gateway 返回的节点仍归该账户。节点浏览器会话使用短期、HttpOnly、host-only Cookie，launch ticket 一次性消费；撤销与到期会终止已有通道。删除账户先在 Gateway 写入永久 tombstone 并撤销，随后删除 Web 数据，失败时不冒充删除成功。这些边界值得保留。

平台服务多个用户，可以先让每个账户访问自己的独立本机节点；共享同一 Ambient 工作区、云端执行、计费和多副本路由不必成为首版前提。独立 HTTP/WebSocket 通道也不能被宣传为沿用已有聊天 RPC 的签名或合规政策。中转端能读取正文，即使它不持久化正文，也需在连接授权与服务说明中说清楚。

## 三项上线阻碍

### 1. 匿名请求可以长期耗尽全站节点容量

[`pair()`](https://github.com/BillShiyaoZhang/agent-collaboration-deploy/blob/94aeccbbf82aa855a2d430b6e34193789a99bff1/workspace-gateway/workspace_gateway/app.py#L423) 不要求账户或已有设备凭据，唯一容量门禁为全表 `count(*) >= max_nodes`，默认 10,000。过期 pending、expired、revoked 节点仍占这一额度；[`sweep()`](https://github.com/BillShiyaoZhang/agent-collaboration-deploy/blob/94aeccbbf82aa855a2d430b6e34193789a99bff1/workspace-gateway/workspace_gateway/app.py#L390) 只清理 launch 与 session，重启也保留全部节点。

隔离复现把 `max_nodes` 调为 2：三次匿名生成配对依次返回 `200, 200, 429`。时钟快进 100,000 秒并等待 sweep 后，创建仍返回 429，节点数仍为 2；重启同一临时 SQLite 后仍返回 429。这个实验验证容量与回收逻辑，没有向生产发送 10,000 次请求。

这使任意未登录客户端能够阻止后续正常用户接入，配对码的五分钟期限不会自动恢复服务。单纯提高上限或添加低速率限制只会延后容量耗尽。正常用户反复重新配对也会累积历史节点。

建议区分短期匿名 pending 与账户已批准节点：限制全局及来源的 pending 数量与创建速率，及时回收未领取的过期申请，给账户设置可配置节点额度；历史失效记录按明确的保留策略处理，不占活跃接入容量。若采用登录后发放短期 enrollment ticket，需要同步变更 Ambient 的首装流程与接口，不能只修改云端。删除账户 tombstone 的禁止重新授权语义必须保留。

同组契约问题还包括账户列表：Gateway 返回全部历史节点且不分页，Web 将响应限制为 128 KiB、最多 500 个节点。积累足够多历史记录后整个列表会被拒绝，用户无法通过该列表打开或撤销节点。应修复账户额度、历史分页与清理契约，保留 Web 的有界响应限制。

### 2. 匿名取得的设备凭据可以持续增加审计记录

匿名生成配对即取得 `connector_token`。[`device_revoke()`](https://github.com/BillShiyaoZhang/agent-collaboration-deploy/blob/94aeccbbf82aa855a2d430b6e34193789a99bff1/workspace-gateway/workspace_gateway/app.py#L482) 接受这一凭据，无需领取或本机批准。[`revoke()`](https://github.com/BillShiyaoZhang/agent-collaboration-deploy/blob/94aeccbbf82aa855a2d430b6e34193789a99bff1/workspace-gateway/workspace_gateway/app.py#L381) 对已撤销节点也重复写 audit；审计表没有清理或容量上限。

隔离复现对同一设备连续撤销三次，全部返回 200，audit 行数从 2 增加到 5。记录的是持久写入增长，未进行磁盘耗尽实验。节点已撤销并不终止这条匿名写入路径。

应让重复撤销保持状态幂等，并避免重复保存同一状态转换；对设备操作设置速率预算，给审计定义保留期限、大小上限、清理与告警。必要的安全审计与账户 tombstone 不应通过无差别清库来修复。HTTP 转发成功也逐次写入 audit，需要一并计入正常流量下的磁盘和写入预算。

### 3. HTTP 读取阶段未纳入节点并发和整体期限

[`proxy()`](https://github.com/BillShiyaoZhang/agent-collaboration-deploy/blob/94aeccbbf82aa855a2d430b6e34193789a99bff1/workspace-gateway/workspace_gateway/app.py#L789) 先检查在途 HTTP 数量，随后完整读取请求正文，在读取完成后才向 `tunnel.http` 预留名额。30 秒 timeout 从 tunnel exchange 才开始，正文读取不在其中。上传结束后的第二次授权与额度检查是正确的，但没有约束上传等待期间的占用。

隔离 ASGI 实验设节点并发 16、请求期限 0.05 秒：20 条带有效合成会话的 POST 慢上传都进入 stream；0.25 秒后 20 条仍等待，而 `tunnel.http` 占用为 0。此实验模拟请求读取，没有测真实 nginx、网络带宽或服务器 OOM，也没有运行匿名 Frame 请求变体。

镜像 [`Dockerfile`](https://github.com/BillShiyaoZhang/agent-collaboration-deploy/blob/94aeccbbf82aa855a2d430b6e34193789a99bff1/workspace-gateway/Dockerfile#L9) **已有 Uvicorn `--limit-concurrency 256` 全局兜底**，不能称为无限连接。然而单个来源仍可占据这份共享额度；它没有保证节点公平性，也没有覆盖应用声明的读取期限。公开固定 Frame 路由无需浏览器 Cookie，因此其请求也需入口预算。

建议在读取前原子预留节点名额，并在成功、拒绝、取消、断开时释放；期限覆盖读取、发送、等待响应全过程，同时限制总缓冲字节、节点与全局连接数、来源速率和带宽。生产 nginx 的请求体、读取时间和连接限制应与应用预算配合，不能只依赖某一层。

## 生产接线与容量仍待验收

[`docker-compose.workspace.yml`](https://github.com/BillShiyaoZhang/agent-collaboration-deploy/blob/94aeccbbf82aa855a2d430b6e34193789a99bff1/docker-compose.workspace.yml) 只绑定 `127.0.0.1:8090`，默认 `localhost:8090/http`，刻意不接现网 nginx。直接追加 overlay 不能提供外网工作区入口。上线至少需要：

- 实际可用的控制域名、节点 wildcard 域名、DNS、HTTPS 证书与续期；保留节点 Host，支持 WebSocket upgrade，阻断公网 `/v1/accounts/*`，抑制 launch ticket 查询参数日志。
- 明确节点页面是不受信任的用户内容。建议门户与工作区采用不同的可注册域名，HTTPS 节点 Cookie 使用 `__Host-` 前缀，并做真实浏览器隔离验收。节点页面可能执行用户提供的 JavaScript；剥除上游 Set-Cookie 无法约束 document.cookie。Cookie 可以声明父域，而 `__Secure-` 不禁止 Domain，`__Host-` 要求 Secure、Path=/ 且禁止 Domain，见 [Mozilla Cookie 说明](https://developer.mozilla.org/en-US/docs/Web/HTTP/Reference/Headers/Set-Cookie#cookie_prefixes)。因此仅有不同 origin 与 host-only 默认 Cookie 还不足以排除同父域 Cookie 注入。本轮未复现门户会话混淆，不将它写成已证实漏洞。
- 将连接、字节、队列、节点和审计额度配置化，记录容量拒绝、内存、磁盘、时延与错误率；上线初期采用受控接入规模。首版可以是单实例，但应说明重启会断开通道、由本机重连且不重放写请求。
- Gateway 独立状态卷的在线备份、恢复和回滚演练；保留设备授权、账户 tombstone 与当前用户状态。

[现行部署指南](../operations/DEPLOYMENT.md)记录云主机只有 1.8 GiB 内存，曾因 Web 在线构建触发全局 OOM。本次未连接云服务器，没有测得当前容量余量。默认 BrowserPipe 队列 32 帧、帧上限 256 KiB、每节点 16 个浏览器 WS，按解码等效 payload 计算即可约 128 MiB/节点，还未计入 base64、Python 对象及其他缓冲；这是配置推导，不是实际测量。不能据此默认与现有 Web/Platform 共机安全。

通过上线门槛后，应按现行操作指南在其他 Linux/amd64 主机从固定提交构建 Web 与 Gateway 镜像，校验后上传；保留 v2 Compose、现有身份、数据库和密钥，做好一致备份与旧镜像回滚标识。新增 nginx 挂载需重建容器，服务重建后检查并 reload nginx。此功能没有要求重建 Platform 或修改 SDK。

## 建议的实现与验收顺序

1. 在 Gateway 修复上述三项资源生命周期问题，明确匿名接入与账户配额；在 Web/Ambient 同步必要的接口与引导变更。
2. 补隔离回归：匿名容量达到上限后过期申请能回收、正常账户仍能接入；重复撤销不造成无限审计增长；慢请求先占额度并按整体期限退出，取消/断开不泄漏名额；审计清理不破坏 tombstone。
3. 在隔离 Linux Docker 环境验证镜像、真实 ingress 与多节点负载，包含固定 Frame、HTTP/WS 回压、Gateway 重启与状态卷恢复。记录共享主机其他组件受影响的上界，并据实际容量设置初期额度。
4. 用真实 HTTPS 节点域名完成浏览器与 Ambient Connector 的配对、本机确认、Widget、聊天、离线恢复、撤销、到期与删账户验收；核对日志没有票据或设备凭据。
5. 同步用户、使用 Agent、开发者与运维文档及服务说明，再由内到外提交 Web 和 Deploy、固定可取得的子模块版本，合并 main 并按部署指南上线。

不需要等待计费或多副本全部实现才提供受控首版，但匿名准入与状态回收、请求预算、生产域名隔离和容量证据必须先成立。继续采用自定义 Gateway 是可行选项；是否将数据平面改用成熟反向隧道组件可单独讨论，不应拿更换组件替代账户与本机授权。

## 本次验证范围

2026-10-01，Windows；使用 Ambient 现有 Python 环境、FastAPI TestClient、临时 SQLite 与 ASGI 模拟请求。Gateway 源码与固定 proposal 核对；原有 Gateway 测试重跑为 **22 passed，1 条上游 Starlette/httpx 弃用提示**。Web 的 workspace-nodes 与 middleware 定向单测本次为 **22/22 通过**。三项资源问题已用上述小规模隔离实验复现。既有本地浏览器验收与 Web Linux 397 项通过属于 proposal 的历史记录，本轮没有重复执行，不冒充本次生产验收。

可复现工具为 [review_workspace_gateway_limits.py](../../tests/integration/review_workspace_gateway_limits.py)，仅使用临时 SQLite、TestClient 和模拟 tunnel，不建立真实网络连接。用安装了 proposal `requirements-dev.txt` 的 Python 执行：

```sh
python tests/integration/review_workspace_gateway_limits.py --gateway-root /path/to/review-copy/workspace-gateway
```

`review-copy` 必须为上述 Deploy proposal 固定提交；无需初始化其子模块。工具断言评审中观察到的问题，未来修复后应失败或得到不同结果，届时应以修复后的回归测试为准。它不是生产容量测试，也不替代真实 ingress 验收。

保存后的复现工具已再次执行，以上四组输出与断言均通过；文档结构检查 `python tools/maintenance/check_structure.py` 为 **157 个 Markdown，0 errors**。临时数据库、测试输出和用户凭据未纳入提交。

本次没有生产请求、用户身份操作、镜像构建、云服务器变更或公网负载测试。后续验收必须覆盖这些未测范围，单元测试全绿不能代替它们。
