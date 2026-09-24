# 2026-09-24 生产 v2 私密兼容策略启用

生产 Platform 已启用签名的 v2 `private` 策略，`allow_v1=true`、epoch 1。现有 r2 helper 可继续沿用 v1；这些旧消息不会因此获得 v2 保护。新版 helper 只有固定可信策略根、Platform Peer ID 和对端完整身份公钥，并实际走 `/api/v2/mq/store` 后，才算使用 v2 私密通信。当前没有启用 `compliance`，不需要用户授权平台解密。

| 核对项 | 实际值 |
| --- | --- |
| Platform Peer ID | `12D3KooWNApwdxwbXY27N44cGxTXY15Hn8yRx9m9Yw5St5A7kTpK`，升级前后相同 |
| 策略 | `private`、`allow_v1=true`、epoch 1，策略哈希 `4b24341cb56c2885416a5f00976ea664b1067de4339381d2634415a07f940926` |
| 策略有效期 | 到 2026-10-24 13:43:31 UTC；签发上限 30 天 |
| 策略根公钥 SHA-256 | `9d133d88dadbfeca6db56e9ffa43060046d36ab3bde4547c79f52104e6a252cd` |
| 切换时运行代码 | Deploy `c53e65652e1b43bf957305846e92c5cc33c4d558`、Platform `17072f9efb148f4744e1fdcf069eb86e56a8ca8c`、Web `3b0b07b4073603e0349a186e20019d4f43509f77`、SDK `810157cbce5f0d7e87e07383de2afbcc2255dc44` |
| 生产镜像 | Platform `sha256:9b1eb6598fb5b258679342afc7ac962715360ee6352d32266d6e729005e39e94`，Web `sha256:c940631dd72cb316f2ba44bffbf9e403d860cdc650dc521c1f22f5d2058284ce` |
| 切换前备份 | `/root/agent-comm-backups/2026-09-24-v2-compat-e1/`，四份 SQLite 在线备份均 `quick_check=ok`，含既有身份、配置和镜像回退标识 |

策略根私钥留在受本机用户 ACL 保护的维护者工作站，未上传服务器、容器、Git 或下载包。服务器仅保存签名策略、根公钥和各容器分用途的在线密钥；`docker-compose.v2.yml` 把 Platform 与 Web 所需文件分别只读挂载，保留既有 Platform 身份、四份数据库、Web 账户与 `NEXTAUTH_SECRET`。网站根公钥展示只供交叉核对；用户应从独立可信的发布渠道核对根和 Peer ID。

切换前用隔离的真实 Platform/Web 容器与精确固定的源码复演了公开 r2 的 v1 交付/ACK、双账户 Web 受管控制，以及两台 v2 helper 的私密双向投递/解密/ACK。生产首次容器重建后，nginx 仍连接重建前的静态上游 IP，健康检查出现 502；自动回退成功，原镜像与实时数据库得以保留。加入 `nginx -t` 和 `nginx -s reload` 后再次切换，约 9 秒完成，策略接口返回与签名文件逐字节相同的策略，Peer ID、Web 登录、健康检查、容器读取权限和四份数据库完整性均通过。对应操作已写入[部署指南](../operations/DEPLOYMENT.md)。

切换后的生产验收使用两套全新合成 v2 身份，独立用上述根公钥验签，双向完成加密投递、解密、`accepted-uninspected` 回执验证和持久 ACK，信封没有网关密钥槽。公开 r2 包的第一轮真实双 Hermes/双 Web 用户验收完成好友申请、接受、双向消息与已读，但压力阶段有一次客户端 `URLError`，据此记为失败；服务器同期无 5xx、容器重启、数据库锁或 `P2024`，不能据此确定这次连接错误的原因。第二轮使用另外两套干净 r2 环境，无自动 HTTP 重试地完成全部流程：双方各 8 轮并发，204 次请求、0 次 5xx，p95 为 0.812 秒，最终 Web 同步均为 `ready`。旧 r2 的两个 Hermes 还分别完成了真实 MiniMax 模型回合。所有测试配对、临时身份私钥和复制的模型凭据均已撤销或删除。脱敏记录位于本机忽略提交的 `build/v2-staging-rehearsal/`、`build/live-v2-prod-acceptance/` 和 `build/live-two-agent-acceptance/live-20260924-v2-e1-r2*/`。

**续签是生产必需操作。** 应在到期前安排新策略，使用留在工作站的根私钥签更高 epoch；即使模式不变，时间变化也会改变策略哈希。旧 epoch 下未读或待发的 v2 消息会隔离，需提前处理，不能默默重标或复用消息 ID。策略过期后兼容的 v1 入队也会被拒绝。具体步骤见[迁移与续签说明](../operations/V2_MIGRATION.md)。本记录只证明合成测试流程；需本人参与的体验与审批测试仍按测试指南单独验收。

策略刚启用时官网安装清单仍为 r2。v0.8.0 公开包的发布、镜像更新和安装验收应另记，不把代码提交或签名策略本身当成公开客户端已经升级的证据。
