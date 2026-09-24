# T13～T21 新增测试执行卡

**状态：本文是执行卡，不记录通过结果；实际结果以对应发布和验收报告为准。** 编号、优先级和发布门禁以[2026-09-24 增量复测方案](RETEST_PLAN_2026-09-24.md)为准；原 T00～T12 的操作及人工步骤见[测试执行指南](TEST_EXECUTION_GUIDE.md)。E2-L 是隔离的旧协议兼容 staging，E2-V 是另一套隔离的 v2 staging；生产已于 2026-09-24 启用签名 `private`、`allow_v1=true`、epoch 1。原公开 r2 包与待发布 v0.8.0 候选包应分开验收；实际公开版本以当次下载清单为准。以下所有写入、故障注入和合成身份只在 E0/E1/E2-V（或标明的 E2-L）使用，E3 仅只读。

每项分别生成 RUN_ID，先保存四仓提交、实际镜像、活动策略状态和接入包清单；保存脱敏的请求 ID、时间线、服务/Agent 日志、前后数据库或 API 快照、`result.json` 与 `cleanup.json`。每个断言标明 **PASS、FAIL、未执行或受阻**，并附证据路径。模拟的 Alice/Bob 授权只证明机制；需要真人选择的分支单独记录同一测试者分别扮演两人，或两名测试者各自的决定。任何结果都不能仅由 HTTP 200、MQ 入队、网关回执或旧 Web 快照推断业务完成。

## T13：公开文档与下载说明（P1；合规告知前 P0）

**目标与环境：** E0 检查四仓 Markdown 结构；在隔离 E2 复现严格检出权限并检查 HTTPS 文档入口、地址跳转、下载清单及访问边界；E3 仅只读核对公网结果。验证文案准确区分“签名 `private` 策略已启用、旧 v1 仍兼容、公开接入包是否已切到 v0.8.0”，并以检查时的策略和下载清单为准。

**Codex：** 运行 `python tools/maintenance/check_structure.py`；逐页请求 `/docs/` 的四仓角色入口、`/docs/?path=platform/guides/API.md`、现行 `/docs/api/` 和旧 `/guide/`，跟随跳转检查相对链接及中英页面；在隔离 E2 用严格只读检出权限复查 Markdown 路由，尝试路径越界和非公开文件地址，记录状态、最终 URL 与响应内容；做桌面/窄屏截图。**你：** 仅在发布合规告知前阅读一次隐私/升级文字，指出是否能理解网关可读范围、是否已启用和如何拒绝；脚本的文字匹配不算真人理解。

**流程：**

~~~mermaid
flowchart TD
    A["冻结文档提交与当前策略/清单事实"] --> B["结构检查和站内链接遍历"]
    B --> C["HTTPS 角色入口、旧地址和中英页面"]
    C --> D["严格文件权限与拒绝路径越界/非公开文件"]
    D --> E["桌面/窄屏和政策告知核对"]
    E --> F{"链接、权限、事实或文案错误？"}
    F -- "是" --> G["FAIL：保存 URL、状态、截图"]
    F -- "否" --> H["PASS：保存检查清单；合规告知另记真人判断"]
~~~

**项目环节：**

~~~mermaid
flowchart LR
    S["四仓 docs 与发布清单"] --> N["nginx 只读 Markdown 路由"]
    N --> U["/docs/ 阅读器与旧地址跳转"]
    U --> H["浏览器中的用户告知"]
    M["实际 Platform 策略"] --> H
    B["公开 ZIP 清单"] --> H
~~~

**判定与证据：** 所有应公开页面为正确内容且无意外 403；旧地址抵达现行页面；不允许的路径不能读到 `.env`、密钥、发布私档或其他非公开文件；文案与 `/api/v2/policy` 和公开 manifest 当时的事实相符。保存链接检查输出、HTTP 状态表、拒绝请求样本与截图；任何泄露、错误模式宣称或关键断链为 FAIL。真实理解未抽查时只记自动检查通过，不记体验通过。

## T14：Platform 管理台数据处置（P0）

**目标与环境：** E0 Go/Node 测试加 E2-V 合成 Registry、v1/v2 MQ 待收与历史数据；生产 E3 只读。验证管理员只能按明确范围查看或处置 Platform 数据，不取得 Agent 本机审批权。

