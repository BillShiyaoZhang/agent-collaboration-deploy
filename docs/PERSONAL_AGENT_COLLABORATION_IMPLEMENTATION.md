# 个人 Agent 协作：当前实现与交接

更新：2026-09-14。早期试用版已发布；用户随后要求 Web 服务端持久保存账户数据并主动同步，本文同步记录该架构调整。本次持久化与后台同步的测试、上线仍在进行，不能用先前版本的验证替代。当前设计与源码关系见 [架构图](PROJECT_ARCHITECTURE_DIAGRAMS.md) 和 [扩展接口](ARCHITECTURE_AND_EXTENSION_PORTS.md)，早期公网及回滚记录见 [发布记录](EARLY_ACCESS_RELEASE_2026-09-14.md)。此前 1.2.0 的“所有内核都在 Hermes 包内”结构已被下述实现取代。

## 当前产品边界

Web 是连接用户 Agent 的远程工作台，保留登录账户、控制台身份、每用户连接记录，并按账户持久保存已认证返回的联系人、事项、消息和对话副本。业务内容使用 AES-GCM 静态加密；有限期 RPC 密文缓存与这些持久副本分开。业务事实和审批授权来自 agent，旧 Web domain 模型和模拟页面/API 继续退役；迁移保留旧表和数据，不在启动时清库。

Agent 侧有两个配套 Python 包：

- `agent-comm-runtime 0.1.0`：SDK 的 `python/agent_comm_runtime/`，无 Hermes 依赖，拥有通用策略/Store、四类端口、adapter registry、dispatcher、显式扩展加载、有限记忆快照、remote pairing/RPC/会话记录与本地 CLI。
- `hermes-platform-agent-comm 1.3.0`：SDK 的 `connectors/hermes-platform/`，提供真实 Hermes HostPort/InteractionPort、Gateway 生命周期与远程独立会话。旧 policy/store/transport import 仅保留兼容导出，运行同一份通用实现。

Go helper 继续拥有密钥、加解密与持久收发；云 platform 提供 Registry/MQ/Relay。可靠 helper 出站走 HTTPS MQ；不会把旧 P2P/DR 路径或平台 ACK 描述为业务完成。

## 已实现的协作能力

五种对外动作：share_slots、share_resource、propose_meeting、accept_meeting、send_text。策略严格检查参数和支持范围：收件人、参与人、资料快照、主题、时间段、时长、累计候选/动作数量与到期时间。自由文本逐次确认；未知能力与无效动作拒绝执行。

首次联系人绑定与委托建立经原生确认。资料登记不授予披露权，新增参会者不开放原资料。单次例外仅对应一个固定动作，不扩大整个委托。原生确认只接收 approval_id，租约留在宿主；会话、回合、版本与期限都要再次验证。

Hermes 当前使用原生问题卡回答框。主聊天中的裸“可以”、对端自称主人已同意、模型提交 approved=true 均不能替代确认。接口仍依赖已验证宿主版本的真实内部会话能力，升级后需要重验。

Store 持久保存联系人、资源、委托、方案、审批、操作、预算、入站与审计。稳定 operation_id/message_id 支持重试与跨对话恢复；执行前预占预算并重新检查权限。撤销停止后续动作，不能收回已被 helper 接受或已披露内容。

## 扩展端口

HostPort 取得和复查真实主体/会话/回合；MemoryPort 提供有界检索与指定资料快照；InteractionPort 取得可信确认，按声明可扩展通知；TransportPort 提供持久 store/retrieve/ack。

注册时检查版本、能力、必需方法与重复端口。未知能力明确 unsupported，不默认导出全部记忆或回退到模型自报授权。runtime 有可运行终端参考适配器，独立 pip 安装和离线运行已验证。用户自建知识图谱尚未编写具体 adapter；框架已提供实现和测试入口。

## 远程 Web 如何访问 Agent

Web 经 `agent-comm-control/v1` 协议和已有签名加密 MQ 通信。请求/响应绑定 request_id、双方 URN、方法和期限。HTTP 注册签名与正文 Registry 签名均有实际跨语言联调验证。

在 agent 侧通过 CLI 或接入脚本显式配对控制台 URN、主人主体、方法范围和到期时间。Hermes 还绑定真实 profile 主体，不能把另一个主体的配对拿来运行当前宿主。Web 保存连接本身不等于授权，同一 agent 可以由不同 Web 账户各自保存连接，实际访问由各自配对控制。

支持方法：capabilities、contacts.list、collaboration.state、inbox.list；Hermes 另支持 conversation.send/get。独立 daemon 只宣称具备其真实支持的方法。conversation.send 仅提交工作，真实 Hermes Gateway 会话在 agent 侧执行，最终文本和状态保存到远程会话库，由 get 查询。发生不确定的进程中断时标记 interrupted，不自动重放可能已有副作用的工具。

远程审批暂不开放。开启 collaboration 或 remote 模式后，普通对端 wire 只进入声明记录，不自动启动有私人权限的 Gateway LLM；只有配对且有范围的 remote conversation 请求可以进入远程会话。原生 inbox 不抢占 control 请求；消息处理保留稳定 ID、先持久化后 ACK，并避免无关消息前缀永久堵塞有效控制响应。

