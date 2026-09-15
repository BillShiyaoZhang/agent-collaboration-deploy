# 当前项目架构与流程图

需要逐层理解实际代码，可阅读 [技术实现详解：13 张 Mermaid 图](TECHNICAL_IMPLEMENTATION_WALKTHROUGH.md)。该文核对 2026-09-15 部署锁定源码，展开加密、RPC、确认租约、消息 ACK、同步 worker、数据模型与故障恢复。

更新：2026-09-14。Web 根据用户要求持久保存账户的连接、联系人和消息，并主动同步；agent 侧提供业务事实与执行授权，通用 runtime 支持不同宿主、记忆与交互渠道。接口细节见 [扩展接口设计](ARCHITECTURE_AND_EXTENSION_PORTS.md)。主动同步改动的验证与上线状态以实际发布记录为准。

## 1. 产品与数据归属

```mermaid
flowchart TB
    U["用户"]
    subgraph LOCAL["Agent 侧"]
        H["用户自己的 Agent / 私人记忆"]
        A["宿主、记忆、交互适配器"]
        R["agent-comm-runtime"]
        D[("联系人、委托、审批、操作、收件")]
        RB["远程配对 / RPC / 会话状态"]
        HP["Go helper：身份与持久收发"]
        H <--> A
        A <--> R
        R <--> D
        R <--> HP
        RB <--> D
        RB <--> HP
        RB <-->|"受配对约束的真实会话"| H
    end
    subgraph CLOUD["云端"]
        W["Web 远程工作台"]
        WD[("账户、连接、控制台凭据<br/>加密的联系人、消息与已知会话副本")]
        WC[("独立的有限期 RPC 密文缓存")]
        WS["常驻 Node 同步 worker"]
        P["Registry / MQ"]
        W <--> WD
        W <--> WC
        W <-->|"认证加密 RPC"| P
        WS <--> WD
        WS <--> WC
        WS <-->|"周期只读 RPC"| P
    end
    U <-->|"原生交互"| H
    U <--> W
    P <--> HP
    P <--> OTHER["对方 Agent 的兼容客户端"]
```

Web 的账户副本保存已认证返回的联系人、消息、事项和会话，内容使用 AES-GCM 静态加密，供跨页面、刷新和换设备恢复。控制台添加连接记录不授予访问权；agent 侧配对决定哪个控制台能调用哪些方法、能访问哪个主体、到何时过期。

## 2. 可替换的代码端口

```mermaid
flowchart LR
    H["HostPort<br/>可信主体 / 会话 / 回合"] --> REG["AdapterRegistry<br/>版本与能力校验"]
    M["MemoryPort<br/>检索 / 有限资料快照"] --> REG
    I["InteractionPort<br/>确认 / 可选通知"] --> REG
    T["TransportPort<br/>持久 store / retrieve / ack"] --> REG
    REG --> R["Runtime.dispatch<br/>统一授权和执行路径"]
    R --> D[("共享本地 Store")]
```

这些是开发接口，不是公网监听端口。缺失的能力返回 unsupported；配置中的可信插件才能注册。Hermes 提供首个实际 Host/Interaction 适配器，其它宿主可以独立安装 runtime 开发。知识图谱尚需实现 MemoryPort，不会自动上传或同步整库。

## 3. 远程连接与配对

```mermaid
sequenceDiagram
    actor U as 用户
    participant W as Web
    participant L as Agent 侧 CLI
    participant B as RemoteBridge
    participant S as Agent 侧状态
    U->>W: 登录并保存 Agent 连接
    W-->>U: 显示控制台公共 URN
    U->>L: 在本机明确配对 URN、方法、期限
    L->>B: 保存配对到本地 SQLite
    W->>B: 经 helper / MQ 发送认证 RPC
    B->>B: 校验签名来源、配对、方法与期限
    B->>S: 查询或提交受支持工作
    S-->>B: 真实数据或提交状态
    B-->>W: 返回绑定 request_id 和双方 URN 的响应
```

Web 的控制台身份兼容既有 URN，不要求用户重新生成身份。未配对、错主体、越权方法、重放冲突和到期请求不能获得数据。远程 conversation.send 提交到真实 Hermes 独立会话，最终答复从 agent 侧 conversation.get 查询；远程审批暂不开放。

### 账户恢复与后台同步

```mermaid
sequenceDiagram
    participant N as Next.js Node 进程
    participant J as 后台同步 worker
    participant D as 账户加密副本
    participant A as Agent（经认证 MQ）
    participant B as 用户浏览器
    N->>J: instrumentation 启动常驻任务
    B->>D: 通过登录 API 读取已保存数据
    D-->>B: 联系人、消息、已知及当前会话、最后同步时间
    loop 无需点击，按租约与退避调度
        J->>A: capabilities
        A-->>J: 当前配对范围和期限
        J->>A: 已授权的 state 或独立读取；当前和待完成会话 get
        A-->>J: 关联到请求的认证响应
        J->>D: 更新联系人视图，按 ID 保存消息和回合
    end
    B->>D: 后台刷新账户视图
    D-->>B: 新数据或离线状态及最后同步数据
```

