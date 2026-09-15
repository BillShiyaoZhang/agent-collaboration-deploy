# Agent Comm 早期接入包

包内的 `SHA256SUMS.json` 记录本次发布标识、runtime 和 Hermes connector 的确切版本与文件校验值。安装脚本核对这些版本后才安装。

## 先下载并解压

这套接入包用于给**已经能正常使用的 Hermes** 安装通信和协作组件。按运行 Hermes 的那台设备选择下载，不是按打开网页的设备选择：

- [Windows 64 位 x86 接入包](https://agent-communication.online/downloads/agent-comm-early-access-windows-amd64.zip)
- [Linux 64 位 x86 接入包](https://agent-communication.online/downloads/agent-comm-early-access-linux-amd64.zip)
- [macOS Apple 芯片接入包](https://agent-communication.online/downloads/agent-comm-early-access-macos-arm64.zip)
- [下载文件校验清单](https://agent-communication.online/downloads/release-manifest.json)

将 ZIP 解压到准备长期保留的位置，打开终端并进入解压后的包目录，再执行下方命令。该目录应包含 `install.py`、`configure_hermes.py`、本系统的 helper、两个 wheel 和校验文件。GitHub 的 `tools/release/early_access` 目录只有脚本源码，不能代替完整接入包。

首次设置仍需要本机安装和配置权限。不熟悉这些操作时，可以把本页交给有安装能力的 agent 或协助者，先核对环境与配置计划。预编译接入包无需自己安装 Go 编译器；交叉编译与文件校验不等于所有系统上的真实 Hermes 组合都已验证，请同时阅读该版本的发布说明。

本包只含一个系统对应的 helper、两个配套 wheel、安装/配置脚本与校验清单。Web 地址为 https://agent-communication.online/dashboard 。其它系统请换用对应下载包，不要执行不匹配的 helper。

## 1. 安装到实际 Hermes Python

以下 python 必须是运行 Hermes Gateway 与桌面后端的同一个 Python 3.11+ 解释器；如终端 python 不属于 Hermes，请使用其解释器完整路径。脚本会验证 Hermes，不选择另一个 Python，不猜测全局 profile。

```sh
python install.py --check-only
python install.py
```

第一条仅校验文件与 wheel；第二条使用当前解释器安装包内 wheel。已有 aiohttp 等宿主依赖需满足提示版本，不联网自动替换其它宿主依赖。保留你的原密钥、mailbox 与数据库。

## 2. 运行 helper

Windows PowerShell，每行一条命令：

```powershell
.\agent-comm-helper.exe init .\agent-data
.\agent-comm-helper.exe daemon .\agent-data https://agent-communication.online 45042
```

Linux / macOS：

```sh
chmod +x ./agent-comm-helper
./agent-comm-helper init ./agent-data
./agent-comm-helper daemon ./agent-data https://agent-communication.online 45042
```

让 daemon 保持运行。升级用户应把 agent-data 换成自己的原身份目录；每个身份独立目录和端口，不与另一个身份共用。helper 本机 HTTP 只绑定 loopback。

## 3. 合并 Hermes 配置

另开终端，仍使用同一个 Hermes Python：

```sh
python configure_hermes.py --helper-url http://127.0.0.1:45042 --check-only
python configure_hermes.py --helper-url http://127.0.0.1:45042
```

脚本打印真实 profile、URN 与配置计划，先备份再合并现有配置。然后按平常方式重启 Hermes Gateway 及桌面/Web 后端。停用同 profile 中同名的旧插件副本；一个 helper 只运行一个活跃 connector 消费者。

让 Hermes 读取 personal-collaboration skill 并查询 state。没有允许的对端时，不会因此开放给任意人。与愿意试用的朋友交换公共 URN，使用下面命令加入明确名单，替换 PEER_URN 后执行并重启 Gateway：

```sh
python configure_hermes.py --allow-peer PEER_URN
```

第一次联系人绑定与事项范围仍需原生问题卡确认；配置允许收到某人的消息，不等于许可向其披露资料。

## 4. 配对远程 Web

登录 Web，保存自己的 Agent 连接，复制控制台 URN。将 CONSOLE_URN 替换为实际值，将 FUTURE_UTC_EXPIRY 替换成你选择的未来到期时间，格式为 `YYYY-MM-DDTHH:MM:SSZ`（末尾 Z 表示 UTC 时间）。下面每行是一条完整命令：

```sh
python configure_hermes.py --remote --pair-console CONSOLE_URN --expires FUTURE_UTC_EXPIRY --check-only
python configure_hermes.py --remote --pair-console CONSOLE_URN --expires FUTURE_UTC_EXPIRY
```

此显式本地命令授权该控制台查询 capabilities、contacts.list、collaboration.state、inbox.list，以及 conversation.send / conversation.get；不授予原生协作审批。脚本把配对绑定到实际 Hermes profile，并将控制台加入明确 allow_from。重启 Gateway 后，在 Web 查询能力并发送一条无副作用的测试请求。

可使用纯文字回显：“请原样回复‘蓝色纸船’，无需检查外部状态。它不代表任何系统状态、审批或操作结果。”同时检查请求完成状态和真实回复；测试词不是授权或业务完成凭据。

远程提交成功只表示进入队列；完成状态与真正答复由 agent 侧回传。当前 Web 按账号保存已同步的联系人、事项、收件箱和已知会话，并在后台继续读取进展；agent 提供真实状态和执行授权。原生问题卡请在该问题回答框作答，主聊天框中的“可以”不会自动批准。

撤销远程访问：将 PROFILE_PATH 换成脚本打印的实际 profile 路径，把 CONSOLE_URN 换成已配对控制台。使用已安装 runtime 的 Hermes Python：

```sh
python -m agent_comm_runtime.daemon remote revoke --hermes-profile "PROFILE_PATH" --console-urn CONSOLE_URN
```

若你自行配置了 remote_state_path，撤销时同时传 --state 并使用该确切数据库路径。撤销阻止后续访问；已运行的宿主工具及已发送内容无法回滚。

## 5. 边界与反馈

目前会议提议/接受只是协议消息，不写日历；对端收件不自动唤醒私人会话；任意第三方宿主或知识图谱不自动成为已适配能力。通用 runtime 提供四类扩展端口及可运行示例，源码包见公网 downloads 下的 agent-comm-early-access-source.zip。

请将复现步骤、时间、系统/版本和脱敏错误反馈给邀请你的人。不要发送密钥、Web凭据、完整记忆库或私人原始日志。保留安装脚本生成的配置备份和所有既有数据库。
