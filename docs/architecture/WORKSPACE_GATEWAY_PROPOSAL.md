# Ambient Workspace Gateway（独立合并建议）

此功能作为独立建议分支发布，未合入上游 main，不改变现有 Agent Comm 控制协议。Ambient 仍拥有本地工作区、Agent、App、密钥和 Run；新 Gateway 只中转有界 HTTP/WebSocket，持久化连接授权及审计元数据，不存业务正文、不重派任务。

## 首版连接流程

1. Ambient Connector 主动调用 `POST /v1/connector/pairings`，保存返回的设备凭据。五分钟一次性码在数据库只存摘要。
2. 已登录 Web BFF 使用独立服务 Bearer 领取该码，账户 ID 必须来自服务端会话。
3. 本机显示领取账户、权限及期限，调用 `POST /v1/connector/approve`，显式提交 `account_id` 和 `grant_id` 并严格匹配领取结果。
4. 已确认 Connector 主动建立 `/v1/connector/tunnel`。云端打开链接仅为短期一次性 launch ticket；节点独立 Host 消费票据后设置 host-only Cookie，并立即跳转 `/`。
5. 本机或云端撤销、授权/会话到期时，已有连接也关闭。断线不会自动重放任何请求。

## 稳定接口

所有对外时间为 ISO UTC 字符串（数据库内部为 Unix 秒数）。节点状态为 `pending`、`claimed`、`paired`、`revoked`、`expired`，`online` 是独立布尔值。节点字段为 `node_id,name,status,online,account_id,account_label,grant_id,scopes,expires_at,workspace_origin,last_seen_at`。

| 方法和路径 | 输入 / 输出 |
| --- | --- |
| `POST /v1/connector/pairings` | `{name,scopes,expires_in}`（300 秒至 30 日） → `{node_id,connector_token,pairing_code,pairing_expires_at,expires_at,workspace_origin}` |
| `GET /v1/connector/state` | 设备 Bearer → 节点 |
| `POST /v1/connector/approve` | 设备 Bearer，`{account_id,grant_id}` → 节点 |
| `POST /v1/connector/revoke` | 设备 Bearer → 节点 |
| `WS /v1/connector/tunnel` | 设备 Bearer；已确认且未过期 |
| `POST /v1/accounts/{account_id}/pairings/claim` | Web 服务 Bearer，`{code,label}` → 节点 |
| `GET /v1/accounts/{account_id}/nodes` | Web 服务 Bearer → `{nodes:[节点]}` |
| `POST /v1/accounts/{account_id}/nodes/{node_id}/launch` | Web 服务 Bearer → `{url,expires_at}` |
| `DELETE /v1/accounts/{account_id}/nodes/{node_id}` | Web 服务 Bearer → 节点 |
| `DELETE /v1/accounts/{account_id}/nodes` | Web 服务 Bearer → `{revoked:数量}`，批量撤销 |
| `DELETE /v1/accounts/{account_id}` | Web 服务 Bearer → `{revoked:数量}`，持久账户 tombstone 并撤销；重复调用幂等，用于删账户 |

Tunnel `hello`、`http.request`、`ws.open` 以扁平字段携带 `node_id,account_id,grant_id,scopes,workspace_origin`。HTTP `body`、WS `kind:bytes` 的 `data` 为严格 base64；头为二元数组。WS open 附带浏览器提供的 `subprotocols`，accept 的 `subprotocol` 可为 null。支持 `http.response`、`ws.accept`、`ws.data`、`ws.close`、`ping`/`pong` 与 `revoked`。

## 隔离与限制

开发使用 `<node_id>.localhost:<port>`；生产使用独立 wildcard 域名和 HTTPS。服务密钥必须显式配置；生产拒绝空密钥和明文公网 origin。账户接口不得在节点 Host 暴露。节点 Cookie 不使用 Domain，HTTPS 设置 Secure，HttpOnly、SameSite=Lax，最多一小时且不得超过授权到期。

Gateway 与 Connector 双重限制目标/路径。`/api/*`、`/ws/*` 到 Backend，普通静态资源到 Frontend；本机 `/api/remote-workspace` 禁止代理。只有 `/_ambient/frame.html`、`/frame_shell.css`、`/frame_shell.mjs`、`/controller_facade.mjs`、`/presentation_context.mjs`、`/vendor/*` 固定壳和模块依赖公开到 Frame。Cookie、设备 Bearer、Authorization、Host、代理身份、hop-by-hop 头不向本机转发。HTML 只注入非秘密同源配置，保持 CSP 和 sandbox 边界。

Web 先验证账户删除意图与密码，再调用 terminal account 接口；Gateway 持久记录删除账户 ID 并禁止后续 claim、approve、launch，随后失效已有许可和连接，阻止跨服务删除期间的并发重新授权。Gateway 失败时 Web 不完成删除；Web 数据库删除失败时连接已经安全关闭。此 ID tombstone 不表示删除全部元数据或备份，重建账户必须采用新 ID。

HTTP 正文 2 MiB；单 WS 帧 256 KiB；每节点 HTTP/浏览器 WS 各最多 16 并发；请求/WS 建立等待 30 秒。实现为单 Gateway 实例，不声称具备生产多副本路由、计费、P2P、跨账户共享或可靠排队执行能力。生产 TLS 由外部反向代理提供，并必须保留节点 Host。

固定 Frame 资源使用 gzip 原始传输，因当前 Babel vendor 未压缩文件超过 2 MiB。Connector 只对固定壳白名单强制请求 gzip 并读原始压缩字节；Gateway 只对该 Frame 路由保留 `Content-Encoding: gzip`。压缩后的 HTTP/tunnel payload 仍受 2 MiB 上限，普通 API/Frontend 保持原大小限制，不普遍透传 encoding。Frontend HTML 改写后重算长度并删除 encoding，Frame HTML 与模块不注入配置或改写 CSP。

## 本地测试

使用独立临时 SQLite 和假本机目标先验证失败再实现。覆盖跨账户隔离、码和 launch 重放、配对后本机确认、真实双向 HTTP/WS、子协议、代理头/路径/配额、撤销和到期终止已建立通道、重启持久状态。Ambient/浏览器完整工作区验收另由集成测试记录实际环境。