**Codex：** 运行 Platform `go test ./internal/api ./internal/mq` 与 `node --test tests/admin_accessibility.test.cjs tests/admin_functionality.test.cjs tests/admin_security.test.cjs tests/admin_workflows.test.cjs`；在隔离环境造 A/B 两个收件箱和不同状态的消息。先试无/错令牌、边界分页与跨 URN 详情，再显式打开一封密文、删除指定 ID、重复删除、清空一个合成队列及驱逐一条合成注册，逐项比较数据库/API 与审计；批量部分失败逐项复核。**你：** 仅需在真人管理员 UX 抽查时评价确认文案和误操作风险，不需亲自删除测试数据。

**流程：**

~~~mermaid
flowchart TD
    A["E2-V 生成 A/B 合成队列并留前快照"] --> B["拒绝无令牌、错令牌及越界查询"]
    B --> C["核对 pending/history/expired 汇总与分页元数据"]
    C --> D["显式查看单封密文并确认删除目标"]
    D --> E["单封删除、重复删除、清空/驱逐隔离样本"]
    E --> F["比对其他收件箱、审计及失败项"]
    F --> G{"越权、误删或伪成功？"}
    G -- "是" --> H["FAIL 并保留隔离库"]
    G -- "否" --> I["PASS 并清理合成对象"]
~~~

**项目环节：**

~~~mermaid
flowchart LR
    UI["/admin/ 页面"] --> AUTH["X-Admin-Token 鉴权"]
    AUTH --> API["Platform admin API"]
    API --> MQ["v1/v2 MQ 与握手帧"]
    API --> REG["Registry"]
    API --> AUDIT["审计日志"]
    AGENT["Agent 本机决定/配对"] -.->|不由管理令牌授予| AUTH
~~~

**判定与证据：** 待收、历史、过期三类计数与实际行一致且互不重叠；列表只含元数据，完整密文仅在详情显式请求后出现，不出现明文；指定删除仅影响指定收件人/ID，重复删除为安全的 0 项；清空同时处理该测试收件人的待取握手帧，其他队列不变；审计记录真实成功/失败范围。保存操作前后清单、分页结果、脱敏审计和 UI 截图。生产若发生写入即 FAIL。

## T15：六项运行配置预览、保存与恢复（P0）

**目标与环境：** E0 API/配置/UI 测试，E2-V 在有进程重启机制的隔离 Platform 上演练。六项是 `registry.ttl_hours`、`mq.default_ttl_days`、`mq.max_msgs_per_urn`、`relay.enabled`、`relay.max_reservations`、`relay.max_circuit_duration`；身份、数据路径、监听、令牌和 TLS 不通过管理台编辑。

**Codex：** 读取 `GET /api/v1/admin/config/editable` 的 revision；对六项分别提交合法边界、非法值和同值预览，核对服务器返回的变更与受影响计数；在 E0 用可控时间测五分钟令牌失效，在 E2-V 测旧 revision、错令牌/错目标拒绝；只对合成配置确认一次真实变更，等待守护进程重启，重新读取覆盖文件、API、Peer ID、既有 Registry/MQ 行，再通过新的预览恢复原测试值。另在克隆卷上演练写失败和旧版回退对 `admin-policies.yaml` 新字段的处理。**你：** 无需逐项点击；真人管理员体验仅抽查影响说明与确认页。

**流程：**

~~~mermaid
flowchart TD
    A["保存六项、身份与数据前快照"] --> B["读 revision 并预览合法/非法/无变化值"]
    B --> C["验证令牌过期、错目标、旧 revision 均拒绝"]
    C --> D["仅确认隔离环境中的目标变更"]
    D --> E["等待重启并独立复读配置和业务数据"]
    E --> F["新预览恢复测试原值；演练写失败/旧版回退"]
    F --> G{"目标、身份和数据均正确？"}
    G -- "否" --> H["FAIL：保留配置与重启日志"]
    G -- "是" --> I["PASS：保存前后修订号和证据"]
~~~

**项目环节：**

~~~mermaid
flowchart LR
    PAGE["管理台配置草稿"] --> PREVIEW["服务端预览/确认令牌"]
    PREVIEW --> POL["admin-policies.yaml 原子写入"]
    POL --> RESTART["进程守护重启 Platform"]
    RESTART --> LIVE["Registry/MQ/Relay 新配置"]
    LIVE --> READ["独立 API 复读"]
