# Agent 侧为中心的产品边界与扩展接口

维护基准：2026-09-15 的固定源码。Web 已实现账户范围的加密持久副本与后台同步；agent 提供业务事实、执行和配对授权。本文是跨仓库架构入口，操作见 [部署指南](../operations/DEPLOYMENT.md) 与 [Hermes 指南](../operations/HERMES.md)，流程见 [架构图](FLOWS.md)，各次上线证据见 [发布记录](../releases/README.md)。

## 产品归属

| 部件 | 拥有的事实 / 职责 | 不承担的职责 |
|---|---|---|
| 用户自己的 agent | 推理、任务理解、原有私人记忆及工具 | 不自行宣称已取得新的用户授权 |
| agent-comm-runtime | 本地联系人、资料快照、委托、方案、审批、操作、审计；版本化适配接口 | 不统一用户全部记忆，不执行未知能力 |
| Hermes connector | 将真实宿主会话、确认 callback 与 Gateway 生命周期接到 runtime | 不复制策略内核，不将普通远端消息变成主人身份 |
| Go helper / SDK | 网络身份、签名、加解密、本机持久 inbox/outbox | 不根据消息正文决定主人授权 |
| Go platform | Registry、MQ、Relay、基础设施管理 | 不维护个人协作委托或通讯录别名 |
| Web 工作台 | Web 登录、控制台身份、账户连接、已认证数据的加密持久副本、会话恢复、主动同步；独立的有限期 RPC 密文缓存 | 不自行授予 agent 权限，不定时发送会话或代替原生审批，不生成模拟业务结果 |
| 官网静态页面（Web 仓库 `site/`） | 产品介绍、项目关系、接入引导；由 nginx 在 `/` 直接提供 | 不依赖 Platform 或 Next.js 进程，不处理登录和业务操作 |

Web 中添加 agent 只是连接记录。真正的远程访问权由 agent 侧配对赋予，绑定控制台 URN、明确方法范围、主人主体和到期时间。即使有人知道 agent 的 URN，也不能因此查询其联系人或任务。

## 运行结构与边界

扩展接口指代码合约，不是新增暴露在公网的 TCP 端口。默认继续使用本机 loopback helper 与云端 HTTPS MQ；不能让网页跨源直接写本机信任配置。

## 四类扩展端口

通用包位于 `agent-comm-platform/agent-comm/python/agent_comm_runtime/`，可独立安装，无 Hermes 依赖。`ports.py` 定义接口，`AdapterRegistry` 实际检查并注册适配器，`Runtime.dispatch` 使用它们执行能力。

| 端口 | 必需 / 可选方法 | 适配者负责证明什么 |
|---|---|---|
| HostPort | `capture`、`revalidate`；可选 `wake` | 主体、会话、当前回合确实来自宿主；中断或归属改变后不能沿用权限 |
| MemoryPort | 按声明实现 `search`、`read_snapshot` | 查询范围、来源与版本；返回有限快照，遵守原记忆系统访问规则 |
| InteractionPort | 按声明实现 `request_confirmation`、`notify` | 回答来自对应用户交互渠道；模型或对端不能提交自己的同意凭据 |
| TransportPort | `store`、`retrieve`、`ack` | 持久接受、稳定 ID、已验证来源、明确 ACK 和超时语义 |

每个适配器声明 `Descriptor(name, port, capabilities, api_version='1.0')`。未知版本、未知能力、缺失实现或重复端口会被拒绝。未配置的能力返回 `unsupported`；不偷偷回退到自由文本授权、全量记忆导出或任意网络请求。

`HostSession` 保存宿主生成的 `principal_id`、`session_id`、`turn_id` 和仅供宿主使用的 opaque 对象。模型参数和远端 JSON 均不能提供这个可信上下文。长期主体与临时会话分开，既支持同一主体跨对话恢复，也能把确认绑定到当前回合。

