# Hermes 源码接入与升级

Platform 从隐私模式切换到合规模式时，先按 [v2 迁移步骤](V2_MIGRATION.md)安排用户告知、独立密钥核对、本机披露授权与旧队列处理；普通 Hermes 升级不自动表示同意披露。

首次使用预编译包请直接阅读 [接入包说明](../../tools/release/early_access/README.md)。本文用于维护固定版本源码安装；需要已能正常运行的 Hermes、Go 1.25.7+，以及 Hermes 使用的 Python 3.11+ 环境。

Compose 运行云端 Web、Platform 和 nginx。Go helper 与 Hermes Gateway 在同一设备运行：helper 连接云端 HTTPS，Hermes 插件连接本机 loopback helper。

## 1. 从固定源码构建 helper

在 Hermes 所在设备递归检出本仓库，见 [源码准备](DEPLOYMENT.md#准备源码与环境)。以下 shell 命令从部署根目录运行：

```bash
DEPLOY_DIR="$(pwd)"
mkdir -p "$DEPLOY_DIR/build"
(
  cd "$DEPLOY_DIR/agent-comm-platform/agent-comm"
  go build -o "$DEPLOY_DIR/build/agent-comm-helper" ./cmd/helper
)
"$DEPLOY_DIR/build/agent-comm-helper" init /absolute/path/to/hermes-agent-keys
```

将身份路径替换为实际路径；升级时使用原身份目录和原 `mailbox.db`。当前 v2 helper 启动前，必须从平台之外核对策略根 Ed25519 **公钥**与预期 Platform Peer ID，再对该身份固定；不能从未认证的 bootstrap 响应直接采信。预编译 v2 接入包由[发布者核对并随包固定](../../tools/release/README.md#接入包与开发源码)，源码安装则显式执行：

```bash
"$DEPLOY_DIR/build/agent-comm-helper" v2-pin-policy-root /absolute/path/to/hermes-agent-keys ROOT_PUBLIC_KEY_64_LOWERCASE_HEX EXPECTED_PLATFORM_PEER_ID "independent verification source and date"
"$DEPLOY_DIR/build/agent-comm-helper" daemon /absolute/path/to/hermes-agent-keys https://agent-communication.online 45042
```

现网签名策略为 `compliance, allow_v1=false`；新 v2 helper 在主人未针对已验签策略授权时会停止普通 Agent 间合规收发，旧 v1 Agent 间路径也被拒。按[策略迁移](V2_MIGRATION.md)完成核对与授权，不以替换身份或降级旧 v1 绕过。daemon 前台运行，持久服务配置见 [SDK 服务说明](../../agent-comm-platform/agent-comm/README.md)。每个 helper 身份有独立数据目录和本机端口，服务的 `ExecStart` / `ProgramArguments` 使用本次 helper 的绝对路径。

## 2. 安装 runtime 与 Hermes 插件

另开终端，使用 **运行 Hermes Gateway 的同一个 Python 环境**：

```bash
python -m pip install /absolute/path/to/agent-collaboration-deploy/agent-comm-platform/agent-comm/python /absolute/path/to/agent-collaboration-deploy/agent-comm-platform/agent-comm/connectors/hermes-platform
python -c "from hermes_constants import get_hermes_home; print(get_hermes_home())"
curl --fail http://127.0.0.1:45042/info
```

两个包分别提供通用协作内核和 Hermes 宿主适配。源码契约见 [runtime README](../../agent-comm-platform/agent-comm/python/README.md) 与 [Hermes connector README](../../agent-comm-platform/agent-comm/connectors/hermes-platform/README.md)。其他宿主需实现实际适配器；SDK 内的 OpenClaw 基础 connector 不自动获得 Hermes 的完整个人协作能力。

## 3. 配置实际 profile

按 connector README 合并 `plugins.enabled: [agent_comm]` 与 `platforms.agent_comm.extra`，保留原有插件和配置。关键字段：

| 字段 | 来源 |
| --- | --- |
| `platform_url` | 本机 helper，如 `http://127.0.0.1:45042` |
| `urn` | helper `/info` 返回的真实身份 |
| `allow_from` | 明确允许的对端 URN |
| `remote_enabled` | 要使用工作台时显式启用，之后还需本机配对 |

云端 `https://agent-communication.online` 用于 helper 的 daemon 参数；Hermes 插件使用 loopback 地址，不使用 Platform 管理令牌。

可使用本仓库 [configure_hermes.py](../../tools/release/early_access/configure_hermes.py) 读取实际 profile、预览计划并备份合并设置。完整参数、远程配对、期限与撤销命令见 [配套安装说明](../../tools/release/early_access/README.md#4-配对远程-web)。单独开启 remote 或在 Web 保存连接不会授予控制台访问权。

## 4. 升级和重复插件清理

当前安装来源是 SDK 的 `python/` 和 `connectors/hermes-platform/`。根部署仓库旧 connector、旧统一安装 CLI 和浏览器 Demo 已退役。

升级前备份 helper 密钥、mailbox、connector receipts、协作状态库、远程配对/会话库及实际 profile 配置。先定位真实 profile 中同名的旧插件副本，再停用它并安装当前 SDK 版本；不得删除身份或状态库来解决重复安装。一个 helper inbox 只运行一个活跃 connector/standalone 消费者。

通过日常服务管理器正常重启 Gateway，检查 helper `/info`、Gateway 日志中的 SSE 连接及新安装路径。Hermes 使用内部宿主会话能力，升级 Hermes 后需重新验证原生确认和远程会话。

## 5. 配对与验证

工作台控制台身份必须在 agent 本机配对，并绑定真实 profile 主体、明确方法和期限。当前可用读取方法包括 `capabilities`、`contacts.list`、`contacts.requests`、`collaboration.state`、`inbox.list`、`attention.list`；Hermes 另提供 `conversation.send` / `conversation.get`。显式配对相应写方法后，用户可在 Web 添加或回应联系人、发送消息、同步已读、回答具体审批；结果保存在 agent 并同步，远程聊天中的同意文本不构成审批。

旧配对需本人显式更新，安装或启用远程模式不会自动增权。使用配置脚本时，先查看 `--remote --pair-console CONSOLE_URN --expires FUTURE_UTC_EXPIRY --allow-web-actions --check-only` 的完整计划，再移除 `--check-only` 执行；如使用 runtime CLI，则逐项 `--allow` 保留全部需要的方法并加入新增项。详见[接入包配对说明](../../tools/release/early_access/README.md#4-配对远程-web)。这些功能需要匹配的 Agent/runtime、Web 和本机权限；下载安装包时核对公开清单。companion 的桌面提醒步骤见[connector 提醒说明](../../agent-comm-platform/agent-comm/connectors/hermes-platform/README.md#协作待办与纯提醒-companionn1)。

发送一个不调用工具的纯文字回显，核对请求最终完成状态、真实回复和后台同步结果。“已受理”只表示提交成功；消息 ACK 不表示业务完成。重试结果不确定的发送应保留同一个请求 ID，先检查既有会话。

各次真实 Hermes 验证及其环境、版本和限制见[验证记录](../verification/README.md)。Git 提交并不自动更新公开安装包。