~~~

**判定与证据：** 无效值、过期令牌、旧修订号、目标不一致和待重启时重复保存均拒绝；无变化不重启；写入失败不改变运行值；成功保存后重启复读为精确目标，Peer ID、已有消息和注册记录不因这六项被追溯删除。记录 preview/PUT 响应、revision、覆盖文件哈希与权限、容器重启事件及前后数据库摘要；旧版回退不识别新字段时必须先在隔离副本处理，不能声称直接回退安全。

## T16：签名 v2 私密路径（P0）

**目标与环境：** E1 当前 Platform/双 helper/`cmd/v2-policy` 的真实进程，随后 E2-V HTTPS 重跑；不调用模型，不使用生产策略或密钥。分别验证 `private, allow_v1=true` 兼容期和更高 epoch 的 `private, allow_v1=false` 严格期。

**Codex：** 用临时根签名策略，A/B 各自从测试独立来源固定策略根、预期 Platform Peer ID 与对方完整 Ed25519 公钥；构建三件二进制并运行 `python tests/integration/test_v2_gateway_network.py --platform PATH_TO_PLATFORM --helper PATH_TO_NEW_HELPER --policy-tool PATH_TO_V2_POLICY_TOOL`，再在 E2-V 做 HTTPS 同等断言。核对新 helper 的 `/api/v2/disclosure`、双向临时握手、A/B 收发、收件本机落盘后 ACK、信封无网关槽与 `accepted-uninspected` 回执；用旧 helper 验证兼容期 v1 但标记为旧协议，严格期验证普通 Agent v1 被拒。**你：** E1 合成钥匙可由 Codex 模拟核对；若验收真实身份绑定，你分别从 Platform 之外核对两端公钥和根/Peer ID，结果另记真人证据。

**流程：**

~~~mermaid
flowchart TD
    A["独立固定根、Platform ID、A/B 完整公钥"] --> B["启用已签 private 且 allow_v1=true"]
    B --> C["新 helper 临时握手、v2 双向收发与持久 ACK"]
    C --> D["检查无网关槽和私密回执；旧 helper v1 单列"]
    D --> E["提高 epoch，private 且 allow_v1=false"]
    E --> F["普通 Agent v1 拒绝；v2 重新握手"]
    F --> G{"签名、模式或隔离不符？"}
    G -- "是" --> H["FAIL 并保存原始脱敏证据"]
    G -- "否" --> I["PASS：两种 private 分支分别记录"]
~~~

**项目环节：**

~~~mermaid
flowchart LR
    ROOT["离线策略签发与可信固定"] --> A["Alice helper v2"]
    ROOT --> B["Bob helper v2"]
    A --> HS["Platform v2 握手队列"]
    B --> HS
    A --> MQ["Platform v2 密文 MQ"]
    MQ --> B
    B --> ACK["收件落盘后 ACK"]
~~~

**判定与证据：** A/B 必须验证同一当前策略与对方完整公钥；两向消息保持稳定 ID，收件方解密、持久化后才 ACK；`private` 信封没有 gateway slot，不能写成“网关已审查”；旧 v1 在兼容期可用但不获得 v2 性质，严格期普通 Agent↔Agent v1 拒绝。保存策略原始字节哈希、双方 disclosure、握手/信封/回执摘要、入站与 ACK 时间线及负向 HTTP/libp2p 结果；仅本地脚本通过不算 HTTPS staging 通过。

## T17：签名 v2 合规路径与两端许可（P0）

**目标与环境：** E1 协议负向测试及 E2-V 独立 HTTPS Platform、A/B 两个 helper；测试策略为更高 epoch 的 `compliance, allow_v1=false`，且 `relay.enabled=false`。这是**网关可解密并准入 Agent 间消息**的分支，不能由 `platform.mode` 展示值启动。

