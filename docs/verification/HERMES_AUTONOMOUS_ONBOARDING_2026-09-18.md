# Hermes 仅凭官网地址自动接入验收 · 2026-09-18

**结论：真实端到端验收通过。** 全新 Hermes 配置 MiniMax China Token Plan 后，只收到一次安装指令；它自行下载安装包、安装组件并发起连接。操作者在已登录的 Web 账号中确认后，本机自动配对并启动 Gateway。随后从 Web 发送消息，Hermes 返回真实模型回复，网页显示“本回合已完成”。

## 验收边界

- 实机：macOS Apple Silicon，Hermes 官方安装器，Python 3.11.14。
- Hermes 源码：`64ea66b03d44ead9ffea48161132e5deca5d255a`。
- 模型：`minimax-cn` / `MiniMax-M2.7`，China Anthropic-compatible endpoint。
- API key 仅保存在本机权限为 `0600` 的 `.env`，不进入代码、安装包或本文。
- 操作者负责清理、重装 Hermes、配置用户指定的模型，以及 Web 账号侧授权和发送验收消息。
- Agent 侧安装从以下唯一用户消息开始；此后没有追加提示、代为执行安装/配对命令、手工重启 Gateway 或修改运行配置：

```text
安装并配置：https://agent-communication.online
```

## 修复前后对照

| 轮次 | 结果 | 发现与处理 |
| --- | --- | --- |
| 原流程，86 次工具调用 | 未通过 | Hermes 自行安装并启动组件，但要求人工提供控制台 URN 并执行本机配对命令。 |
| 首次自动接入包复测，50 次工具调用 | 未通过 | Hermes 通过搜索读取到尚未更新的 GitHub 指南，并沿用安装器输出的手动配对提示。将 GitHub 主分支、官网说明和安装器下一步提示统一到自动入口。 |
| 最终全新环境，35 次工具调用 | 通过 | Hermes 自主执行自动入口，生成申请；Web 确认后自动完成连接，真实消息回复成功。 |

首轮按要求删除了旧 Hermes、旧集成身份和旧服务。后续失败测试环境在停止进程后完整移入私人备份目录，再从空的 `~/.hermes` 重装，避免反复销毁数据。最终启动前检查：runtime、connector、onboarding 状态、Gateway PID、agent-comm 配置、聊天历史均不存在。

## 最终实机记录

以下时间均为 Asia/Shanghai，日期 2026-09-18。

1. 安装会话 `20260918_013418_489d85` 使用 `MiniMax-M2.7`。只读查询 Hermes 会话数据库，确认该会话恰有一条用户消息，原文严格等于上述指令。Hermes 自行读取官网指南与 `llms.txt`，下载并校验 ZIP，找到实际 Hermes Python，再执行包内 `onboard_hermes.py`。
2. 安装回合约 190 秒，退出码 `0`，共产生 35 次工具调用。它输出 Web 申请链接；安装对话已经结束，后台 worker 继续等待授权。
3. 在已登录 Web 账号中核对签名 Agent 身份、七天权限和到期时间，然后点击“授权并连接这个 Hermes”。没有复制控制台 URN、公钥或本机命令。
4. 01:39:22，本机状态变为 `connected`，`local_pair_installed=true`、`web_ack_pending=false`；Gateway 进程存活，`agent_comm` 平台状态为 `connected`。日志记录自动创建 Gateway 服务并启动。网页显示“Hermes 已完成本机配对”，工作台显示“已同步”。
5. 01:40，从 Web 发送下列消息，页面显示“本回合已完成”，回复内容完全匹配：

| 方向 | 内容 |
| --- | --- |
| Web → Hermes | 请做纯文字回显：只回复“蓝色纸船-7Q4M”，不要调用工具。 |
| Hermes → Web | 蓝色纸船-7Q4M |

独立只读检查本机模型记录：回复会话为 `20260918_014021_97f61e9a`，provider 为 `minimax-cn`，模型为 `MiniMax-M2.7`；实际 API 调用一次、工具调用零次，耗时约 3.215 秒。模型请求 ID 为 `06fb5906a8fc64251ce53cbc28be0539`。对应远程回合 `turn-afa087b4c61f14bab45bb3f992422d97ad33a49c` 状态为 `completed`，与 Hermes 用户消息的 `platform_message_id` 一致，回复精确匹配上述标记。

