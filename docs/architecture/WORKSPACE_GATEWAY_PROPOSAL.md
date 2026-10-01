# Ambient Workspace Gateway

此功能已合入 `main`；生产启用范围见[发布记录](../releases/AMBIENT_WORKSPACE_DEPLOYMENT_2026-10-01.md)。Ambient 拥有本地工作区、Agent、App、密钥和 Run；Gateway 只中转有界 HTTP/WebSocket、持久化授权与审计元数据，不保存业务正文或重派任务。云端与本机交接见[2026-10-01 文档](../developers/AMBIENT_WORKSPACE_HANDOFF_2026-10-01.md)，历史缺陷证据见[审查记录](WORKSPACE_GATEWAY_REVIEW_2026-10-01.md)。

## 接入与授权

1. 已登录 Web 主动调用 BFF 生成有效期 300 秒的一次性接入码；Gateway 以摘要保存，绑定服务端会话对应账户。
2. Ambient 提交接入码调用公开 pairings，原子消费码并创建 pending 节点。设备凭据仅在成功响应返回一次。
3. 同一云账户领取五分钟 pairing code；其他账户不能领取、不能消耗码。
4. 本机显示账户、权限及期限，并以匹配的 account_id/grant_id 明确批准。接入码或云端领取不代替本机确认。
5. 批准的 Connector 建立 Tunnel。门户生成短期一次性 launch ticket，节点 Host 消费后设置 host-only Cookie 并立即跳转根路径。
6. 本机/云端撤销、账户删除、授权或浏览器会话到期会关闭已有连接。断线不自动重放请求。

## HTTP 与 Tunnel 契约

所有对外时间为 ISO UTC 字符串。节点状态为 pending、claimed、paired、revoked、expired，online 为独立布尔值。pending 的账户 ID 来自接入码，但 account_label 为空，不能当作已领取授权。节点字段继续为 node_id,name,status,online,account_id,account_label,grant_id,scopes,expires_at,workspace_origin,last_seen_at。

| 接口 | 输入 / 输出 |
| --- | --- |
| POST /v1/accounts/{account_id}/enrollments | 服务 Bearer，{label} → {enrollment_token,expires_at} |
| POST /v1/connector/pairings | {enrollment_token,name,scopes,expires_in} → {node_id,connector_token,pairing_code,pairing_expires_at,expires_at,workspace_origin} |
| GET /v1/connector/state | 设备 Bearer → 节点 |
| POST /v1/connector/approve | 设备 Bearer，{account_id,grant_id} → 节点 |
| POST /v1/connector/revoke | 设备 Bearer → 节点；重复撤销不重复写审计 |
| WS /v1/connector/tunnel | 设备 Bearer；仅已批准且有效 |
| POST /v1/accounts/{account_id}/pairings/claim | 服务 Bearer，{code,label} → 节点 |
| GET /v1/accounts/{account_id}/nodes | 服务 Bearer；limit=1..100（默认50）、view=active或history、cursor → {nodes,next_cursor} |
| POST /v1/accounts/{account_id}/nodes/{node_id}/launch | 服务 Bearer → {url,expires_at} |
| DELETE /v1/accounts/{account_id}/nodes/{node_id} | 服务 Bearer → 节点 |
| DELETE /v1/accounts/{account_id}/nodes | 服务 Bearer → {revoked:数量} |
| DELETE /v1/accounts/{account_id} | 服务 Bearer → {revoked:数量}，永久 tombstone；重复幂等 |

配额不足不消耗接入码；分页 cursor 使用签名并绑定账户、视图及排序位置，不能跨账户使用。接入码失效/重放为409，参数非法422，删除账户410，限流/容量429。期限仍为300秒至30日。

Tunnel hello/http.request/ws.open 携带扁平 node_id,account_id,grant_id,scopes,workspace_origin。HTTP body、WS kind:bytes 的 data 为严格 base64，头为二元数组。WS open 附 subprotocols，accept 的 subprotocol 可为 null。支持 http.response、ws.accept、ws.data、ws.close、ping/pong、revoked；严格校验消息与大小。

## 隔离与资源

开发使用 localhost 和节点子域；生产仅 HTTPS，控制和节点需同一可注册域名，默认 `separate-site` 与门户使用不同可注册域名。显式 `same-site-subdomains` 可临时共用注册域，但保持每节点独立 Host，门户在节点域之外，并同时部署全部门户 __Host Cookie、Fetch Metadata/Origin guard 与 nginx 防护。相同 Host 的路径方案不满足存储、Cookie 与 service worker 隔离。临时模式仍存在父域 Cookie 耗尽的可用性风险，具体规则见[运维说明](../operations/WORKSPACE_GATEWAY.md)。Gateway 离线使用完整 ICANN/PRIVATE Public Suffix List，Web 使用锁定版本的 PSL 库。生产 Cookie 为 __Host- 前缀、Secure、HttpOnly、SameSite=Lax、Path=/，无 Domain；最长一小时，不超过授权期。

公网入口仅开放控制 Host 的五条 Connector 路由和精确节点 Host；账户、健康、指标只在内网。单独代理专网及精确 /32 可信来源，不信任客户端伪造的 forwarded 头。Gateway 与 Connector 双重校验路径；/api/*、/ws/* 到 Backend，静态资源到 Frontend，禁止代理 /api/remote-workspace。秘密、Cookie、Authorization、Host、代理身份和 hop-by-hop 头不向本机转发。

仅固定 Frame 壳及模块资源公开，其余请求要求节点会话；GET/HEAD 不能带正文。固定 vendor 使用受限 gzip 原始字节，因为 Babel 未压缩体积超过2MiB；压缩 payload 仍受限，普通 API 不普遍透传 encoding。普通 Frontend HTML 仅注入无秘密同源配置、重算长度并删除 encoding，保持 CSP；Frame HTML 不改写。

同账户默认最多3个有效接入码、3个待批准节点、10个有效节点（含待批准节点）。全局上限、限流表、HTTP/浏览器WS/Tunnel并发、队列与逻辑内存预算同时生效。HTTP正文2MiB、WS帧256KiB；正文读取前取得资源预留，完整处理超时，断开释放。Uvicorn还限制连接数、WS接收队列和帧大小；应用预算不是整个进程的实测RSS。运维配置及实际验证见[运维说明](../operations/WORKSPACE_GATEWAY.md)和[验证记录](../verification/WORKSPACE_GATEWAY_CLOUD_2026-10-01.md)。

过期授权/码和历史节点按保留配置清理，审计有时间与行数上限。删除账户 tombstone 永久保留。升级保留既有 paired 身份/grant/期限；旧匿名 pending/claimed 作废。Web验证删除意图/密码后先使 Gateway 账户终止，再完成数据库删除；Gateway失败则不删除，恢复数据库不能复活删除许可。

首版为单 Gateway 实例，不能多副本共享 SQLite 路由，不提供计费、跨账户共享、P2P或可靠任务队列。真实 Ambient 和浏览器联调仍是合并门禁。