**Codex：** 签发测试策略并验证错误组合（合规却开启 v1 或 Relay）启动失败；重启后分别读取 A/B 已验签的 `/api/v2/disclosure`，在尚未授权和只授权一端时尝试新发送/接收，均不得投递。经两个独立本机许可后双向发送无副作用文本；核对信封只有同一正文密文、recipient/gateway 两个密钥槽，网关先实际解密并签 `decrypted-admitted` 回执，B 使用自己解出的 CEK 验证持钥证明并持久收件后 ACK。另测错误签名/回执、同 ID 改字节、旧 v1 HTTP/libp2p、撤回后的新发送和策略变化后的旧授权。**你：** 真人验收时，在可信渠道核对根、Platform ID、网关 key ID、epoch、完整 hash、有效期与披露含义；分别以 Alice 和 Bob 主人身份对**当前精确 hash**允许或拒绝。Codex 可以准备 CLI/界面和复核输出，但不能替你决定真实披露许可；E1 自动调用许可命令只记“模拟授权”。

**流程：**

~~~mermaid
flowchart TD
    A["更高 epoch 的已签 compliance；关闭 v1 与 Relay"] --> B["A/B 核验策略与未授权拒绝"]
    B --> C["Alice 本机决定；Bob 本机另作决定"]
    C --> D{"两端都授权当前 hash？"}
    D -- "否" --> E["保持拒收；记录各自选择"]
    D -- "是" --> F["双向发送并检查网关解密准入回执"]
    F --> G["收件方验证同 CEK 证明、落盘、ACK"]
    G --> H["篡改/重放/v1 绕过/撤回负向检查"]
    H --> I{"有越权披露或状态混淆？"}
    I -- "是" --> J["FAIL，停止 v2 验收"]
    I -- "否" --> K["PASS：分别记录机制与真人决定"]
~~~

**项目环节：**

~~~mermaid
flowchart LR
    POLICY["签名合规策略与本机许可"] --> A["Alice helper"]
    POLICY --> B["Bob helper"]
    A --> ENV["同一正文密文 + 两个 CEK 槽"]
    ENV --> G["Platform 网关解密并准入"]
    G --> R["签名回执与持钥证明"]
    R --> B
    B --> ACK["本机持久收件后 MQ ACK"]
    WEB["Web 用户确认"] -.->|不能替代本机许可| POLICY
~~~

**判定与证据：** 未经任一端当前 hash 的本机许可、新 epoch/网关密钥变化或本机撤回后，新的合规消息不得走旧 v1 旁路；错误签名/密钥槽/回执证明不入收件箱且不 ACK；同 ID 同原始信封仅返回原回执，同 ID 改字节拒绝。回执仅证明网关准入，B 的持久接收和业务处理分别取证；它不证明法律合规。保存原始策略摘要、A/B 的许可/拒绝时间、逐条 mode/epoch/key ID、信封与回执哈希、B 的本机入站/ACK，以及负向拒绝与无明文普通日志证据。若只有脚本模拟授权，真人许可一栏为未执行。

## T18：Web 政策披露、账户暂停与托管 v1 例外（P0）

**目标与环境：** E0 Web 协议/策略单测、E1/E2-V Web + Platform + 两个独立账户/控制台；旧环境 E2-L 验证无策略兼容分支。Web 目前仍使用受证书约束的 **v1 控制 RPC**；不能把它标为 Agent↔Agent v2 私密或合规收据。

**Codex：** 运行 Web `npm test` 与现有 `tests/unit/v2.test.cjs`、`workspace-sync.test.cjs`；在隔离环境依次切换五类策略状态：① 无策略 404 且从未固定根；② 已签 `private, allow_v1=true`；③ 已签 `private, allow_v1=false`；④ 已签 `compliance, allow_v1=false`；⑤ 已固定后策略失效、错签、过期、倒退或不可得。A/B 分别登录、读取披露；只在 `compliance` 下分别确认当前 hash，再测暂停/恢复、控制与同步，比较 MQ 新行及旧工作台快照。严格 private/compliance 下再验证 Web 用控制台私钥登记策略指定签发者的一小时受管证书；证书缺失、到期、撤销或身份不符时不让旧信封越权。分别验证 store 遭 400/403 后自动重登记，以及 retrieve/ACK 的失败关闭或人工重试；重新登记后仅恢复仍被账户允许的控制。旧 v1 行不能因事后登记追溯授权。**你：** 阅读 Web 对“Web 可读、网关可读、当前模式”的说明，评价是否能区分 Web 账户确认与 A/B 各自的本机合规许可；如验收真人 UX，由你分别做账户确认/暂停选择。