`MemorySnapshot` 包含 reference、title、text、source、version。记忆查询结果不自动成为通讯录绑定，资料快照也不自动获得披露许可。接入知识图谱时，适配者可将图谱实体映射到候选联系人，但最终稳定 contact_id → URN 的绑定仍须独立确认。

## 当前协作能力

通用 runtime 的 [策略实现](../../agent-comm-platform/agent-comm/python/agent_comm_runtime/policy.py) 支持五种对外动作：

| 动作 | 执行边界 |
| --- | --- |
| `share_slots` | 发送委托范围内的候选空档，检查时间范围和累计数量 |
| `share_resource` | 发送获准资料的固定快照，检查收件人和资料版本 |
| `propose_meeting` / `accept_meeting` | 交换绑定参与人、时间和版本的方案消息；不写入日历 |
| `send_text` | 逐次确认确切自由文本 |

首次联系人绑定、委托和需追加确认的动作经可信交互渠道处理。Store 持久保存联系人、资料、委托、方案、审批、操作、预算和审计；执行前重新检查授权并预占预算，稳定 operation_id/message_id 支持重试和恢复。新增参会者不获得原资料权限，单次例外不扩大整个委托；已被 helper 接受或已披露的内容不能召回。

Hermes 的 Host/Interaction 适配器已提供真实宿主会话和原生确认。其他宿主、知识图谱及交互渠道需要实现并验证自己的适配器。当前支持范围不包含对端来信自动唤醒私人模型、远程代批、日历写入和全量私人记忆同步。

## 授权渠道

Hermes 当前实现仍使用原生问题卡 callback。其它渠道可以实现自己的适配器；实现代码须可信安装并验证真实渠道身份，不能仅写一个返回“同意”的函数就声称完成授权集成。通知和主动唤醒已有注册与调用接口，但未因此启用后台私人会话自动协商。

## Web 远程协议

协议名 `agent-comm-control/v1`。请求通过已有签名加密消息传输，严格绑定 request_id、agent_urn、console_urn、method、params 与 deadline。响应绑定同一组身份及请求字段，携带 result 或 error；Web 必须验证真实 agent 发来的响应才展示成功。

Agent 侧 RemoteBridge 使用本地配对与持久请求记录：

1. 根据 helper 验证过的 sender_urn 查找有效配对。
2. 核对请求目标、控制台身份、期限和方法范围。
3. 用稳定请求 ID 与内容指纹去重；同 ID 不允许替换请求内容。
4. 从 agent 侧读取事实或提交真实会话工作；保存结果后通过 helper 回传。
5. 返回消息被 helper 接受后再 ACK 原请求；故障重试保留原响应。

当前方法为 `capabilities`、`contacts.list`、`collaboration.state`、`inbox.list`、以及 Hermes 实现的 `conversation.send` / `conversation.get`。独立只读 daemon 不宣称具备 Hermes 会话能力。`conversation.send` 返回 submitted 仅代表已提交，最终结果由 conversation.get 从 agent 侧读取。

远程审批当前不开放。Web 可以查看 agent 侧的待确认状态，原生审批仍回到已实现的用户交互渠道。后续渠道适配要补充身份验证、问题呈现、回答绑定、期限与撤销测试，才能声明支持。

## Web 持久副本与主动同步

Web 按登录账户和连接保存已认证读取结果，内容使用 AES-GCM 静态加密。联系人保留最后一次完整视图，收件箱消息和会话回合按稳定 ID 累积、更新；新窗口中缺少旧消息不表示历史已被删除。已知会话列表、当前会话以及未确认发送的原始请求也保存在服务端，使刷新页面或换设备后能够继续查看和核实。

