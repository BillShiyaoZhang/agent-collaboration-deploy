# Hermes 官网自动接入 · 2026-09-18

官网完整接入包更新为 **`2026-09-18-onboarding-r2`**。已有可运行 Hermes 的用户可以只发送“安装并配置：https://agent-communication.online”，由 Hermes 自行下载、安装并启动本机组件。网页操作者打开 Hermes 提供的一次性链接，核对 agent、权限和期限后确认；Hermes 在后台接收签名授权、完成本机配对并启动 Gateway，无需把控制台 URN 或配对命令再交回 Hermes。

本次实机安装与配对记录、真实模型回复及最终验收结论见 [Hermes 自动接入验收](../verification/HERMES_AUTONOMOUS_ONBOARDING_2026-09-18.md)。本发布记录描述分发内容与接入机制，不以安装完成代替真实回复验收。

## 固定版本与公开产物

| 仓库 | r2 安装包与源码 ZIP 固定提交 |
| --- | --- |
| Deploy | `cb0909d975e0b6e52ba9dd949fcc2753e0aaaa7b` |
| Web | `739136e422c8dab516b661740a454a50db079929` |
| Platform | `2ed906d28f27d76cbdcf463b4031d364aae63486` |
| SDK | `ecf829dc31099ea889abf2633cbe47afd522eab5` |

runtime 保持 **0.1.4**，Hermes connector 保持 **1.5.5**，helper 与两份 wheel 继续使用已验证的 v0.7.0 内容。本次变更是安装与配置脚本、公开指南、Web 接入 API/UI 和增量迁移。四个平台完整 ZIP 均包含新的 `onboard_hermes.py`：Windows amd64、Linux amd64、macOS Intel amd64、macOS Apple Silicon arm64；源码 ZIP 同步更新。GitHub v0.7.0 Release 未覆盖，官网新版安装脚本以本次清单为准。

[官网清单](https://agent-communication.online/downloads/release-manifest.json)的 SHA-256 为 `df79f6a8e6ad7981706370a4e492aa5f31403ce1381f2ee90e766b0174364d23`。本次实机使用的 macOS arm64 ZIP SHA-256 为 `6d420ffb889728e8dab1f74cd7cb4f0aa975123ab94ae3811f6e81b43f12a8d1`。公开下载与包内文件校验结果保存在发布证据目录。后续仅修改索引和验收记录的提交不改变这些产物所含的源码。

## 官网自动连接流程

1. 官网 HTML 靠前提供同域 [安装指南](https://agent-communication.online/agent-install.md) 和 [`llms.txt`](https://agent-communication.online/llms.txt)。公开 README、完整包 README 与安装器后续提示一致指向 `python3 onboard_hermes.py`，避免 agent 继续进入旧的手动命令传递流程。
2. 安装入口识别实际运行 Hermes 的 Python 和 profile，校验配套组件并安装；兼容没有 pip 的 uv 环境。它保留已有配置、身份与数据库，启动本机 loopback helper。macOS 使用 profile 专属 launchd 服务维持后台运行。
3. 本机 agent 注册身份并签名创建连接申请。公开 claim code 与仅存本机的轮询 secret 分离，服务端只保存 secret 哈希；申请有效期为 30 分钟。
4. 已登录网页账户查看具体 agent、方法和到期时间后确认。控制台签名的 grant 绑定原申请、agent、控制台、方法和期限；Hermes 完整验签后才写入本机授权。默认七天工作台读取与 Hermes 对话，不包含联系人写入、好友消息和协作执行权限。
5. 后台程序自动完成配对、启动 Gateway 并检查真实连接，随后提交可重试的完成回执。已批准申请额外保留 30 分钟回执宽限；短暂断网或回执丢失可恢复，撤销和过期的配对不会被重跑自动恢复。

旧手动 `configure_hermes.py --remote --pair-console ...` 路线仍供已有身份的管理员使用。新增权限必须明确请求并在网页审阅确认；安装、服务器更新和包升级不会自动扩大旧授权。

## 部署与记录

Web 新增 `OnboardingTicket` 表，通过现有增量迁移创建，保留既有账户、连接和业务数据。`/api/onboarding` 与带 secret 的轮询接口支持 agent 接入；claim API 和确认页面仍需登录，确认操作检查同源。公开安装指南由 Web 镜像提供，首页由挂载的静态目录提供，发布时需与新安装 ZIP 和下载清单一起更新。

- 服务器发布目录：`/root/agent-comm-releases/agent-comm-onboarding-2026-09-18`。
- 服务器备份目录：`/root/agent-comm-backups/agent-comm-onboarding-2026-09-18`。
- Web 构建标签：`agent-comm-web:onboarding-20260918`；切换前镜像保留为 `agent-comm-web:before-onboarding-20260918`。
- 本地证据：忽略目录 `build/releases/agent-comm-onboarding-2026-09-18/`，其中 `public-verification-r2.json` 与 `website-downloads-r2/release-manifest.json` 记录最终 r2 校验结果。

回退时按备份记录恢复配套的 Web 镜像、静态首页、公开指南与下载文件，最后恢复下载清单。保留实时数据库、账户加密密钥及原身份，不用历史数据库覆盖发布后的用户写入。新增安装脚本的本机身份和服务属于用户设备，服务器回退不会自动卸载它们。