**流程：**

~~~mermaid
flowchart TD
    A["两个账户和独立控制台；保留旧快照"] --> B["无策略 404：未固定根时测 legacy"]
    B --> C["已签 private：allow_v1 true/false 分支"]
    C --> D["已签 compliance：A/B 分账户披露与确认"]
    D --> E["合规未确认或暂停成功后：测无新控制/同步"]
    E --> F["有效受管证书登记与 v1 控制往返"]
    F --> G["错签/过期/倒退/证书撤销与重登记"]
    G --> H{"越权、错误标注或旧快照丢失？"}
    H -- "是" --> I["FAIL 并保存账户隔离证据"]
    H -- "否" --> J["PASS：按策略组合分别报告"]
~~~

**项目环节：**

~~~mermaid
flowchart LR
    P["Platform 已签策略"] --> V["Web 固定根/Platform ID 验签"]
    V --> A["账户 A/B 确认与暂停状态"]
    A --> CERT["Web 托管证书登记"]
    CERT --> CTRL["v1 控制 RPC 的明确例外"]
    CTRL --> AG["各自 Agent 的本机配对"]
    A --> SNAP["Web SQLite 旧快照仍可读"]
    AG -.->|不授予 Agent 间合规许可| P
~~~

**判定与证据：** 只有**从未固定 v2 根且平台确无策略**时可按 legacy 控制；固定根后策略 404/不可验签必须失败关闭。`private, allow_v1=true` 的兼容路径与 `allow_v1=false` 的受管证书路径分开记账；`compliance` 需 A/B 各自当前 hash 的 Web 确认，未确认或暂停 API 成功后不得发起新的控制、MQ 拉取与同步，旧副本仍可读；此前在途响应与 ACK 单独取证，不误判成新请求。状态为 `policy_paused` 或错误时 `policy_unavailable`，不伪报 `needs_pairing`。有效证书仅准许所属控制台，过期/撤销/错误身份不得放行；store 的自动重登记与 retrieve/ACK 的拒绝或恢复分别记录，成功重新登记不能重写旧 v1 准入事实。保存两账户披露/API/浏览器截图、证书序号和有效期的脱敏记录、MQ 前后行数、同步状态与 Agent 本机 pairing 证明；Web 确认与 helper 本机许可分别列栏。

## T19：原身份迁移、旧队列隔离和高 epoch 回退（P0）

**目标与环境：** E2-V 独立部署，使用同一组测试身份、Web 账户和旧 SQLite/配对从旧 v1 经已签 `private` 兼容期升到 `compliance`；备份和故障只碰测试卷。验证迁移保留历史，但不把旧密文追溯标为网关审查。

**Codex：** 先留旧 v1 待收/已读、好友、Web 快照与私密 v2 队列样本；在线备份 Platform 三库、Web 库及身份/策略文件并做 `PRAGMA quick_check`。同身份升级，在 `private, allow_v1=true` 处理一部分旧消息，留下未读样本；签更高 epoch 合规策略，核对未交付旧 v1/private 行被隔离而非重加密/误 ACK，跨 epoch 的同字节重试只取回原回执；确需重发时由新意图分配新 ID。轮换策略 key/hash 后核对先前许可失效、进程重启后最高 epoch 仍保存；尝试旧签策略及仅关闭 v2 配置均不得重新开放普通 v1。若演练技术回退，另签**更高 epoch** 策略，在恢复隔离副本中检查同一 Peer ID、身份、历史和切换后新写入。**你：** 真实披露及任何生产切换由你决定；Codex 可独立操作合成数据的 E2-V。

**流程：**

~~~mermaid
flowchart TD
    A["同一身份创建旧 v1/私密队列和 Web 历史"] --> B["在线备份、quick_check、记录 Peer ID"]
    B --> C["private 兼容期交付部分旧消息"]
    C --> D["更高 epoch 切合规；旧未读/待发隔离"]
    D --> E["核对原字节重试与新 ID 重发"]
    E --> F["策略轮换、重启、旧策略/关闭 v2 绕过尝试"]
    F --> G["更高 epoch 技术回退及隔离恢复核对"]
    G --> H{"身份、数据、隔离或防回退异常？"}
    H -- "是" --> I["FAIL，保留卷与时间线"]
    H -- "否" --> J["PASS，备份与实时写入均可核实"]
