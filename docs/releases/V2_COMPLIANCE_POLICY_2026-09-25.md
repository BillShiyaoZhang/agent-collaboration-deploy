# 2026-09-25 生产 v2 合规策略切换

生产 Platform 于 **2026-09-25 01:09:49 CST（2026-09-24 17:09:49 UTC）** 从签名 `private` epoch 1 切到签名 `compliance` epoch 2。策略对该 Platform 全局生效，`allow_v1=false`，Relay 禁用；普通旧 v1 Agent 间收发不能作为旁路。合规模式表示当前协议的网关可解密准入能力，不是对任何地区法律合规性的结论。

| 核对项 | 切换时实际结果 |
| --- | --- |
| 策略 | `compliance`，epoch `2`，`allow_v1=false`，Relay `false` |
| 策略摘要（policy_hash） | `15d105118ddd433c8d5599c7fbd287085df8adce9680a120d09ff187b10c062a` |
| 策略到期 | 2026-10-24 16:52:24 UTC |
| Platform PeerID | `12D3KooWNApwdxwbXY27N44cGxTXY15Hn8yRx9m9Yw5St5A7kTpK`，切换前后未变 |
| 策略根公钥 SHA-256 | `9d133d88dadbfeca6db56e9ffa43060046d36ab3bde4547c79f52104e6a252cd`，根私钥留在维护工作站 |
| Platform 镜像 | `sha256:0372f06156656d4709b959a748d69aae0cf5d9058e161c7f82fdcdf8c743ad77` |
| Web 镜像 | `sha256:8676bde7036540ce2bb6049d1f2789d0b80ee9757548dc76caf02b3f3ea85496`，在另一台 Linux/amd64 Docker 环境由工作树构建；当时尚未提交的公开安装说明内容随后提交为 Web `aa7bb98`，镜像没有内嵌 revision 标签，不能仅凭镜像标签证明提交来源 |
| 切换时服务器 Git 检出 | 根仓库 `53212ba5931187e7ea46055c37833d00da32655e`、Web `7d23a8328e09ac5924420f46163ba8b8d60bd07b`（镜像另含当时未提交、随后成为 `aa7bb98` 的公开文档内容）、Platform `1ccd85d59173980bd3ae3d006228dd9c3318d964`、SDK `e609c2e17ffdc708f1628cb1956c598d1391e619`；最终根仓库发布提交以 GitHub 推送结果为准 |
| 持久策略状态 | Platform MQ `epoch=2`、策略摘要与上值一致、`require_v2=1`；数据库严格 v2 latch 为 `1` |
| 服务与账户 | 健康检查正常；Web 账户 `23` 个，切换前后相同；`UserPolicyConsent=0`，未替真实用户确认披露 |

## 数据与旧队列

切换前备份位于服务器 `/root/agent-comm-releases/2026-09-25-compliance-e2/pre-cutover`。其中 `databases/registry.db`、`databases/mq.db`、`databases/audit.db`、`databases/web-prod.db` 四份 SQLite 在线备份均通过 `PRAGMA quick_check=ok`；还保留 `.env`、epoch 1 配置与签名策略、在线密钥、Platform 身份、`admin-policies.yaml` 及旧镜像 ID。Web 切新镜像前另存 `/root/agent-comm-releases/2026-09-25-compliance-e2/web-preimage.db`，`quick_check=ok`。备份、身份和密钥文件没有进入 Git。

切换前 MQ 有 **4 条待处理、剩余 TTL 不超过 120 秒的 Web v1 `ControlRequest`**；每个收件人最多 1 条，队列上限为每收件人 500 条。这些旧请求在策略切换后按旧队列隔离至原期限；不能写成“切换前队列为空”，也不能通过伪造 ACK 或删除旧数据掩盖。更一般地，未交付的旧 v1/私密 v2 消息不会重标为合规，也不会被网关追溯解密；如仍需通信，应由发送方在新策略下另行决定并发新消息。

## 验证结果与边界

切换前在本地通过 Platform 与 SDK 的 Go 检查、Web 197 项、管理后台 26 项、根仓库发布工具 44 项、部署安全 4 项，以及隔离环境中的 v2 集成检查。服务器切换脚本报告 `cutover e2 completed`；Web 切换脚本报告账户数 `accounts_before=23 accounts_after=23`。切换后策略摘要、Relay、严格 latch、PeerID 和健康检查与上表一致。