验收连接的 Agent URN 为 `urn:agent-comm:agent:5E8LWa9iMBnBFYkf7krbbd`，工作台 ID 为 `cmu5tdoqf0003l2d3z5mr3wfv`。会话已保存到账号，可在 [Hermes 工作台](https://agent-communication.online/dashboard/agents/cmu5tdoqf0003l2d3z5mr3wfv) 查看。后台服务保留运行。

Hermes 的安装结束语仍提出“完成后告诉我，我再验证”，但本次没有发送该追加消息；后台已独立完成配对、启动与回执，真实 Web 回复证明不依赖再次唤醒安装对话。

## 修复内容

1. 完整接入包新增 `onboard_hermes.py`，识别真实 Hermes Python/profile；没有 pip 的 uv 环境也能安装配套 wheel。
2. 自动初始化独立身份、签名注册并持久运行 helper；macOS 使用 profile 专属 launchd 服务。
3. Agent 签名发起短期申请；Web 登录用户确认 Agent、权限范围与期限。轮询 secret 留在本机，Web 仅存哈希。
4. Agent 校验 Web grant 的签名、控制台身份、原始申请、方法和期限，自动保存配对并启动 Gateway。只有检测到真实存活进程与 `agent_comm` 已连接后，才向 Web 回执。
5. 短暂断网、Gateway 启动失败和回执丢失可重试；撤销或过期授权不能通过重跑恢复。
6. 官网 `/agent-install.md`、`/llms.txt`、首页入口、GitHub 指南及安装器提示统一到自动流程。已有手动管理的身份继续保留原路线。

默认授权七天的工作台读取和 Hermes 对话。本次未授予联系人写入、好友消息发送或协作审批权限。

## 自动检查

| 范围 | 结果 |
| --- | --- |
| 安装、生命周期、签名与撤销回归 | 33 项通过 |
| 发布、完整包和源码校验 | 5 项通过 |
| Web、真实 SQLite、签名与客户端契约 | 173 项通过 |
| Hermes connector / 当前官方 Hermes | 142 项通过 |
| Desktop companion | 55 项通过 |
| Web 生产构建 | 本地和服务器均通过 |

四个平台的安装 ZIP 均已构建并验证内部文件校验。**真实模型端到端验收范围为本次 macOS ARM64**；其他平台不据此声称已完成实机验收。

## 发布与证据

- 当前官网包：`2026-09-18-onboarding-r2`。
- 包内 Deploy 提交：`cb0909d975e0b6e52ba9dd949fcc2753e0aaaa7b`。
- Web 提交：`739136e422c8dab516b661740a454a50db079929`。
- 运行的 Web 镜像：`sha256:bf4d40418a55bb3ab72e947df4fde46b9dbab46e094820fbcdf4832c2d5c3754`。
- 官网 manifest SHA-256：`df79f6a8e6ad7981706370a4e492aa5f31403ce1381f2ee90e766b0174364d23`。
- macOS ARM64 ZIP SHA-256：`6d420ffb889728e8dab1f74cd7cb4f0aa975123ab94ae3811f6e81b43f12a8d1`。
- runtime `0.1.4`、connector `1.5.5` 和 helper 二进制沿用匹配的 v0.7.0 内容；本次改变安装脚本与 Web，不覆盖旧 GitHub Release。
- 本地脱敏证据：`build/releases/agent-comm-onboarding-2026-09-18/`，包含空环境检查、公开下载校验、各轮摘要及构建记录。该目录不纳入版本管理。
- 原始模型日志保留在本机 `/tmp/hermes-agent-comm-success.jsonl`，不提交到仓库。
- 服务器发布暂存：`/root/agent-comm-releases/agent-comm-onboarding-2026-09-18`。
- 服务器回滚备份：`/root/agent-comm-backups/agent-comm-onboarding-2026-09-18`，包含原 Web 镜像标记、一致性 SQLite 备份、静态站点、下载文件及服务器本地环境文件。

安装包已从公网重新下载验证，GitHub 原始指南也已确认是新流程。Web 和部署仓库的实现提交均已推送主分支。