~~~

**项目环节：**

~~~mermaid
flowchart LR
    OLD["原 helper/Web 身份和旧队列"] --> BACK["SQLite 在线备份 + 身份文件"]
    OLD --> PRI["签名 private 兼容期"]
    PRI --> COMP["更高 epoch compliance"]
    COMP --> Q["旧密文隔离；新消息按新 ID"]
    COMP --> RESTART["Platform/helper/Web 重启"]
    RESTART --> ROLLBACK["更高 epoch 技术回退"]
    BACK --> RESTORE["隔离副本恢复核对"]
~~~

**判定与证据：** 既有 URN/Peer ID、密钥、mailbox、Web 账户/配对及历史不重置；旧未读不被当前策略取回或标为 `decrypted-admitted`，旧 v1 普通 Agent 流不能通过 HTTP/libp2p 绕过；同 ID 不重新加密，需新发送时新意图/新 ID；策略倒退、同 epoch 改文、仅关 v2 均失败关闭。四库备份及恢复 `quick_check=ok`，恢复副本含切换前历史，实时库切换后的新写入仍在。保存版本/epoch/hash 时间线、队列行摘要与状态、双方许可状态、备份清单与恢复报告；不得用上线前备份覆盖实时库制造通过。

## T20：公开包、候选 v2 包与严格权限镜像（P0；公开 v2 前必过）

**目标与环境：** E0 打包校验，E2-L 测试冻结的 r2 旧版首装，E2-V 候选 v2 首装/原身份升级，以及原生 Windows amd64、Linux amd64、macOS amd64/arm64 环境。检出权限复现用隔离 Linux 构建环境，不在生产改文件权限。v2 正式发布后另用当时官网清单和 ZIP 做公开首装，不以候选包结果代替。

**Codex：** 先核对官网 `release-manifest.json` 和四种公开 ZIP，按[接入包指南](../../tools/release/early_access/README.md)在独立 Hermes Python/profile 运行 `install.py --check-only` 与 `onboard_hermes.py`，确认 r2 接当前兼容服务。另由根仓库发布工具从**干净且已提交的四仓固定检出**构建四种**单独标记的候选 v2 完整 ZIP**，记录外部 manifest 与内部 `SHA256SUMS.json`、两个 wheel、helper/脚本摘要；各原生 OS 测错误架构拒绝、首装与保留原 `keys_dir`/`mailbox.db` 的就地升级。候选 Agent 间发送只连已签 E2-V 策略，并按 T16/T17 核对信任锚和授权。用严格 `umask 077` 的检出重建 Web 镜像，以 UID 1001 在旧库上实际运行迁移并读取 Prisma SQL、CLI 与 Next 文件；复核旧账户/控制台、`UserPolicyConsent`、`UserControlPause`。**你：** 需要真人首装 UX 时查看 claim 的账户、权限和期限并作本次授权决定；Codex 可完成预先约定的合成账户安装。macOS 原生机器等缺失时只标未覆盖，不借交叉编译代替。

**流程：**

~~~mermaid
flowchart TD
    A["冻结公开 r2 与候选 v2 两份清单"] --> B["四包摘要、wheel、脚本和 OS/CPU 校验"]
    B --> C["公开 r2：干净 Hermes 接 E2-L"]
    C --> D["候选 v2：原生首装与旧身份就地升级到 E2-V"]
    D --> E["严格 umask 构建；UID 1001 旧库迁移"]
    E --> F["复读身份、mailbox、配对和新旧表"]
    F --> G{"某平台未原生测或迁移异常？"}
    G -- "未测" --> H["该平台标未覆盖，不称四包通过"]
    G -- "异常" --> I["FAIL，保留包与迁移日志"]
    G -- "全部通过" --> J["PASS，分开记录公开包/候选包/镜像"]
~~~

**项目环节：**

~~~mermaid
flowchart LR
    SRC["固定四仓源码"] --> PKG["四种候选 ZIP + 内外摘要"]
    PUB["官网 r2 manifest/ZIP"] --> VERIFY["原生 OS 安装校验"]
    PKG --> VERIFY
    VERIFY --> HERMES["Hermes Python/profile 与 helper 身份"]
    HERMES --> CLAIM["Web claim 与 E2 Platform"]
    SRC --> IMAGE["Web 严格权限镜像"]
    IMAGE --> DB["UID 1001 在旧 SQLite 上迁移"]