后台只发读取 RPC，不定时发送对话、不代替审批。结果不确定的发送保留原请求供恢复和核实，不以新 ID 自动重发。收件箱和会话读取只有最近 100 项，保存时不会因新窗口缺项而删掉旧消息；现有协议没有 `conversation.list`，未知旧会话不能自动发现，也不保证窗口之外的完整历史回补。

## 4. 本地协作与授权

```mermaid
flowchart TD
    START["原生会话发起 / 继续任务"] --> STATE["读取 state / inbox"]
    STATE --> CONTACT["明确联系人；首次绑定确认"]
    CONTACT --> GRANT["建立 / 恢复有期限委托"]
    GRANT --> ACTION["准备固定对象与内容的动作"]
    ACTION --> POLICY{"策略判定"}
    POLICY -->|"allow"| SEND["执行前复查、预占预算、提交 helper"]
    POLICY -->|"ask"| ASK["通过 InteractionPort 确认具体动作"]
    POLICY -->|"clarify"| FIX["补齐信息"]
    POLICY -->|"deny"| STOP["停止该动作"]
    ASK -->|"可信回答同意"| SEND
    ASK -->|"拒绝 / 超时"| STOP
    FIX --> ACTION
    SEND --> WAIT["保存状态，等待对方"]
    WAIT --> RESUME["会话查询消息后继续"]
    RESUME --> ACTION
```

授权维度包括能力、对象、参与人、资料、时间范围、时长、累计候选/动作数量和期限。范围内结构化动作可连续执行；自由文本逐次确认。登记资料不等于披露许可，新增参与人不等于向其开放原资料。

## 5. 原生确认的可信来源

```mermaid
sequenceDiagram
    participant A as Agent
    participant R as Runtime
    participant H as HostPort
    participant I as InteractionPort
    participant S as Store
    A->>R: confirm(approval_id)
    R->>H: 获取并检查宿主会话
    R->>S: 获取确切问题与私有租约
    R->>I: 展示用户问题并等待回答
    I-->>R: 渠道返回回答
    R->>H: 重新核对回合与归属
    R->>S: 校验租约、版本、期限
    S-->>A: 授权 / 拒绝 / 待澄清
```

Hermes 当前对应原生问题卡的回答框。主聊天框中的裸“可以”、远端 JSON 的 approved=true、模型自报用户同意，都不能替代该流程。适配器扩展必须验证真实渠道身份。

## 6. 消息持久收发

```mermaid
sequenceDiagram
    participant A as 我方 runtime
    participant AH as 我方 helper
    participant MQ as 云 MQ
    participant BH as 对方 helper
    participant B as 对方 runtime
    A->>A: 保存动作、预算和稳定 ID
    A->>AH: 提交
    AH-->>A: 本机持久接受
    AH->>MQ: 投递同一签名密文
    MQ-->>AH: 平台存储成功
    AH->>AH: 标记 platform_queued
    BH->>MQ: 认证拉取
    BH->>BH: 验证、解密、落盘
    BH->>MQ: ACK
    BH-->>B: 通知 / 重放
    B->>B: 持久保存
    B->>BH: 本机 ACK
```

可靠 helper 出站使用 HTTPS MQ。传统 SDK 另有 P2P/DR 与平台 Relay，不能混画成此处的默认路径。通信 ACK、业务接受和日历执行是不同事实；当前会议能力发送协商消息，不写日历。

## 7. 恢复、撤销与当前自动化范围

```mermaid
flowchart TD
    RESTART["进程重启 / 新原生会话"] --> READ["读取 agent 侧持久状态"]
    READ --> CONFIRM["待确认：新租约、原期限"]
    READ --> RETRY["未完成投递：同一操作和消息 ID"]
    READ --> REMOTE["远程请求：复用持久响应"]
    READ --> RUN["中断的远程会话：标记 interrupted"]
    RETRY --> CHECK{"当前授权仍有效？"}
    CHECK -->|"是"| CONTINUE["继续尚未完成的收件人"]
    CHECK -->|"否"| STOP["停止后续动作"]
    RUN --> REVIEW["由用户检查结果；不自动重放未知副作用"]
```

配对撤销阻止后续 RPC 与未执行的远程任务；已开始的宿主工具和已披露的信息不能回滚。协作对端收件仍不自动唤醒私人 LLM；有范围的远程主人会话请求是另一条显式入口。

数据库分层保留：协作 Store、远程配对/会话库、connector receipts、helper mailbox/密钥、云 Registry/MQ，以及 Web 的账户持久副本和独立投递缓存。Web 的 10 分钟 RPC 缓存到期不删除已同步历史。离线时仍可查看最后同步的数据及时间，不据此声称当前在线；删除连接级联删除该账户的相关副本，不改变 agent 本地记录。

旧浏览器 demo、Web 独立业务 API/页面、根目录退役 connector 和旧安装脚本已移除。历史产品探索保留为决策记录，不再作为当前安装说明。