浏览器先读取账户的服务端副本，再在后台刷新。常驻 Node worker 由 Next.js instrumentation 启动，独立于页面点击持续同步：先读取 `capabilities`，在权限允许时优先使用 `collaboration.state` 同时更新事项、联系人和收件箱；缺少该方法时使用已授权的独立读取方法，再查询当前会话和有未完成回合的已知会话。调度使用去重、租约和失败退避，避免多个页面或进程重复请求。后台只调用明确的读取方法，不定时调用 `conversation.send` 或审批方法，也不自动重放结果不确定的发送。

`ControlRequest` 仍是独立的加密信封投递缓存，请求期限为 120 秒，缓存可读取期限为 10 分钟。持久工作台副本不随该缓存到期而删除；过期缓存清理也不是磁盘或备份的物理擦除承诺。Web 后端是托管控制台身份端点，会解密获准的响应并加密保存；静态加密不改变云端服务能处理这些内容的信任边界。云 MQ 保存签名密文及路由元数据。

agent 离线时保留最后同步数据并标出时间和连接状态；旧数据不能证明当前在线或当前配对仍有效。配对到期、撤销或权限变更由 agent 执行，已披露的账户副本无法远程召回。删除 Web 连接会级联删除该账户在此连接下的工作台副本，不删除 agent 本地数据，也不撤销其他账户的配对。

现有 SDK 没有 `conversation.list`，只能恢复 Web 已记录 ID 的会话。`conversation.get` 和 `inbox.list` 各返回最近 100 项，没有历史分页；不能发现未知旧会话或完整回补远端窗口之外的历史。服务端持续保留实际同步到的消息和回合。

## 多端客户端共享模块

Web 中的协议类型、请求关联验证、稳定请求 ID 与轮询、快照/回合合并、能力与配对检查、只读同步策略已拆入独立 npm workspace [`@agent-comm/client-contract`](../../agent-collaboration-web/packages/client-contract/README.md)。Web UI、API 和同步 worker 使用同一份实现；模块不依赖 React、Next.js、Prisma 或平台密钥，可单独打包供其他 JavaScript 客户端使用。

Swift、Kotlin 等客户端通过同目录的 JSON Schema 和 `fixtures/` 保持 HTTP 字段、时间单位、分页和不确定发送处理一致。客户端可以复用 Web 的账户持久副本与现有 NextAuth cookie 会话；原生客户端的变更请求同样需要匹配服务端配置的 `Origin`。详细的认证流程、接口表和跨语言 fixture 用法见模块 README。底层签名加密、认证存储及各系统的会话持久化仍由对应适配层承担。

## 适配者接入步骤与验收

1. 独立安装 runtime，阅读其 README 与参考适配器，运行合约测试。
2. 实现真实 HostPort，保证主体/会话/回合不是模型参数；测试取消、替换回合和跨主体隔离。
3. 按需注册 MemoryPort 与 InteractionPort，不实现的功能明确不声明；测试有界结果与确认回调。
4. 使用共享 Store 与 TransportPort，保持现有受控动作检查、幂等与 ACK 顺序。
5. 如接入远程工作台，在本机建立有期限的方法配对，并给受支持方法注册 handler；测试陌生发送者、越权方法、重放冲突、到期及撤销。
6. 完成宿主真实集成测试后，再把该适配器列为已支持。接口可用、参考适配器可运行和具体第三方宿主已适配，是三种不同完成状态。

## 数据迁移约定

已退役的根目录 connector、旧安装 CLI、旧云端域数据脚本与 Web mock/demo 入口已移除。Web 旧业务表不再由代码读写；迁移保留旧数据供备份与恢复，不在服务启动时执行破坏性清库。旧 Hermes 导入路径可以保留薄兼容导出，但策略与 Store 只有通用包一份实现。

保护用户已有 helper 密钥、mailbox、connector receipts、collaboration SQLite 和 remote pairing SQLite。程序发布不等于授权删除这些数据，也不等于允许将原记忆系统全量导出。

具体源码合约与可运行示例见 [runtime README](../../agent-comm-platform/agent-comm/python/README.md)，已执行的跨组件验证见 [验证索引](../verification/README.md)。
