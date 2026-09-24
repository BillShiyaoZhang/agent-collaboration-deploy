# 2026-09-24 Agent Comm v0.8.0 客户端与官网下载发布

2026-09-24 发布 [GitHub Release v0.8.0](https://github.com/BillShiyaoZhang/agent-comm/releases/tag/v0.8.0)，并将四个平台的完整接入 ZIP 和源码 ZIP 更新到[官网发布清单](https://agent-communication.online/downloads/release-manifest.json)。本次接入包把 v2 策略根公钥与 Platform Peer ID 写入受校验的 `policy-trust.json`，安装到原有 helper 身份目录；新版 helper 启动前核对固定的可信锚，不能从 Platform 响应或 Web 配对临时取得根信任。两位 Agent 的完整 Ed25519 公钥仍须各自独立核对并固定。生产策略保持签名的 `private`、`allow_v1=true`、epoch 1：旧 helper 可暂走 v1，新 helper 的 v2 私密发送使用明确的 v2 路径；旧 v1 流量不因此获得 v2 保护，也未开启 `compliance` 平台解密。

| 对象 | 固定版本 |
| --- | --- |
| Deploy | `ddafa0992b0005e59b8854c6c5a24efe123518bf` |
| Platform | `1ccd85d59173980bd3ae3d006228dd9c3318d964` |
| Web 首发 / 提示修正 | `9cd8b93493a453a30ea2195835252a554547e2e2` / `7d23a8328e09ac5924420f46163ba8b8d60bd07b` |
| SDK / `v0.8.0` | `e609c2e17ffdc708f1628cb1956c598d1391e619` |
| Python 包 | runtime `0.1.4`，Hermes connector `1.5.6` |
| 首发生产镜像 | Platform `sha256:0372f06156656d4709b959a748d69aae0cf5d9058e161c7f82fdcdf8c743ad77`；Web `sha256:9058cf4f0f213fba92ee25e126eee5c559f901544ff0808c3fdc6ac9bafe5678` |
| 生产备份 | `/root/agent-comm-backups/2026-09-24-v2-public-v080-attempt2/`，仅服务器 root 可读 |

GitHub Release 含 16 项资产：四平台 helper、两个 wheel、四份安装 ZIP、源码 ZIP、文档 ZIP、下载脚本、两份 manifest 和 `SHA256SUMS`。官网清单与 GitHub 的 `early-access-manifest.json` 逐字节相同，SHA-256 为 `6d103efa7cb2de535ad405b29d57f61c1498271a2ab5343101a8e7e280b86ee8`。五份官网 ZIP 的 SHA-256 如下，完整资产清单见 [GitHub `release-manifest.json`](https://github.com/BillShiyaoZhang/agent-comm/releases/download/v0.8.0/release-manifest.json)：

| ZIP | SHA-256 |
| --- | --- |
| Windows amd64 | `d0679b96a431bae2404255cc68d1d559facaf4eed13ecc1965e4ba58da29b1b3` |
| Linux amd64 | `ed5230e8a44d6834f919e30761d88e90e98d8543ff969ae6f91586cf796ed7e2` |
| macOS Intel | `1ca4e9b30fcda865f9a8833ba48afb5ba3276095e399d0f5b7213330b76dcd1b` |
| macOS Apple Silicon | `6b22cd5045257517f0b3a5740c5dba9852787c8fb773b6ceeaec2952b6d1fd31` |
| 源码 | `9e83216292b66f1ef7766c6340587387b3e43d8bf9bc0848ef1c2b6ca367b6f6` |

GitHub Actions 的测试、构建和资产组装阶段通过；在依赖修复后，tag 上的发布 workflow 与 `main` 不同，Actions 的 `GITHUB_TOKEN` 创建 Release 返回 403。随后使用维护者凭据手动发布经本地校验的 16 项资产，并在上传后核对全部资产的 GitHub API digest 与长度；另独立下载两份 manifest、`SHA256SUMS` 和五份 ZIP，复核实际字节。因此本记录**不声称公开资产与 CI 构建字节完全相同**。官网五份 ZIP 经服务器本机同域 HTTPS 入口逐份下载核对，Windows 包另从外部公网 HTTPS 下载核对；四份接入 ZIP 的内部清单、`policy-trust.json`、对应 helper 和 wheel 与发布清单一致。固定策略根公钥 SHA-256 为 `9d133d88dadbfeca6db56e9ffa43060046d36ab3bde4547c79f52104e6a252cd`，策略信任文件 SHA-256 为 `9283ef7b8f683771628a53d2039aec5fea087e1f17488bded6dbc94a05b4be04`。

服务器升级前在线备份 Platform 三库与 Web 数据库并逐库运行 `quick_check`，保存非数据库数据、配置、旧镜像回退标签及旧官网下载包。切换后核对源码、运行镜像、既有 Platform Peer ID、签名策略、三容器运行状态和四库完整性；nginx 在 Platform/Web 重建后重新加载。官网五份 ZIP 和清单先在独立发布目录核验，再逐个替换，并最后替换清单；同域 HTTPS 下载的长度与 SHA-256 与 GitHub 发布资产一致。普通代码回滚应恢复旧镜像与配置而保留实时数据库，数据库备份只用于故障恢复。

在新服务端镜像上，用公开旧 r2 包做了双全新 Hermes、双 Web 用户兼容回归。第一轮已完成好友申请/接受和双向消息，但压力阶段遇到一次客户端 TLS 握手意外 EOF，整轮记为失败；此前 177 个有响应的 HTTP 请求没有 5xx，同期服务器无容器重启或相关错误日志，根因未确定。第二轮换全新环境后完成双方联系人、双向消息与已读、每侧 8 轮并发控制/工作台/同步；196 次 HTTP 请求无 5xx，p95 0.813 秒、最慢 1.734 秒，双方 Web 同步最终为 `ready`。两侧临时配对均已撤销，清理报告 `remaining=[]`。第二轮通过不解释第一轮 TLS EOF，也不等同于 v0.8.0 首装。

公开 v0.8.0 Windows ZIP 与全新首装所用 ZIP 的 SHA-256 完全一致。两套互相隔离的 Hermes 环境分别完成安装、Web 合成用户一次性授权和真实 MiniMax 模型回合；双方 Web 联系人申请与接受、双向消息和已读、各 8 轮并发均通过，211 次 HTTP 请求无 5xx，p95 为 0.859 秒，两边最终同步为 `ready`。同一批新身份还经双向完整身份公钥固定，分别完成 v2 私密投递、`accepted-uninspected` 签名回执验证、解密及各一次 ACK。首轮在**未固定对端公钥**时，`contacts.add` 返回 `requested` 但请求只在 Alice 本机持久队列中；固定双方公钥后，原请求使用同一个消息 ID 自动投递并送达 Bob，没有降级到 v1。Web 随后修正了“已发出”的误导性提示，明确本地排队和公钥核对前提。合成配对已撤销，临时进程、模型凭据、身份私钥与一次性链接均已清除。脱敏证据在本机忽略提交的 `build/live-two-agent-acceptance/live-20260924-v080-fresh/`，其中初始未固定公钥的失败与补齐后的通过分别保留，不能将第一次写成通过。

2026-09-25 凌晨部署上述 Web 提示修正时，第一次尝试在 1.8 GiB 内存的 ECS 上运行 Next.js 镜像构建，主机内存耗尽，内核杀掉 Docker 守护进程，三个容器均停止；构建端收到 Docker EOF。升级脚本已在切换前回退源码和镜像标签，但 Docker 被杀后容器不会自行恢复。维护者启动原 Platform、Web、nginx 容器并重载 nginx，确认原版 `/healthz` 和 `/login` 恢复。该次尝试记为**失败并恢复**，不能当作成功部署。

随后在本机 Docker Desktop 的 Linux/amd64 引擎上，从固定的 Web 提交 `7d23a83` 构建镜像 `sha256:4b7b6f9db64c6c9cc9c0e348d733c1b9bef441b69aa4f424e04bfe04cb5d991b`。压缩镜像 SHA-256 为 `5e9620aa41d3c465cc79d850f4882d43cf7d4edcf5a056b40fa7d2267df3e8a7`，上传前后校验值一致；服务器新备份位于 `/root/agent-comm-backups/2026-09-24-v080-web-offhost/`。服务器只加载已构建镜像、校验镜像 ID/架构/源码标签、重建 Web，随后重载 nginx；部署结果 `/root/agent-comm-releases/2026-09-24-v080-web-offhost/result.txt` 为 `exit_code=0`。最终服务器根提交为 `1c2cc4861d8be6b500e84c3e4b40e37f3e45a6cc`，Platform 镜像仍为首发镜像。线上验证了原策略字节、Peer ID/策略哈希与 `private` 模式、官网下载清单、修正后的 `/agent-install.md`、四库 `quick_check`、Web 无重启，以及独立公网 `/healthz`、`/login`、`/api/v2/policy` 均返回 200。服务器保留额外 swap 以承受镜像加载和日常内存波动；后续升级须监看磁盘和 swap，避免再次在这台小内存机器上在线构建 Web 镜像。

公开 Linux v0.8.0 ZIP 在服务器上的全新、只读且断网的 Linux 容器中，通过了 `install.py --check-only`、helper 初始化和向临时身份目录执行 `--pin-only`；这不是 Linux 原生 Hermes 全流程，macOS 仅有交叉构建与包校验。T05、T06、T07、T10 中需要两边用户亲自阅读、决定及评价体验的步骤，仍不能由 Codex 的合成账户确认代替。现行签名策略有效期到 **2026-10-24 13:43:31 UTC**；届时须按[迁移与续签说明](../operations/V2_MIGRATION.md)在到期前续签更高 epoch，并妥善处理旧 epoch 的待发、未读消息。