远程配对撤销与响应提交按本地事务顺序处理；撤销阻止后续 RPC、agent 侧尚未提交给 helper 的缓存响应和未执行会话。已经返回 Web 的持久副本、短期缓存及已披露内容无法召回，已经运行的宿主工具不能回滚。Web 的 10 分钟期限只适用于 RPC 投递缓存，不适用于已同步的历史。Web 后端是托管控制台身份端点，会解密获准内容并加密保存；云 MQ 保存签名密文及路由元数据。

## 账户持久化与主动同步

联系人保存最后一次完整视图，收件箱消息和会话回合按稳定 ID 累积更新。服务端同时记录已知会话列表、当前会话及未确认发送的原始请求，刷新、重新登录或换设备后可恢复。浏览器先显示服务端副本，再后台更新；断线时保留最后同步内容，明确显示同步时间和当前状态。

常驻 Node worker 由 Next.js instrumentation 启动，不依赖用户打开标签或点击刷新。它先查询 capabilities，再按权限优先读取 collaboration.state 并派生联系人与收件箱视图，必要时回退到独立读取方法；会话同步覆盖当前及含待完成回合的已知会话。调度包含去重、租约和错误退避，避免重复请求与持续冲击离线 agent。

定时工作仅调用读取方法，不发送 conversation.send、不批准事项、不重放结果不确定的写请求。agent 侧配对范围和期限继续决定访问权，历史数据不能作为在线或授权证明。删除 Web 连接会级联删除此账户在该连接下的副本，agent 本地数据保持独立。

本轮不修改 SDK 协议。没有 conversation.list，不能自动发现 Web 未记录 ID 的旧会话；conversation.get 和 inbox.list 只返回最近 100 项，也没有历史分页。持久库保留实际同步到的数据，不承诺补齐这些窗口之外的历史。

## 安装与开发入口

早期用户使用配套下载包，包含对应系统 helper、两个 wheel、install.py、configure_hermes.py、README 与 SHA256SUMS.json。源码接入时先安装 SDK/python，再安装 SDK/connectors/hermes-platform。不要只安装旧包或调用已移除的统一安装 CLI。

接入脚本必须由实际 Hermes Python 运行，识别真实 profile；配置前备份并合并既有设置。helper URL 是 loopback，云 URL 只用于 helper daemon；明确 --pair-console 和期限才授予远程访问。单独 --remote 不自动信任控制台。保留旧密钥、mailbox、receipts、协作库和远程配对库。

开发者从 [runtime README](../agent-comm-platform/agent-comm/python/README.md) 开始。其它宿主需要实现和验证自己的端口，现有 OpenClaw 基础 connector 不因这次抽取就自动具备全部新协作能力。

## 早期试用版验证记录

以下是持久化与后台同步改动之前的验证记录；本次改动需另行完成迁移、账户隔离、进程恢复及后台同步验证。

- 通用 runtime/remote：39 项通过。
- Hermes 原生、connector 与 remote lifecycle：109 项通过。
- Web：54 项通过，TypeScript 与 production build 通过（包含登录回跳地址校验）。
- 接入脚本：12 项临时环境测试通过，不修改用户真实 profile。
- 真实本地 Go helper/platform：认证收发、离线队列、强制重启恢复、ACK 与稳定 ID 检查通过。
- 真实本地 remote network：agent 侧联系人、控制请求隔离、响应恢复、方法范围与撤销通过。
- 完整 Web + Go + Python：真实注册/登录、控制台身份、双签名 Registry、MQ 加密往返、agent 侧事实返回与撤销检查通过。

可复用入口：[remote 网络测试](../tools/test_remote_control_network.py)、[Web 全栈 smoke](../agent-collaboration-web/tests/full_stack_smoke.py)、[helper/platform 测试](../agent-comm-platform/agent-comm/tools/test_helper_platform.py)。临时数据和日志位于各自 build 目录；未把本地模拟 handler 宣称为真实模型推理测试。

最终 wheel 必须重建并与源文件逐一核对，尤其新增 identity.py 和 remote/platform 修复。打包脚本 [build_early_access.py](../tools/build_early_access.py) 会执行该检查及每个 OS 包的 install --check-only。Windows helper 已运行验证，Linux/macOS 是交叉编译产物，对应 Hermes 宿主仍需首批试用确认。

## 清理及发布约定

移除根目录退役 connector/CLI、SDK 旧统一安装 CLI、旧绑定/消息脚本、Web 独立业务 API/页面和浏览器 demo。历史探索文档标为决策记录；当前入口不再引用旧安装方法。用户数据库和已有部署数据不属于废弃代码，不删除。

用户明确授权新版 Web 部署到现有域名。发布采用先构建、备份数据及旧镜像、校验迁移、切换后检查的流程；具体公网发布证据与回滚位置记录在本轮发布记录。初次部署及公开安装包来自已校验源码快照，安装包附校验清单；本次 Git 发布同步固定两级子模块提交。后续发布也必须先提交并推送 SDK/Web，再更新 platform/deploy 引用。
