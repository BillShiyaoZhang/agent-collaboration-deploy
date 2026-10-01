# Ambient 长期授权建议（2026-10-02，尚未部署）

本建议基于部署仓库 `bfc7d0bec494612880d9c150ee44fb9fcee48942`；Gateway 源码与当前发布的 `152dea974f09e5dbca4d0da16867df1be9d3395e` 相同。独立建议分支为 `codex/ambient-until-revoked-20261002`。本记录不表示原项目 main、服务器镜像、配置或数据库已经更新。

## 协议

在原账户绑定 enrollment → pairing → 同账户 claim → 本机 approve 流程中，配对请求新增可选 `until_revoked`，只接受 JSON 布尔值，默认 `false`。原 `expires_in` 的默认值和 300 秒至 30 天验证保持；即使选择长期模式，该字段仍须有效。省略或传 `false` 的请求保持原有限期限行为。

输入校验失败仍返回 422，使用固定安全错误消息，不回显 Pydantic input、请求正文或接入码。

`until_revoked: true` 的配对响应必须使用字面期限 `9999-01-01T00:00:00Z`，对应 Unix 秒 `253370764800`。这是可撤销的长期节点授权；不可用 `datetime.max`、Infinity 或 null，不改变已有 grant 的期限。使用 UTC epoch 加 timedelta 格式化时间，避免 Windows CRT 的 year 3000 限制和最大日期的浮点舍入/时区溢出。

Ambient 在发送长期配对请求前，先对用户填写的公开控制 origin 执行无凭证 `GET /v1/connector/capabilities`；不得携带 Cookie、Authorization、接入码、正文或 query，不跟随重定向。成功响应为以下有界 DTO，不生成节点、接入码或浏览器会话：

```json
{"supported_grant_modes":["bounded","until_revoked"]}
```

只有确认支持字面模式 `until_revoked` 才提交长期 POST。旧服务器的 404、缺失/无效能力或网络失败应在 POST 前停止；有限期请求继续原流程。响应和待批准 claimed 状态中的长期期限必须精确匹配上述字面 ISO，不能静默截短、延长或替换为等价 offset。用户在本机核对账户、权限及“直到撤销”后明确批准。

生产 ingress 仅在控制 Host 新增上述 exact GET 路由，沿用控制请求限流/并发/无日志规则；其他方法为 405，后缀路径为 404。`/health`、`/v1/metrics`、账户接口仍不向公网开放。Gateway 同样拒绝能力查询携带凭证头或 query，响应不包含 Cookie、重定向或用户信息。节点 Host 和内部 service Host 不提供控制能力查询。

## 不变的权限与会话边界

enrollment 与待批准 pairing 仍最多五分钟。跨账户领取、单次消费、配额、本机批准、设备 Bearer、grant/scopes 归属和不重放写操作继续原契约。旧 paired 身份与期限不迁移；撤销或删账户仍关闭 HTTP/WS/Tunnel，账户 tombstone 仍永久保留。

长期节点授权不延长打开票据或 Cookie：launch 默认 60 秒，浏览器 session 默认一小时，且不超过节点期限。现有 WS 会话到期规则保持；浏览器会话到期后从登录门户重新打开。Portal 现有 Web schema 可解析 year 9999 的 ISO，功能不依赖改 Web 子模块；“直到撤销”显示优化可由 Web 项目另行考虑。

## 验证与部署门禁

先保存本契约，再用隔离数据库测试：严格布尔值与有限期边界、能力 DTO 无凭证无副作用、exact host/method/path 及私有路由保留、长期配对/领取/本机批准、旧 paired 重启期限保持、长期节点的短 session 到期、撤销/删账户关闭 Tunnel、UTC 时间跨 Windows 格式化。运行完整 Gateway 测试及 ingress renderer 单元测试，记录实际结果；未执行公网或容器 ingress 验收时须明确说明。

原项目接受建议后，从固定源码构建 Gateway 镜像，备份实时授权库并核验镜像/source label；不清空卷或迁移已有期限。重新运行 ingress renderer、检查新增 exact 能力路由与原私有路由、执行 nginx 配置检查和 reload，再核验公网 HTTPS 能力 DTO与原有路由拒绝。随后在本机显式新授权，不能靠编辑旧 node.json 或云数据库延长期限。部署操作按[运维指南](../operations/WORKSPACE_GATEWAY.md)执行；本建议分支不自行部署。