~~~

**判定与证据：** 公开 r2、候选 v2 和镜像迁移必须有三份独立结论；候选包未发布时不能把其 PASS 写成官网可下载。每个 OS 原生 `--check-only`、首装、错误架构拒绝、升级后同 URN/密钥/mailbox/配对和可用控制链路均有输出，未跑的 OS 标“未覆盖”。Web 以非 root UID 可读运行时文件、旧库迁移成功，身份与历史未丢失，四库 `quick_check=ok`。保存清单 SHA-256、安装前后包/路径清单、claim 与连接结果、镜像 digest/UID、迁移输出和表/数据摘要；不把私钥、完整 `onboarding.json` 或数据库提交仓库。

## T21：有界并发、慢轮询与断线恢复（P1；发布观察 P0）

**目标与环境：** E2-L/E2-V 各自两套真实隔离 Agent 和 Web 账户，使用部署镜像实际 `DATABASE_URL` 的单连接配置。验证两个用户同时操作时没有写锁/连接池失败、重复业务或控制状态误判；E3 只读观察。该缓冲只在单 Web 进程内排队，不证明多副本共享 SQLite 安全。

**Codex：** 在运行前把并发数、轮次、请求总数、每接口超时和历史 p95/p99 基线写入 `run-config.json`；标准窗口为 A/B 各 8 轮、最多 12 个并行 HTTP 请求、至少 150 个完成请求，同时覆盖控制轮询、工作台读取、同步与 Push。令两边真实 helper 都消费控制请求，核对最终 Web/Agent 状态；记录每接口请求数、p95/p99/max、达到 2 秒的分段计时、HTTP 5xx、Code 5、P2024、重启数。另在明确标注的故障注入窗口只断开一次**测试**网络/TLS，保留原 request ID 查询或重试，核对 Agent Store/Web 投影没有第二次业务副作用。注入前后各留一段正常窗口；不自动抹掉单次错误记录。**你：** 无需参与脚本负载；若要判断两边页面在长尾期间是否令人困惑，可抽查等待、失败和恢复提示。

**流程：**

~~~mermaid
flowchart TD
    A["固定版本、单连接 URL、基线和负载参数"] --> B["A/B 真 helper + 双账户重叠并发窗口"]
    B --> C["逐请求记录状态、时延与两端最终事实"]
    C --> D["单次受控 TLS/网络中断"]
    D --> E["用原 request ID 恢复查询，检查无重复"]
    E --> F["正常窗口复跑并收集分段日志/容器状态"]
    F --> G{"5xx、Code 5、P2024、丢失/重复或非注入 TLS EOF？"}
    G -- "是" --> H["FAIL：保留失败窗口和原始请求"]
    G -- "否" --> I["PASS：报告延迟分布与已知限制"]
~~~

**项目环节：**

~~~mermaid
flowchart LR
    AW["Alice Web"] --> N["HTTPS/nginx"]
    BW["Bob Web"] --> N
    N --> WEB["单进程 Web/Prisma 单连接排队"]
    WEB --> DB["Web SQLite 状态/同步任务"]
    WEB --> P["Platform Registry/MQ"]
    AH["Alice helper"] -->|HTTPS| P
    BH["Bob helper"] -->|HTTPS| P
    P --> AG["A/B helper 持久收件与业务 Store"]
    WEB --> MET["慢轮询阶段计时与错误日志"]
~~~

**判定与证据：** 非注入窗口至少完成预定请求数，均在预先记录的接口时限内达到预期状态；无 HTTP 5xx、Code 5、P2024、非注入 TLS EOF、丢失/重复业务或容器意外重启。注入窗口允许预定的一次传输失败，但原 request ID 的恢复查询必须与 Agent 最终事实一致且无二次执行。p95/p99 与 2 秒慢轮询计数作为固定基线比较和定位材料，不在测后修改阈值；即使复跑成功，既有 TLS EOF 原失败仍留在报告。保存 `run-config.json`、逐请求脱敏时间线、两端业务 ID/Store 对账、分位数与阶段日志、容器/数据库检查；E3 只读数据不能证明故障注入通过。