线上最终合规协议验收 `build/live-two-agent-acceptance/live-20260925-compliance-e2-final/` 使用两个全新、相互隔离的合成身份，结果为 **PASS**：两边独立核对签名策略；无本机授权、仅单侧授权时均拒绝合规新收发；两端针对精确策略分别授权后，A→B 和 B→A 都产生收件人与网关两个密钥槽，并验证网关已解密准入的签名回执及 proof、收件端持久 inbox 与 ACK；普通 Agent v1 路径被拒，双方分别撤回本机授权后继续拒绝新合规收发。网关准入回执只证明平台解密并接纳原始密文，不证明收件 Agent 已 ACK、已读或业务完成。

同一最终测试使用两个一次性 Web 账户，逐账户执行披露确认前后的合成控制检查，`web-live-preclaim.json` 与 `web-live-postclaim.json` 均为 **PASS**；网页确认没有代替 Agent 的本机许可。另一次全新线上回合中，两侧均通过真实 Web→Hermes→MiniMax 模型链路完成精确挑战，结果 **PASS**，Web `5xx=0`。这些是合成账户和真实模型调用的机制测试，不代表两位真实用户曾作披露选择。各轮测试后的本地临时凭据与进程均清理，最终轮 `cleanup.json` 为 **PASS**。

另以两套**全新公开 v0.8.0 安装**执行线上合规联系人闭环，脱敏结果位于 `build/live-two-agent-acceptance/live-20260925-compliance-e2-contact/`，结果 **PASS**。两侧分别完成合成 Web 账户披露确认与连接认领、对端完整公钥固定和精确策略本机授权；Alice 从 Web `contacts.add` 发起，Bob 在本机 `contacts.requests` 收到请求并由合成身份明确接受，最终两边 `contacts.list` 均为 `connected`。随后双向发送消息并同步已读，各主人侧 8 轮，共 203 次 HTTPS 请求、0 次 Web 5xx，p95 为 782 毫秒、最大 1329 毫秒。测试用临时凭据与进程已撤销、移除；这只验证自动化机制，**不等于真人完成 T05 的好友与消息体验验收**。

另用独立的全新合成双 Agent/Web 身份验证拒绝分支，`build/live-two-agent-acceptance/live-20260925-compliance-e2-reject/contact-reject-result.json` 为 **PASS**：Bob 实际收到 Alice 的请求并明确拒绝，Alice 随后看到 `rejected`，Bob 未建立联系人连接；46 次 HTTPS 请求、0 次 Web 5xx。该轮的两端临时凭据与进程也已撤销、移除。接受与拒绝是两轮不同的请求和身份，没有把同一次请求写成两种结果。

线上合规 harness 的前两轮曾报告 **FAIL**，定位为测试脚本重启 helper 时遇到瞬时 `ConnectionResetError`。脚本加入有界重试后，以第三套全新身份重跑通过；前两轮失败不能抹去，也不将其误写成合规协议或产品门禁失败。脱敏测试结果在上述忽略提交的本机目录，身份私钥、临时凭据和原始私人日志不进入仓库。

本次记录没有真实用户公告送达、Web 确认或任一 Agent 本机合规授权的证据；需要本人参与的 T05、T06、T07、T10 仍按[测试步骤](../testing/TEST_EXECUTION_GUIDE.md)单独执行。另在本机隔离的合规 E2-V 栈，使用同一 Web 镜像、新签策略及独立数据库，预声明最多 12 路并发，实际 16 次写入与 160 次读取均为预期 HTTP 状态，Web SQLite `quick_check=ok`，未见数据库锁错误或容器重启；一次测试客户端在收到已提交写入的响应头后断开，原记录仍只有一条，重复提交为 409，随后 12 次读取正常。脱敏结果与清理记录在 `build/t21-compliance-isolated-20260925/`，测试容器、临时密钥及数据库已清除。此窗口**未覆盖双真实 helper 同时消费、外部 Push 投递或请求中途断线恢复**，因此 T21 整项仍只算部分通过。现网未来续签须签更高 epoch，并按[迁移指南](../operations/V2_MIGRATION.md)处理旧队列和重新授权，不能重放 epoch 1 策略或清库绕过严格门禁。
