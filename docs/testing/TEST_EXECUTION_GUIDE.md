# 测试步骤说明：两个 Agent、两边用户与整套部署链路

原有执行基准：2026-09-22；2026-09-24 的变更、重测范围和新增门禁见[增量测试计划](./RETEST_PLAN_2026-09-24.md)。本文是可照着执行的 T00～T12 顺序，覆盖从组件回归到两个 Agent 互相通信，再到 Alice/Bob 两边用户介入和服务器升级。每个测试活动都说明目标、Codex 可代办的步骤、你必须参与的步骤、环境、流程图和它在项目链路中的位置。执行前以实际源码、运行配置和公开安装包分别核对版本，不能把任一层的结果当作另一层已通过。

## 0. 统一角色、环境和证据

测试中的角色固定为：

| 角色 | 对应对象 | 你的操作 |
| --- | --- | --- |
| Alice | Hermes profile A、helper A、Web 账户 A | 发起请求、确认联系人/事项、发送消息 |
| Bob | Hermes profile B、helper B、Web 账户 B | 接收、接受/拒绝好友、回复消息、处理审批 |
| Platform/Web 运维者 | staging 服务器 | 启停服务、备份、查看日志、执行升级/恢复 |
| 测试记录者 | Codex | 为每一步记录时间、决定、状态和证据；你只补充主观体验 |

Codex 可以在临时环境中创建 A/B 身份、启动进程、操作两个浏览器会话、轮询接口、收集日志和生成报告。只有真实用户意图、Hermes 原生确认、系统权限弹窗、服务器凭据以及生产发布/回滚仍由你决定。只有一个人时，你可以交替操作 Alice 和 Bob 两侧；每次切换必须回到对应的浏览器 profile、Hermes profile 和终端，不能用数据库修改来代替用户点击。若要验证真实的双人体验，再让第二个人只操作 Bob 侧。

### 执行人标记

| 标记 | 含义 |
| --- | --- |
| **C** | Codex 可以在当前工作区或临时测试环境独立完成；你不需要逐步操作。 |
| **C+授权** | Codex 可以执行，但需要你先提供一次性服务器/浏览器/测试账户授权，并确认目标是 staging 或临时数据。 |
| **H** | 必须由你做真实用户决定、提供秘密凭据，或批准高影响的服务器动作。Codex 可以准备界面和证据，但不能替你做这个决定。 |
| **C→H** | Codex 先自动执行到决定点，再暂停给你；你完成决定后，Codex 继续对账和收集证据。 |

默认原则是：Codex 自动完成所有可逆、隔离、无副作用的步骤；你只介入真实授权和不可由程序推断的决定。

使用临时 A/B 账户时，可以先约定本轮脚本中的“接受、拒绝、审批、claim 确认”等选择，随后由 Codex 操作两侧界面并核实状态，不必每次再请你点击。它证明预定用户决定能正确生效；涉及真实人的理解、意愿或原生界面体验时，再由你扮演 Alice/Bob 做一次人工验收。已有的环境和操作授权沿用，不逐步重复索取。

Codex 的实际执行边界：我可以读写当前工作区、运行本地命令、启动临时进程和 Docker、运行 Node/Go/Python 测试、操作已有 Playwright/浏览器会话、收集日志和生成报告。访问 staging 服务器、真实 Hermes profile、外部模型账户或系统通知，需要你先提供对应的连接/授权。生产环境的升级、回滚、删除、密钥读取和任何真实用户决定不自动执行；我会先准备检查、停在确认点，或只做只读验证。

环境分为四层：

| 环境 | 用途 | 必需对象 | 是否调用模型 |
| --- | --- | --- | --- |
| E0 本地组件 | 单元、协议、策略、迁移 | Node、Go、Python、临时 SQLite | 否 |
| E1 本地组合 | 两个 helper 与 Platform 的真实收发 | 构建后的 Platform/helper、临时身份 | 否 |
| E2 staging | HTTPS、Web、两个 Agent、两边用户 | 使用已有阿里云服务器部署测试服务；若与生产共用，隔离服务、卷、端口和域名；两个 helper、一个或两个 Hermes | T07、T12 回显；原生对话用例按实际需要 |
| E3 线上烟测 | 部署后健康和只读验证 | 线上域名、smoke 账户 | 否 |

每次运行开始前生成 RUN_ID，例如 20260922-120000-ab12。所有账户、消息、联系人、任务和报告都带 RUN_ID。至少保存：

- A/B 两个 helper 的 /info；
- A/B 的 Console URN、配对方法和期限；
- request_id、message_id、approval_id、task_id、conversation_id；
- Platform、Web、helper、Hermes 日志；
- A/B 的 state、contacts、inbox、attention 快照；
- 浏览器截图和最终 result.json。

判断时永远区分：

~~~text
本机接受 != Platform 入队 != 对方 Agent 收到
对方 Agent 收到 != 对方用户接受
conversation submitted != Hermes 已完成回答
~~~

### 两个 Agent 的隔离方式

最小隔离单元是“身份 + 进程 + 数据目录 + 端口 + profile”。先在本机创建 Alice/Bob 两套测试目录和进程，连接同一个阿里云测试 Platform；不需要为每个 Agent 单独部署 Platform。下面按自动接入脚本的实际默认布局组织，A/B 对称：

~~~text
build/test-runs/RUN_ID/
├── agents/alice/
│   ├── hermes-install/      # 测试 Hermes 安装及独立 Python 环境
│   └── hermes-profile/      # 通过 --hermes-home 选择
│       └── agent-comm/
│           ├── identity/    # helper 密钥及 mailbox.db
│           ├── collaboration.sqlite3
│           ├── remote.sqlite3
│           ├── releases/    # 校验后的接入包
│           ├── onboarding.json  # 含本机凭据，不复制进报告
│           └── logs/
└── agents/bob/
    ├── hermes-install/
    └── hermes-profile/      # 同样结构，独立身份和数据库
~~~

隔离规则：

- A/B 使用不同 helper keys、URN、Peer ID、mailbox、runtime state、remote pairing、Hermes profile、Web 账户和 Console URN。
- helper A/B 使用不同 loopback 端口，例如 45042 和 45043；每个 helper inbox 只允许一个活跃 Hermes connector/consumer。
- A/B 各自使用独立浏览器 context/profile，隔离 cookie、localStorage 和 Web 登录；两个普通标签页不构成会话隔离。
- 各自 `allow_from` 使用明确 URN：Web 配对加入本方 Console；测试直接宿主通信时才按需要加入对端 Agent。联系人关系不自动授予远程控制或工具执行权，禁止通配授权和复制对方身份/数据库。
- 自动接入时 A 使用 `--hermes-home <A_HOME> --python <A_PYTHON> --port 45042`，B 使用对应 B 路径及 45043；两者的 `--platform` 相同。分别核对脚本报告的 home、helper `/info`、Gateway PID、会话和数据库路径。
- 新 profile 只隔离配置和状态；安装/升级测试还必须隔离 Python 环境，避免 `install.py` 重装两边共享的包。T12 不能复用已装过 agent-comm 的解释器。
- 同一 OS 用户下的目录隔离不限制 Agent 工具读取另一目录。上述方式适合固定无副作用用例；验证工具权限或要求更强隔离时，使用两个 VM/容器或有文件权限隔离的 OS 用户，不挂载另一侧或你的真实 profile。两边只需访问共同的测试 Platform，不开放 helper 到公网。
- 如果一个 Hermes 进程不能同时运行两个独立 profile，第二个真实 Agent 要放到另一台机器、虚拟机或容器；第二个 helper 不能替代第二个真实宿主会话。
- Codex 用 A Console 访问 B 验证拒绝，停止 A 确认 B 仍工作，再检查消息/会话没有串到另一侧，作为隔离验收。
- 收尾先停止本轮 Gateway、helper、后台 pairing 任务及关联服务，保存脱敏证据，再按 RUN_ID 清理临时数据；不能只删目录留下后台进程，也不能删除给其他用例复用的 staging 卷。

### staging 主机可以使用现有阿里云服务器吗？

可以。**staging 就是发布前的测试环境，默认使用你已有的阿里云服务器，不要求购买新 ECS。** E0～E3 是测试层次，也不代表需要四台机器。

- 服务器专门用于这个项目的测试：直接用它部署测试版 Platform/Web/nginx，配套测试域名、数据和凭据；本机运行 Alice/Bob。
- 服务器还在承载生产：在同一 ECS 上部署独立测试实例。让 HTTPS 入口按 staging 子域名将 Web 路由和 Platform 的 `/api/v1/`、`/healthz` 路由都指向测试服务，测试实例使用独立 Compose project、卷、数据库、`.env`、Platform 身份及端口。
- 当前根 Compose 有固定 `container_name` 和 80/443/45041 端口，单加 `-p agent-staging` 不足以共存。Codex 在部署前生成并检查 staging 配置，移除/改名容器，替换冲突端口和挂载。根 nginx 配置的域名、证书路径、`NEXTAUTH_URL` 也要改为测试值；Platform 的外部 P2P 地址、映射端口、可信代理网段要与测试部署一致。当前文档没有声称这些配置已经生成或部署。

Codex 负责检查现有服务、生成配置差异、核实卷/端口/路由和备份位置，再在已授权测试范围执行。只有涉及已有生产入口变更或影响生产的启停才保留最终审批；同机故障注入只针对测试容器。必须模拟整机重启、资源耗尽等故障时，使用可独占的测试机或 VM。

---

## T00：环境和版本预检

**目标**

分别确认本轮源码、服务器实际运行版本、v2 签名策略是否启用、公开安装包版本，以及隔离数据，避免把源码能力误判为线上或公开包能力。

**Codex 可代办（C）**

1. 生成 RUN_ID 和 staging 测试目录。
2. 分别记录根仓库及三个子模块固定提交、工作树状态，以及服务器实际运行的镜像 digest、Compose 配置和服务状态；源码提交不能替代容器版本证据。
3. 单独记录签名 v2 策略状态：`/api/v2/policy` 是否可用、策略 epoch/摘要/模式，以及实际是否加载 v2 Compose 覆盖文件。接口返回 404 时标记为“v2 代码存在、策略未启用”，不推断隐私或合规消息已上线。
4. 单独读取公开 `release-manifest.json`、对应 ZIP 摘要和包内 helper/runtime 版本；若另有候选包，记录其独立摘要和来源，不与现有公开包混写。
5. 用临时值运行 compose config，检查缺失密钥时是否按预期失败。
6. 在已授权的 staging 服务器启动或检查 nginx、Web、Platform，保存 healthz、证书和容器日志。
7. 检查 Alice/Bob 的 keys、mailbox、profile、端口和数据库路径是否互不相同。

**你只需参与（C+授权/H）**

- 提供 staging 主机、测试域名和日志读取权限，并确认不会触碰生产卷。
- 提供或在本机安全输入 staging 所需密钥；Codex 不应读取生产 secret 明文。
- 如果发现容器名、DNS、证书或数据卷会与生产冲突，由你决定使用独立主机还是建立 staging override。

**环境**

E2 staging 服务器；本机可暂时不启动 Hermes。

**流程**

~~~mermaid
flowchart TD
    A["生成 RUN_ID"] --> B["分别记录源码、运行镜像、签名策略和公开包"]
    B --> C["检查 staging .env、卷、DNS 和证书"]
    C --> D["docker compose config"]
    D --> E["启动 nginx、Web、Platform"]
    E --> F["检查 /healthz、HTTPS 和容器状态"]
    F --> G{"全部通过？"}
    G -- "否" --> H["停止本轮测试并修复环境"]
    G -- "是" --> I["保存四层版本清单，进入 T01/T02"]
~~~

**在项目中的环节**

~~~mermaid
flowchart LR
    S["根仓库提交"] --> M["固定 Web/Platform/SDK 子模块"]
    M --> C["Compose 配置"]
    C --> N["nginx"]
    C --> W["Web"]
    C --> P["Platform"]
    N --> H["健康检查"]
    W --> H
    P --> H
~~~

**通过条件**

- staging 健康、HTTPS 和证书正确；
- 生产数据卷没有被挂载；
- 源码、服务器运行镜像、v2 签名策略状态及公开安装包分别有可追踪证据；
- 任一服务不健康时不进入业务测试。

---

## T01：组件单元、协议和安全基线

**目标**

在启动两个 Agent 前，先证明各组件自身没有回归：协议、签名、认证、数据库迁移、策略、重试和容器安全都通过。

**Codex 可代办（C）**

- 安装/检查锁文件依赖，运行 Web、Platform Go 与管理台、SDK Go、Python runtime、Hermes 与 OpenClaw connector 测试。
- 收集失败输出、测试数量、构建产物和已有 lint 警告。
- 生成 E0 result.json，并标记阻断项。

**你只需参与（H）**

- 只有当 Python、Go、浏览器或依赖未安装时，决定在哪里安装；不需要亲自逐条执行测试命令。
- 对已有警告决定是记录为已知问题，还是把它提升为本轮发布阻断。

**环境**

E0。本机需要 Node 20+；SDK/Platform 测试还需要 Python 3.11+ 和 Go。

**执行步骤**

~~~sh
cd agent-collaboration-web
npm ci
npm run db:generate
npm test
npm run lint
npm run build

cd ../agent-comm-platform
go test ./...
node --test tests/admin_accessibility.test.cjs tests/admin_functionality.test.cjs tests/admin_security.test.cjs tests/admin_workflows.test.cjs

cd agent-comm
go test ./...
python -m unittest discover -s python/tests -q
python -m unittest discover -s connectors/hermes-platform/tests -v

cd connectors/openclaw-channel
npm ci
npm test
~~~

**流程**

~~~mermaid
flowchart TD
    A["安装锁定依赖"] --> B["Web 单元与契约测试"]
    B --> C["Web lint/build"]
    C --> D["Platform Go 测试"]
    D --> E["Platform 管理台 Node 与 SDK Go 测试"]
    E --> F["Python runtime、Hermes 与 OpenClaw 测试"]
    F --> G{"有失败、未解释 skip 或构建错误？"}
    G -- "是" --> H["阻断后续测试"]
    G -- "否" --> I["生成 E0 报告"]
~~~

**在项目中的环节**

~~~mermaid
flowchart LR
    WEB["agent-collaboration-web/tests/unit"] --> NODE["Node/npm"]
    CONTRACT["packages/client-contract"] --> NODE
    SDKGO["agent-comm-platform/agent-comm"] --> GO["Go packages"]
    RUNTIME["agent-comm-platform/agent-comm/python"] --> PY["Python runtime"]
    HERMES["connectors/hermes-platform"] --> PY
    ADMIN["Platform 管理台"] --> NODE
    OPENCLAW["connectors/openclaw-channel"] --> NODE
    NODE --> GATE["E0 合并门禁"]
    GO --> GATE
    PY --> GATE
~~~

**通过条件**

- Web 当前提交的全部测试通过；记录实际测试数量，不沿用旧版本的固定数量；
- Web lint/build 通过；已有警告必须记录；
- Platform Go 与管理台、SDK Go、runtime、Hermes 与 OpenClaw connector 没有新增失败；
- T01 不通过时不执行 E1/E2。

---

## T02：两个临时 Agent 的协议闭环

**目标**

不调用模型，分开验证旧 v1 社交能力兼容路径，以及新版 helper 在签名 v2 策略下的双 Agent 收发；两条路径使用不同的 helper 版本与判定条件。

**Codex 可代办（C）**

1. 创建随机临时目录、两个 helper key、临时 SQLite 和随机端口。
2. 为旧 v1 回归准备与其匹配的旧版 helper；为 v2 准备当前 helper、Platform 和离线策略签发工具，分别启动隔离进程并运行对应组合测试。
3. 自动轮询 /info、Registry、MQ、Store、attention 和 presence。
4. 读取 result.json 和 A/B/Platform 日志，检查同一个 message_id 是否只产生一次业务记录，并区分本机接受、平台准入、收件方持久接收及业务结果。

**你只需参与（C+授权）**

- 第一次运行前确认测试只使用临时身份和本地 Platform；之后 Codex 可以反复执行，不需要你逐步点击。
- 如果要把同样的临时 Agent 接到远端 staging Platform，由你一次性授权目标 URL 和测试账户，Codex 负责执行和清理。

**环境**

E1。本地真实 Go Platform、两个 helper、临时 SQLite 和随机端口；不连接生产服务器。

**执行步骤**

旧 v1 好友、消息、已读与 presence 回归使用**旧版 helper 二进制**；新版 helper 的普通本机 `/api/v1/mq/store` 会按迁移策略拒绝，不能将其传给这条脚本：

~~~sh
python tests/integration/test_agent_web_parity_network.py \
  --helper PATH_TO_OLD_V1_HELPER --platform PATH_TO_PLATFORM
~~~

该脚本会建立 Alice/Bob 临时身份，验证 Web 控制身份、联系人请求、Bob 接受、双向消息、共享已读和 presence。新增的 v2 路径使用当前三件二进制，在本机隔离环境签发策略并测试双 helper；它不调用生产 Platform：

~~~sh
python tests/integration/test_v2_gateway_network.py \
  --platform PATH_TO_PLATFORM --helper PATH_TO_NEW_HELPER \
  --policy-tool PATH_TO_V2_POLICY_TOOL
~~~

v2 验收包含 `private` 握手、策略 epoch 切换、双端合规授权、网关回执和旧队列隔离；其中脚本执行的授权只模拟测试身份，不等于真实用户已同意。真实 Hermes 与 HTTPS 用户流程在 E2 单独验收，详见[增量测试计划](./RETEST_PLAN_2026-09-24.md)。

**流程**

~~~mermaid
sequenceDiagram
    participant T as 测试进程
    participant P as 临时 Platform
    participant A as Alice helper/Store
    participant B as Bob helper/Store
    T->>P: 启动并检查 healthz
    T->>A: 启动 helper，获取 Alice URN
    T->>B: 启动 helper，获取 Bob URN
    T->>P: 注册 A/B 身份
    T->>A: 提交 contacts.add(B)
    A->>P: 加密好友请求
    P->>B: 暂存并转交
    B->>B: 本地 owner 接受
    B->>P: 加密接受回执
    P->>A: 转交回执
    A->>B: 发送消息
    B->>A: 回复消息
    T->>A: 标记对方消息已读
    T-->>T: 检查双方 Store、attention、presence
~~~

上图是旧 v1 社交回归流程；v2 的签名策略、握手和网关路径按本节独立进程测试执行，不能以旧图或旧 helper 的结果代替。

**在项目中的环节**

~~~mermaid
flowchart LR
    TEST["tests/integration/test_agent_web_parity_network.py"] --> STORE["Python Runtime Store"]
    STORE --> HA["helper A"]
    STORE --> HB["helper B"]
    HA --> P["Platform Registry/MQ"]
    HB --> P
    P --> R["签名、加密、暂存、转交"]
    HA --> SA["Alice Agent 事实"]
    HB --> SB["Bob Agent 事实"]
~~~

**通过条件**

- Bob 接受后双方都为 connected；
- 旧 v1 回归中的 Web/native 消息使用同一个 message_id；v2 路径的消息与回执绑定相同的稳定 ID 和当前策略；
- 已读和提醒终态在双方一致；
- 重试、重放、错目标和伪造请求不产生第二次业务副作用。

---

## T03：Web 注册、添加 Agent、Console 配对

**目标**

证明用户可以从零开始注册 Web 账户、保存 Agent、创建 Console，并由本机用户明确授权 Web 读取能力。

**Codex 可代办（C/C+授权）**

1. 用临时账户自动注册、登录、保存 Agent、创建 Console 和检查私有 API。
2. 用 Playwright 或现有 full-stack smoke 驱动 Web 页面，保存截图、cookie 状态和 RPC 记录。
3. 运行 configure_hermes.py 的 check-only 计划，核对方法、主体、期限和 profile。
4. 如果 helper、Hermes profile 和密钥目录是临时的，Codex 可以启动 helper、重启测试 Gateway、点击“重新检查连接”并收集 capabilities。
5. 自动用 Bob 账户重复并验证账户隔离。

**你必须参与（H/C→H）**

- 提供实际 staging 登录方式、测试账户创建授权或浏览器登录确认。
- 确认配对的真实 profile、agent URN、Console URN 和有效期限；这一步不能由模型猜测。
- 如果使用你正在工作的 Hermes profile，必须由你确认不会替换原配置、身份或 mailbox；Codex 只执行 check-only 或已授权的临时修改。
- 当配对命令需要本机管理员权限、系统服务重启或外部认证时，由你执行/批准；之后 Codex 继续检查连接。

**环境**

E2 staging + Alice/Bob helper；第一次可以不启动第二个 Hermes，但真实配对必须使用实际 profile。

**配对检查命令**

~~~sh
python configure_hermes.py --remote \
  --pair-console CONSOLE_URN \
  --expires FUTURE_UTC_EXPIRY \
  --allow-web-actions --check-only

python configure_hermes.py --remote \
  --pair-console CONSOLE_URN \
  --expires FUTURE_UTC_EXPIRY \
  --allow-web-actions
~~~

**流程**

~~~mermaid
flowchart TD
    A["用户注册 Web 账户"] --> B["登录并输入 Agent URN"]
    B --> C["保存连接记录"]
    C --> D["创建 Console identity"]
    D --> E["复制 Console URN"]
    E --> F["用户在本机 pair"]
    F --> G["重启 helper/Gateway"]
    G --> H["Web 重新检查连接"]
    H --> I["读取 capabilities 和快照"]
    I --> J{"方法、主体、期限正确？"}
    J -- "否" --> K["显示未配对/权限不足"]
    J -- "是" --> L["进入 Agent 工作台"]
~~~

**在项目中的环节**

~~~mermaid
flowchart LR
    BROWSER["Web 浏览器"] --> AUTH["NextAuth 注册/登录"]
    AUTH --> DB["Web 用户和 Agent 连接"]
    DB --> CONSOLE["Console identity"]
    CONSOLE --> CTRL["/api/agents/:id/control"]
    CTRL --> MQ["Platform/MQ"]
    MQ --> HELPER["本机 helper"]
    HELPER --> PAIR["Hermes remote pairing"]
    PAIR --> SNAP["Agent 快照返回 Web"]
~~~

**通过条件**

- 保存 Agent 连接不等于获得访问权；
- Console 只能读取对应 Agent；
- capabilities 由 Agent 返回；
- 未配对、错误 Console、方法未授权、过期和撤销都明确失败；
- Alice 和 Bob 账户不能互相读取。

---

## T04：Web 添加联系人，Bob 用户接受或拒绝

**目标**

验证最重要的双边用户旅程：Alice 从 Web 提交联系人，v0.8.0 双方 Agent 在签名 `private` 策略下通过 v2 交付请求，Bob 用户做接受/拒绝决定，双方最终同步。Web 返回 `requested` 只证明 Alice Agent 已在本地持久排队，不证明 Platform 准入或 Bob 收件。

**Codex 可代办（C/C→H）**

- 创建 A/B 测试账户、浏览器会话和联系人测试数据。
- 对隔离生成的合成身份，Codex 可从预先约定的独立渠道核对双方完整 Ed25519 身份公钥，并分别在 A/B 原身份目录执行 `v2-pin-peer`；记录核对来源和 pin 结果，不从 Platform 搜索结果或 Web URN 推断主人身份。
- 自动打开联系人表单、填写姓名/别名/URN，验证未勾选确认时按钮禁用。
- 分别监听本地入队、v2 peer pin/会话、Platform 准入、Bob 持久收件和双方 Store，记录 request_id、contact_id、时间线和截图。
- Alice 提交后自动注入测试网络断开、刷新页面、恢复连接和执行原请求核实。
- 在 Bob 做完决定后，自动检查双方联系人、attention、outbox 和 Web 副本。

**你必须参与（C→H）**

- 如果用真实 Alice/Bob 身份验收，你分别以两边主人身份，通过平台之外的可信渠道核对**对方完整 Ed25519 身份公钥与真人/设备的绑定**，确认后再让各自 Agent 固定；Codex 不能把短 URN、平台注册表或网页授权当成该核对。
- Alice 的“提交联系人”如果要代表真实用户意图，由你确认表单并点击提交；Codex 可以先填好并暂停在确认点。
- 真人体验验收中，Bob 的接受和拒绝由你在 Bob 原生 Hermes 或 Bob Web 的具体请求卡中做出；合成身份的预定分支可由 Codex 操作，但不能记作真人决定。
- 需要验证两个决定时，你可以先做一次接受，再清理临时身份后做一次拒绝；不能把同一次请求的两个结果混在一起。

**环境**

E2 staging；两个 v0.8.0 helper、已验证的签名 `private` 策略、双方各自固定的策略根与 Platform Peer ID；最好两个 Hermes profile；A/B Web 账户；Alice Console 有 contacts.add，Bob Console 若从 Web 决定则有 contacts.respond。双方另须独立核对并固定**彼此的完整 Ed25519 身份公钥**；旧联系人 `trusted`、仅有 URN 或 Web 配对均不能替代。旧 v1 兼容路径按 T02 单独记录，v2 投递失败不能静默回退到 v1。

**流程**

~~~mermaid
sequenceDiagram
    actor Alice as Alice 用户
    participant WA as Alice Web
    participant A as Alice Agent
    participant P as Platform
    participant B as Bob Agent
    actor Bob as Bob 用户
    participant WB as Bob Web
    Alice->>A: 独立核对并固定 Bob 完整 Ed25519 公钥
    Bob->>B: 独立核对并固定 Alice 完整 Ed25519 公钥
    Alice->>WA: 打开联系人并填写 Bob URN
    WA->>WA: 勾选明确确认
    WA->>A: contacts.add
    A->>A: 本地持久排队好友请求
    A-->>WA: requested（仅本地排队）
    A->>P: 基于双向 pin 建立 v2 会话并发送加密请求
    P-->>A: v2 准入/入队回执（非 Bob 收件）
    P->>B: 转交 v2 请求
    B->>B: 验签、解密并持久收件
    B-->>P: 收件 ACK
    B->>Bob: attention/原生请求卡
    alt Bob 接受
        Bob->>B: 接受具体请求
        B->>P: contacts.respond(accept)
        P->>A: 转交接受回执
        A-->>WA: 同步 connected
        B-->>WB: 同步 connected
    else Bob 拒绝
        Bob->>B: 拒绝具体请求
        B->>P: contacts.respond(deny)
        P->>A: 转交拒绝回执
        A-->>WA: 同步 rejected/denied
        B-->>WB: 关闭待办
    end
~~~

缺少任一方的 peer pin、签名策略或 v2 会话时，`requested` 仍只表示本地排队；应查看本机发送状态和明确失败/隔离原因，不得宣称平台已准入、Bob 已收到，也不得静默降级为 v1。Web 到 Alice Agent 的受管控制请求与两 Agent 间的 v2 好友请求是两段不同链路。

**在项目中的环节**

~~~mermaid
flowchart LR
    UI["Web 联系人表单"] --> ROUTE["Web /api/agents/:id/control"]
    ROUTE --> RPC["受管 Web 控制请求"]
    RPC --> CMQ["Platform 控制路由"]
    CMQ --> HA["Alice helper"]
    HA --> SA["Alice Store 本地持久排队"]
    SA --> REQUESTED["requested：仅本地队列"]
    REQUESTED --> SESSION["双向 peer pin + v2 会话"]
    PINA["Alice 固定 Bob 完整公钥"] --> SESSION
    PINB["Bob 固定 Alice 完整公钥"] --> SESSION
    SESSION --> ADMIT["Platform v2 准入/入队"]
    ADMIT --> HB["Bob helper 验签解密"]
    HB --> SB["Bob Store 持久收件/待办"]
    SB --> HUMAN["Bob 用户决定"]
    HUMAN --> RESP["contacts.respond"]
    RESP --> ADMIT_R["回应的 Platform v2 准入/转交"]
    ADMIT_R --> SA
    SA --> PROJ["Web 加密副本/联系人视图"]
~~~

**通过条件**

- 页面打开不会自动写入；
- 未勾选确认时按钮禁用；
- 提交后显示 pending/requested，而不是 connected；它仅表示本地持久排队，不能当作 Platform 准入或 Bob 收件；
- 双方完整 Ed25519 身份公钥经独立渠道核对并各自固定后才交付 v2；缺 pin 或会话失败时无静默 v1 回退；
- 单独取得 Platform v2 准入、Bob 持久收件和 Bob 主人决定的证据；
- Bob 接受才进入 connected；
- Bob 拒绝后不得继续发送后续业务消息；
- 断线刷新后的重试保留原业务参数，不创建第二个联系人请求；
- 相同 ID 重放幂等。

---

## T05：双向消息、阅读和跨端提醒

**目标**

验证两个 Agent 之间的消息可以双向传输，且 Web、原生 Hermes、Agent inbox 和提醒状态一致。

**Codex 可代办（C/C+授权）**

1. 自动从 Web 发送带 RUN_ID 的纯文本，保存 request_id/message_id。
2. 自动驱动另一侧 Web、测试 helper 或协议 fixture，验证收件、回复、已读、重复 retrieve 和提醒关闭。
3. 自动执行停 helper、恢复 helper、刷新 Web 和后台同步，比较前后快照。
4. 自动反向运行 Bob Web → Alice Agent 的同一场景。

**你必须参与（H，仅真实用户体验）**

- 如果要验证 Bob 真正看到 Hermes 原生来信并理解后回复，必须由你在 Bob 的原生会话中阅读和回复；Codex 不能用脚本伪造“人已读”。
- 如果只验证协议和状态机，T02/fixture 已足够，Bob 的回复可以由 Codex 自动完成，不需要你重复操作。
- Alice Web 的“标记已读”可以由 Codex 操作；若要验证用户判断，可以由你确认页面内容后再点击。

**你参与的步骤（真人体验分支）**

~~~mermaid
flowchart TD
    S["Codex 准备 A/B 会话和测试消息"] --> Q{"本轮验收真人原生体验？"}
    Q -- "否" --> N["你无需操作；Codex 验证收发和状态"]
    Q -- "是" --> B1["切换到 Bob 的 Hermes profile"]
    B1 --> B2["阅读 Alice 来信，核对发送者、正文和未读提醒"]
    B2 --> B3["在 Bob 原生会话中理解并回复"]
    B3 --> A{"亲自验收 Alice Web 的阅读判断？"}
    A -- "是" --> A1["切换到 Alice Web，核对回复并点击标记已读"]
    A -- "否" --> A2["Codex 代办 Web 已读"]
    A1 --> R{"还验收反向原生体验？"}
    A2 --> R
    R -- "是" --> R1["切换到 Alice Hermes，阅读 Bob Web 来信并回复"]
    R -- "否" --> C1["Codex 代跑反向用例"]
    R1 --> C2["Codex 核对双方状态"]
    C1 --> C2
~~~

一人扮演两侧时，每次都要切回对应的 Hermes profile 和 Web 登录；Codex 的自动回复或已读可证明协议状态，不能记成真人阅读体验。

**环境**

E2 staging；两个 helper；两个 Web 账户；两个 Hermes profile；双方已 connected。

**流程**

~~~mermaid
sequenceDiagram
    actor Alice as Alice 用户
    participant WA as Alice Web
    participant A as Alice Agent
    participant P as Platform
    participant B as Bob Agent
    actor Bob as Bob 用户
    participant WB as Bob Web
    Alice->>WA: 发送 A-to-B 文本
    WA->>A: messages.send
    A->>P: 加密出站消息
    P->>B: 转交消息
    B->>Bob: inbox/attention 显示未读
    Bob->>B: Hermes 回复 B-to-A
    B->>P: 加密回复
    P->>A: 转交回复
    A-->>WA: 后台同步回复
    Alice->>WA: 标记已读
    WA->>A: inbox.mark_read
    A-->>WA: 已认证 read 结果
    A-->>WB: Bob 侧提醒终态同步
~~~

**在项目中的环节**

~~~mermaid
flowchart LR
    WEBUI["Web 消息 UI"] --> CONTROL["messages.send / inbox.mark_read"]
    CONTROL --> WSTORE["Web ControlRequest 和加密副本"]
    WSTORE --> MQ["Platform MQ"]
    MQ --> HA["helper A"]
    HA --> SA["Alice inbox/outbox"]
    MQ --> HB["helper B"]
    HB --> SB["Bob inbox/outbox"]
    SB --> HERMES["Bob Hermes 原生会话"]
    SA --> SYNC["Web background sync"]
    SB --> SYNC
    SYNC --> ATT["Web/Agent attention 状态"]
~~~

**通过条件**

- Platform ACK 只表示传输层接收，不表示用户已读；
- A/B 文本、收发人、message_id、in_reply_to 一致；
- Web 标记已读必须写回 Agent；
- 重启、SSE 重连、重复 retrieve 不产生重复消息；
- 一个端处理后，另一端提醒最终关闭。

---

## T06：双方用户都要决定的协作事项

**目标**

验证真正需要两边用户同意的场景，例如会议提议、资料分享或范围变化；证明 Alice 的同意不能代替 Bob 的同意。

**Codex 可代办（C/C→H）**

- 准备固定联系人、资料快照、时间范围、数量、期限和 proposal fixture。
- 自动读取 capabilities、collaboration.state、inbox、attention 和审计记录。
- 自动制造版本变化、过期、撤销、重复请求和迟到回调，并检查拒绝/失败状态。
- 在用户决定后自动对账 A/B Store、outbox、Platform 消息和 Web 副本，确认没有日历或外部工具副作用。

**你必须参与（C→H）**

- Alice 必须确认具体的 scope 和发起动作；Codex 可以把问题准备好并停在确认卡前。
- Bob 必须在具体审批卡中接受或拒绝；接受和拒绝两种分支要分开记录。
- 若用 Web approval.respond，必须由你确认 approval_id、内容、版本、期限后点击；Codex 不能把自然语言“可以”转换成批准。

**你参与的步骤（真人决定验收）**

~~~mermaid
flowchart TD
    S["Codex 准备具体提议和确认卡"] --> A1["以 Alice 身份核对接收人、范围、资料版本、时间和期限"]
    A1 --> A2["明确确认发起这一个提议"]
    A2 --> C["Codex 将对应审批卡呈现给 Bob"]
    C --> B1["切换到 Bob 原生会话或 Bob Web"]
    B1 --> B2["核对具体事项、范围、版本和期限"]
    B2 --> W{"使用 Bob Web 审批？"}
    W -- "是" --> W1["再核对 approval_id"]
    W -- "否：原生卡" --> D{"本轮 Bob 的独立决定"}
    W1 --> D
    D -- "接受" --> Y["在这张审批卡点击接受"]
    D -- "拒绝" --> N["在这张审批卡点击拒绝"]
    Y --> V["Codex 对账双方状态和审计记录"]
    N --> V
    V --> R{"接受与拒绝已分别验收？"}
    R -- "否" --> S2["Codex 创建新的独立提议"]
    S2 --> A1
    R -- "是" --> E["记录两次决定及观察到的结果"]
~~~

接受和拒绝必须用不同提议分别运行；Alice 的确认不能替 Bob 决定，聊天里说“可以”也不是审批。临时账户若预先约定固定选择，可由 Codex 点击并验证状态，但该路径不计为真人决定体验。

**环境**

E2 staging；两个真实 Hermes profile；两个 helper；匹配版本的 runtime、connector 和 Web；至少一侧允许 approval.respond。

**流程**

~~~mermaid
flowchart TD
    A["Alice Agent 准备事项 scope"] --> B["Alice 用户确认发起"]
    B --> C["A Agent 发送结构化 proposal"]
    C --> D["B Agent 持久化待办"]
    D --> E["Bob 用户查看具体审批"]
    E --> F{"Bob 决定"}
    F -- "接受" --> G["B 写入 approved_once"]
    G --> H["A/B 同步同一 proposal 版本"]
    F -- "拒绝" --> I["B 写入 denied"]
    I --> J["双方关闭后续执行"]
    D --> K["事项过期/版本变化/撤销"]
    K --> L["迟到决定失败，要求重新确认"]
~~~

**在项目中的环节**

~~~mermaid
flowchart LR
    HERMESA["Hermes A Host/InteractionPort"] --> RT["Runtime policy/Store"]
    RT --> APPA["Alice approval"]
    APPA --> OUTA["A Agent outbox"]
    OUTA --> MQ["Platform MQ"]
    MQ --> INB["B Agent inbox"]
    INB --> HERMESB["Hermes B Host/InteractionPort"]
    HERMESB --> APPB["Bob approval 或 Web approval.respond"]
    APPB --> RTB["B Runtime policy/Store"]
    RTB --> RESULT["proposal/approval/state 同步"]
~~~

**通过条件**

- 两边的审批记录绑定各自 owner、approval_id、版本和期限；
- Bob 拒绝后不发送后续业务消息；
- 迟到、过期、撤销或版本变化的接受失败；
- Web 聊天中的自然语言“可以”不能代替具体审批接口；
- 同意只改变授权/审批状态，不直接声称对方已完成工作。

---

## T07：Web conversation 与真实 Hermes 模型回合

**目标**

证明 Web 提交的会话请求确实由 Alice 的真实 Hermes 处理，并能区分提交、运行、完成、失败和结果不确定。

**Codex 可代办（C+授权）**

1. 使用已授权的 staging Web 和测试模型配置提交无副作用纯文本。
2. 自动轮询 submitted、running、completed、failed、interrupted，并保存 conversation/turn。
3. 自动关闭浏览器、重启测试 Gateway、注入网络超时，再查询原 conversation/turn。
4. 自动比较重试前后的请求 ID、密文和 Web/Agent 快照，检查没有新建请求。

**你必须参与（H）**

- 提供或确认模型账户、调用费用、测试 prompt 和“无外部副作用”边界。
- 如果要验证真实用户发起，Codex 可以填好 prompt 并暂停；由你确认并点击发送。
- 你需要对真实模型回答做最终语义判断；Codex 只能检查状态、关联字段和是否重复执行。

**你参与的步骤**

~~~mermaid
flowchart TD
    S["Codex 准备测试模型和无副作用 prompt"] --> H1["确认模型账户、调用费用、prompt 和无外部副作用范围"]
    H1 --> Q{"要验收本人从 Web 发起？"}
    Q -- "是" --> H2["核对 Web 中预填的 prompt 并点击发送"]
    Q -- "否" --> C1["Codex 代为提交请求"]
    H2 --> C2["Codex 跟踪真实 Hermes 回合与请求状态"]
    C1 --> C2
    C2 --> R{"得到真实模型的最终回答？"}
    R -- "是" --> H3["阅读回答，判断语义是否符合 prompt"]
    H3 --> H4["反馈通过或具体偏差"]
    R -- "否" --> C3["Codex 记录失败或结果不确定；暂不做语义判定"]
~~~

只有点击发送这一步是可选的真人发起验收；模型账户和费用边界、最终回答的语义判断仍由你确认。Bob 不参与本测试。

**环境**

E2 staging；真实 Hermes A、Gateway、helper、Web；模型使用测试账户或无副作用模型配置。Bob 不必参与本用例。

**流程**

~~~mermaid
sequenceDiagram
    actor Alice as Alice 用户
    participant WA as Alice Web
    participant P as Platform
    participant A as Alice RemoteBridge
    participant H as Hermes Gateway
    participant M as 测试模型
    Alice->>WA: 提交纯文字回显
    WA->>P: 加密 conversation.send
    P->>A: 转交控制请求
    A->>H: 绑定真实 host/session/turn
    H->>M: 调用模型
    M-->>H: 文本回复
    H-->>A: 持久保存完成结果
    A-->>P: control.response
    P-->>WA: submitted 后轮询 conversation.get
    WA-->>Alice: 显示最终回答和状态
~~~

**在项目中的环节**

~~~mermaid
flowchart LR
    CHAT["Web conversation UI"] --> API["/api/agents/:id/control"]
    API --> CACHE["ControlRequest 缓存"]
    CACHE --> MQ["Platform/MQ"]
    MQ --> BRIDGE["Hermes RemoteBridge"]
    BRIDGE --> HOST["HostPort/真实 Hermes 会话"]
    HOST --> MODEL["测试模型"]
    MODEL --> RESULT["conversation.get 完成结果"]
    RESULT --> PROJ["Web 加密工作台副本"]
~~~

**通过条件**

- submitted 不被显示为已完成；
- 最终文本来自真实 Hermes 回合；
- 结果不确定时复用原请求 ID，不自动新建请求；
- 后台同步不会自动调用 conversation.send；
- Hermes 重启后可以继续查询原 conversation/turn。

---

## T08：离线、断线、重启和持久恢复

**目标**

验证一侧 Agent、Platform 或 Web 暂时不可用时，另一侧不会误报成功；恢复后能补拉和继续核实。

**Codex 可代办（C/C+授权）**

1. 自动先同步联系人、消息和会话，保存基线快照。
2. 在隔离 staging 中依次停止 Bob helper、Platform、Web 或 Gateway，每次只改变一个故障变量。
3. 自动刷新 Web、读取 offline/needs_pairing/uncertain 状态并记录截图。
4. 自动恢复服务、等待后台 worker 同步、比较旧快照和原请求 ID。
5. 自动检查是否重复发送、丢失消息或误报完成。

**你只需参与（C+授权/H）**

- 明确允许 Codex 停止和重启的测试服务；这些动作只能针对 staging/临时进程。
- 如果测试服务器与生产共用主机或网络，由你先确认故障注入范围；Codex 不应自行操作生产服务。
- 只需要你在发现需要覆盖真实用户判断时查看恢复后的页面，不必逐次执行重启。

**环境**

E2 staging；完整服务器、A/B helper、Web、Hermes；备份已完成。

**流程**

~~~mermaid
flowchart TD
    A["先完成一次正常同步"] --> B["停止 Bob helper 或隔离网络"]
    B --> C["Alice 发送/查询"]
    C --> D["Web 保留旧快照并标离线"]
    D --> E["刷新页面或重启 Web"]
    E --> F["恢复 Bob helper"]
    F --> G["后台 worker 补拉"]
    G --> H["按原 ID 对账"]
    H --> I{"是否重复发送/丢失/误报成功？"}
    I -- "是" --> J["阻断发布并保留现场"]
    I -- "否" --> K["进入下一种故障"]
~~~

**在项目中的环节**

~~~mermaid
flowchart LR
    FAIL["网络/进程/服务故障"] --> HELPER["helper inbox/outbox"]
    FAIL --> MQ["Platform MQ/Registry"]
    FAIL --> WEB["Web sync worker"]
    HELPER --> RECOVER["retrieve、ACK、重试"]
    MQ --> RECOVER
    WEB --> RECOVER
    RECOVER --> STORE["Agent Store + Web 加密副本"]
    STORE --> UI["offline/last synced/uncertain UI"]
~~~

**通过条件**

- 离线旧数据可读，但不能显示在线；
- 未确认发送保留原 ID；
- 恢复后不产生第二次外部副作用；
- Platform、helper、Web 重启后数据和权限不丢；
- 已撤销或过期的配对不会因缓存恢复而重新生效。

---

## T09：撤销、过期和安全负向路径

**目标**

证明任何一方撤销或到期后，后续访问被阻止；伪造、越权、跨账户、重放和错误 Origin 都 fail-closed。

**Codex 可代办（C/C+授权）**

1. 创建临时、短期限的测试 pairing，并保存配对前状态。
2. 自动发送未授权 method、错误 Console、伪造 ID、跨账户 Agent、错误 Origin 和过期请求。
3. 运行 test_deployment_security.py，收集 HTTP 状态、Agent error code、日志和 ACK 结果。
4. 在测试 pairing 上执行 revoke，自动验证 Web 读写都被阻断而旧快照仍被标记保留。

**你必须参与（H）**

- 明确授权测试目标、测试账户和安全测试范围；不能把负向请求发到生产账户。
- 如果需要真实服务器管理员凭据、短期限 token 或证书操作，由你输入或批准，Codex 不保存 secret。
- 只由你决定是否把发现的安全失败升级为发布阻断；Codex 负责保留现场和复现步骤。

**环境**

E2 staging；A/B 测试账户；nginx、Web、Platform、安全测试脚本。

**执行入口**

~~~sh
python tests/integration/test_deployment_security.py
~~~

**流程**

~~~mermaid
flowchart TD
    A["创建短期限 Console pairing"] --> B["正常 capabilities/contacts.list"]
    B --> C["发送越权、伪造、跨账户和错误 Origin 请求"]
    C --> D["检查拒绝且不 ACK"]
    D --> E["等待期限到期或本机 revoke"]
    E --> F["再次读取、发消息、审批"]
    F --> G{"仍能成功？"}
    G -- "是" --> H["安全阻断，保留日志和数据库"]
    G -- "否" --> I["确认旧快照仅可查看并标记失效"]
~~~

**在项目中的环节**

~~~mermaid
flowchart LR
    ATTACK["匿名/伪造/越权请求"] --> NGINX["nginx 限流、Origin、请求体"]
    NGINX --> WEBSEC["Web session/账户/Agent 归属"]
    WEBSEC --> RPC["control protocol 关联校验"]
    RPC --> PAIR["Agent pairing/期限/方法"]
    PAIR --> STORE["Agent Store owner 校验"]
    STORE --> ACK["仅验证成功后 ACK"]
~~~

**通过条件**

- 未授权、过期、撤销请求不能读取或写入；
- 无效签名和错误关联不 ACK；
- 旧 Web 快照不能伪装成当前 Agent 在线；
- 日志不包含密码、私钥和完整 Console secret；
- 跨账户访问始终失败。

---

## T10：通知、手机布局和键盘可用性

**目标**

验证用户能在桌面、窄屏和键盘环境中完成双 Agent 关键操作，且通知不泄露正文。

**Codex 可代办（C/C+授权）**

1. 使用 Playwright 自动设置 1440px、390px、320px 视口，完成联系人、消息和审批路径。
2. 自动执行键盘导航、焦点检查、ARIA 检查、无横向溢出检查和页面错误收集。
3. 自动验证通知 payload 只含摘要，点击通知只导航到事项。
4. 生成截图和 accessibility/notification 报告。

**你只需参与（C→H）**

- 浏览器权限弹窗、真实手机、系统勿扰模式和 OS 通知中心的最终体验由你确认；Codex 可以先运行脚本并停在权限点。
- 你可以抽查一个 320px 和一个真实手机流程；其余尺寸由 Codex 自动覆盖。
- 如果通知权限已被系统永久拒绝，由你决定是否修改浏览器设置后重跑。

**你参与的步骤（系统与真实设备体验）**

~~~mermaid
flowchart TD
    S["Codex 准备提醒和桌面/窄屏自动检查"] --> P{"出现浏览器通知权限弹窗？"}
    P -- "是" --> H1["选择允许或拒绝，并判断提示是否易懂"]
    P -- "否" --> C1["Codex 检查当前权限状态"]
    H1 --> A{"当前通知权限允许？"}
    C1 --> A
    A -- "是" --> H2["查看 OS 通知中心，切换勿扰模式并观察真实表现"]
    H2 --> H3["核对摘要不泄露正文，点击后仅打开对应事项"]
    A -- "否" --> H0["可选：观察系统无通知；Codex 验证站内提醒"]
    H3 --> M1{"抽查 320px 操作？"}
    H0 --> M1
    M1 -- "是" --> H4["在 320px 窄屏完成关键操作并反馈可读性"]
    M1 -- "否" --> C2["Codex 自动覆盖 320px"]
    H4 --> M2{"抽查真实手机？"}
    C2 --> M2
    M2 -- "是" --> H6["在真实手机完成关键操作并反馈体验"]
    M2 -- "否" --> C3["Codex 保留桌面和窄屏自动化结果"]
    H6 --> R{"通知权限被永久拒绝？"}
    C3 --> R
    R -- "是" --> H5["决定是否修改浏览器设置并重跑"]
    R -- "否" --> E["反馈实际通知和操作体验"]
    H5 --> E
~~~

真实手机是可选抽查；320px/390px 布局、键盘导航和 ARIA 检查默认由 Codex 自动覆盖。通知点击不能代替接受好友、批准事项或发送消息。

**环境**

E2 staging；Chrome/Edge；可选真实手机；已产生好友请求、普通消息和审批提醒。

**执行入口**

~~~sh
node tests/integration/accessibility-browser.cjs
node tests/integration/notifications-browser.cjs
~~~

**流程**

~~~mermaid
flowchart TD
    A["产生好友/消息/审批提醒"] --> B["浏览器前台/后台切换"]
    B --> C["允许或拒绝通知权限"]
    C --> D["桌面和手机宽度操作"]
    D --> E["键盘导航和表单提交"]
    E --> F["点击通知，只打开对应事项"]
    F --> G{"是否泄露正文或绕过审批？"}
    G -- "是" --> H["阻断发布"]
    G -- "否" --> I["记录截图和可访问性报告"]
~~~

**在项目中的环节**

~~~mermaid
flowchart LR
    AGENT["Agent attention/inbox"] --> SYNC["Web background sync"]
    SYNC --> DB["加密通知副本"]
    DB --> PAGE["通知中心/工作台"]
    PAGE --> SW["Service Worker/Web Push"]
    PAGE --> A11Y["ARIA、键盘、响应式布局"]
    SW --> USER["用户查看并导航"]
~~~

**通过条件**

- 通知只含摘要，不含聊天正文或审批答案；
- 320px/390px 无横向溢出；
- 键盘能完成主要操作；
- 通知点击不会自动接受、批准或发送消息；
- 浏览器拒绝通知时仍能使用站内提醒中心。

---

## T11：服务器升级、备份、恢复和线上烟测

**目标**

证明发布不会破坏已有账户、Agent 配对、Web SQLite、Platform 数据和证书入口。

**Codex 可代办（C/C+授权）**

1. 读取版本、镜像、配置和数据库状态，生成发布前清单。
2. 在 staging 创建 Web SQLite、Platform 数据和配置备份，并校验备份可读。
3. 在隔离 staging 执行升级、迁移、T03～T06 最小回归和回滚演练。
4. 收集 compose ps、nginx -t、healthz、服务日志、smoke 结果和版本差异。
5. 在你批准的线上只读范围内运行官网、healthz、登录/登出、smoke 工作台和快照读取。

**你必须参与（H）**

- 明确发布窗口、目标主机、备份位置和回滚版本；生产升级/回滚不能由 Codex 自行决定。
- 提供或输入服务器凭据、证书权限和 secret；Codex 只使用授权后的命令，不把 secret 写入报告。
- 在 staging 验证通过后，由你做最终发布批准；生产失败时由你批准停止流量或回滚。
- 线上 smoke 的测试账户、测试 Console 撤销和数据清理由你确认完成范围，Codex 负责执行只读检查和记录。

**环境**

E2 staging 必需；E3 production 只做无副作用烟测。需要 Docker、备份目录、证书和服务器运维权限。

**流程**

~~~mermaid
flowchart TD
    A["记录版本/镜像/配置"] --> B["备份 Web、Platform、.env 和证书配置"]
    B --> C["启动 staging 旧版本"]
    C --> D["执行升级和迁移"]
    D --> E["健康、登录、同步、消息、撤销回归"]
    E --> F["从备份启动隔离回滚"]
    F --> G{"新旧数据都可读？"}
    G -- "否" --> H["停止发布并恢复备份"]
    G -- "是" --> I["执行线上只读 smoke"]
    I --> J["记录发布证据并清理 smoke 身份"]
~~~

**在项目中的环节**

~~~mermaid
flowchart LR
    SOURCE["根仓库/子模块提交"] --> IMAGE["Web/Platform 镜像"]
    SOURCE --> CONFIG["Compose/nginx/Platform 配置"]
    IMAGE --> DEPLOY["服务器部署"]
    CONFIG --> DEPLOY
    DEPLOY --> MIGRATE["Web SQLite 迁移"]
    MIGRATE --> DATA["Web/Platform 持久卷"]
    DATA --> BACKUP["备份/恢复/回滚"]
    DEPLOY --> SMOKE["HTTPS/healthz/只读烟测"]
~~~

**通过条件**

- 升级不删除用户、连接、消息、配对或密钥；
- 回滚环境可以读取备份；
- nginx 配置、证书、ACME、限流和请求体限制正常；
- 线上烟测不发送好友请求、消息或模型任务；
- 每次发布都有版本清单、日志、结果和回滚位置。

---

## T12：从干净环境安装 agent-comm 并完成连接

**目标**

验证一台没有安装过 agent-comm 的新环境，可以使用与系统匹配的接入包完成校验、安装 helper/runtime/Hermes connector、创建新身份、连接 staging Platform、在 Web 完成主人确认，并最终从 Web 看到真实 Agent 状态。

这里的“干净环境”是一个可工作的 Hermes 测试安装，拥有独立 Python 环境和新 profile：解释器中没有 `agent-comm-runtime`/`hermes-platform-agent-comm`，profile 中没有旧 helper 身份、mailbox、协作库、插件或远程 pairing。只创建空 profile、继续使用已装 connector 的 Python，不能算干净安装。当前接入包以“已有可用 Hermes”为前提，Codex 可以先在 VM/容器或本机独立目录准备纯 Hermes 基线，再保存快照；每条失败用例都从这个基线开始。

按安装包来源分两条独立轨道记录结果：

| 轨道 | 本轮实际对象 | 通过条件的边界 |
| --- | --- | --- |
| r2 旧版兼容首装 | 测试冻结时官网 `release-manifest.json` 指向的 r2 ZIP 和包内旧版 helper | 验证 r2 用户能下载、校验、安装并完成 Web 配对和旧协议兼容流程；不能记为 v2 新版安装已通过。 |
| v2 发布候选包首装 | 单独构建、签名并记录摘要的候选 ZIP；在实际发布前不冒充官网包 | 除安装与 Web 配对外，还须在隔离 staging 部署有效签名策略，并从独立可信渠道核对、固定策略根、Platform Peer ID 和对端完整身份公钥。未具备这些前提时，新 helper 拒绝普通 Agent 间发送是预期结果，不能靠重建身份或退回 v1 使测试“通过”。 |

**状态更新（2026-09-24）：** 生产已启用签名 `private`、`allow_v1=true`、epoch 1；本节原先记录的“策略未启用”仅适用于切换前。E3 公网保持只读烟测，候选包的写入式双 Agent 验收仍在隔离 E2-V 完成；只有官网清单实际发布 v0.8.0 并从公网下载完整 ZIP 再首装验收，才能声称用户可获得 v2 接入包。源码安装或本地模拟通过不得替代候选 ZIP 与公开 ZIP 各自的首装证据。

**Codex 可代办（C/C+授权）**

1. 准备独立 Hermes 安装/解释器/profile，记录安装前包清单与文件清单，确认旧 runtime/connector 不存在；检查 Python 3.11+、Hermes 宿主依赖、系统架构、端口和网络。临时 OS 用户也要有独立解释器，不能继承机器全局的 agent-comm 包。
2. 先选择并标记上述轨道。r2 兼容回归使用已冻结的官网 ZIP 与外部 `release-manifest.json` 证据；v2 发布候选包取独立候选清单与完整 ZIP。公开清单切换后，再新增一条**当时真实公网下载的 v2 ZIP**首装记录。分别核对 ZIP 摘要、包内 `SHA256SUMS.json`、helper 和两个 wheel；源码脚本目录不能代替任一接入包。
3. 使用测试 Hermes 的 Python 运行 `install.py --check-only`。该命令验证包内文件、wheel 元数据及 helper 对应的 OS/CPU；它不证明 Hermes 宿主依赖完整。跨平台发布构建器可显式加 `--cross-platform-check` 做只读完整性检查，首装测试不得使用该选项绕过宿主匹配校验。
4. 使用指定的临时 Hermes home、解释器、staging HTTPS origin、helper 端口和 1 天期限执行 `onboard_hermes.py`；它内部执行安装，然后初始化 helper、签名注册并生成 claim。首装主路径不预先手动安装，以便覆盖真实自动安装过程。
5. 打开测试账户的 claim 页面，核对已登录账户、Agent、方法与到期时间。新增 Agent 权限的浏览器操作需要在点击时确认；你确认本次页面列出的范围后，Codex 可代为点击。真人 UX 验收时则由你亲自检查和点击。Console URN 在完成后的配对状态中核对，当前 claim 页面不展示它。
6. 轮询 `--status`、helper `/info`、Platform 注册、Gateway 状态及 Web capabilities；等待本机连接完成后发送已约定的纯文字 Web 控制回显，核对真实回答与 completed，再验证重复运行和进程重启恢复。若测试候选 v2 Agent 间消息，还要单独核对两端 `/api/v2/disclosure` 和收件结果：签名策略、可信固定及本机许可缺失时不得发送。`platform_queued` 或 Web 控制回显不能代替对端 Agent 完成。
7. 保存版本、摘要、URN、权限、期限和脱敏日志。`onboarding.json` 含 poll secret，只读必要状态字段，不整份复制进报告。完成证据采集后撤销测试配对，停止本轮 Gateway/helper/后台任务及服务，再清理运行目录。

**你需要参与的部分（H；新增网页授权需当次确认）**

- 提供测试服务器/账户的访问方式及模型凭据；本机临时目录和独立环境的创建、包校验与安装由 Codex 完成。只有新建付费资源或需要额外系统权限时再由你决定。
- 约定测试授权范围：例如本轮测试账户允许列出的 Web 方法、1 天期限和一次纯文字模型回显。浏览器中新增 Agent 权限需要在当次 claim 点击前确认；收到确认后 Codex 可完成后续确定性步骤。
- 做一次新用户体验验收时，你在 Codex 已打开的 claim 页面检查文案、选择确认，再反馈是否知道授予了哪些权限、是否看得懂等待/失败状态。后续确定性回归由 Codex 复现这些操作。

**环境**

E2 的已有阿里云测试服务；本机独立安装或可恢复快照的 VM/容器；可工作的纯 Hermes、独立 Python 和 profile；所选轨道对应系统的完整接入 ZIP；测试 HTTPS 域名、Web 账户及模型访问。候选 v2 Agent 间消息另需隔离且已启用签名策略的 Platform、带外核对的根/Peer ID/双方身份公钥，以及合规模式下双方主人对精确策略的本机授权。第一轮覆盖实际使用的 OS；声称支持的其它系统在对应原生环境另跑，不能把 Linux 容器通过当作 Windows/macOS 通过。

**推荐执行步骤**

下面为 PowerShell 示例；在解压的完整接入包目录执行，先把路径和域名替换为预检确认的测试值。POSIX shell 使用相同参数调用该 Hermes 解释器。

~~~powershell
$testHermesPython = 'C:\path\to\clean-hermes\.venv\Scripts\python.exe'
$testHermesProfile = 'C:\path\to\RUN_ID\agents\alice\hermes-profile'
$testPlatformOrigin = 'https://staging.example'

# 仅验证完整接入包
& $testHermesPython .\install.py --check-only
if ($LASTEXITCODE -ne 0) { throw 'Bundle verification failed' }

# 安装由 onboard 内部执行；返回 claim_url 后后台任务等待 Web 确认
& $testHermesPython .\onboard_hermes.py --python $testHermesPython --hermes-home $testHermesProfile --platform $testPlatformOrigin --allow-web-actions --pair-days 1 --port 45042
if ($LASTEXITCODE -ne 0) { throw 'Onboarding failed; preserve evidence' }

# Web 确认后查询状态；pending/approved 不能作为成功
& $testHermesPython .\onboard_hermes.py --python $testHermesPython --hermes-home $testHermesProfile --platform $testPlatformOrigin --status
~~~

首装主路径通过后，在同一测试 profile 重跑同样的接入命令，必须保留 URN/mailbox/配对范围。随后分别停止并恢复本轮进程，再验证 Web 读取和模型回复；进程恢复与 OS 开机自启分别记录，不能把前者通过当作后者通过。

至少另做以下分支，各用纯 Hermes 快照/独立环境：

| 分支 | Codex 操作 | 期望结果 |
| --- | --- | --- |
| 包被篡改 | 修改副本中的 wheel/helper 字节后运行 `--check-only` | SHA256 不匹配，非零退出；没有安装或身份/配对变更 |
| 错误 OS/架构包 | 在 Windows 用完整 Linux 包执行 `install.py --check-only`；发布构建器另试显式 `--cross-platform-check` | 普通校验在安装前拒绝 OS/CPU 不匹配；构建器只读完整性检查可通过，不安装或建立配对 |
| 宿主不兼容/缺依赖 | 使用不含有效 Hermes 或缺少必要依赖的解释器执行安装 | 明确失败，未成功安装/配对，不修改现有 Hermes 环境 |
| 打开 claim 但不确认 | 读取页面和状态，等真实票据期限到期，再重跑 | 安装/helper 可以已完成，但不建立远程配对；过期不报成功；重跑生成新票据且保留同一 Agent 身份 |
| 端口占用 | B 指定已被 A 身份占用的 helper 端口 | 报身份/端口冲突，不接管 A；换空闲端口后可恢复 |

手动安装路线单独从纯 Hermes 基线执行 `install.py`，再按[接入包说明](../../tools/release/early_access/README.md)初始化 helper、合并配置及配对，记录为 T12 的另一条结果。它不能替代上面自动接入主路径。

**流程**

~~~mermaid
flowchart TD
    A["Codex 准备纯 Hermes、独立 Python 和新 profile"] --> B["检查无旧包、系统架构和网络"]
    B --> C["按冻结 r2、v2 候选或已发布 v2 轨道核对清单与 SHA256"]
    C --> D{"校验通过？"}
    D -- "否" --> E["停止，不安装"]
    D -- "是" --> F["install.py --check-only"]
    F --> G["onboard 内部安装 runtime 与 connector"]
    G --> H["创建新身份，启动接入包内的 helper"]
    H --> I["Platform 注册并生成 claim URL"]
    I --> J["Codex 按已约定脚本核对；真人 UX 时交给你"]
    J --> K{"在对应账户确认 Web claim？"}
    K -- "否" --> L["保持 pending/过期，不写入配对"]
    K -- "是" --> M["验证签名授权并合并临时 profile"]
    M --> N["启动 Gateway，检查 agent_comm connected"]
    N --> O["Codex 做 capabilities、同步和安全回显"]
    O --> P["验证重跑与恢复，保存脱敏证据"]
    P --> Q["撤销测试配对，停本轮服务后清理"]
~~~

**在项目中的环节**

~~~mermaid
flowchart LR
    BUNDLE["冻结 r2、v2 候选或已发布 v2 ZIP / 对应清单"] --> VERIFY["install.py 校验"]
    VERIFY --> PY["Hermes Python runtime + connector"]
    BUNDLE --> HELPER["onboard 启动包内 Go helper"]
    HELPER --> REGISTER["Platform Registry 注册新 URN"]
    REGISTER --> CLAIM["Web onboarding claim"]
    CLAIM --> PAIR["本机 pairing / allowlist / 期限"]
    PAIR --> GATEWAY["Hermes Gateway + agent_comm"]
    GATEWAY --> RPC["加密 control RPC / MQ"]
    RPC --> WORKSPACE["Web 工作台、同步和 conversation"]
~~~

**通过条件**

- 安装前包清单与 profile 清单证明没有复用旧 runtime/connector、身份、pairing 或 mailbox；
- ZIP 与其所属轨道的清单一致，包内文件符合 SHA256；篡改在安装前失败，OS/架构核验单独记录；冻结 r2、v2 候选和实际已发布 v2 不合并为一个通过结果；
- runtime 和 connector 安装到运行 Hermes 的同一个 Python；
- helper 生成新 URN 并在 staging Platform 注册，helper 只绑定 loopback；
- claim 页面显示真实 Agent、方法与短期限，正确账户确认后才建立配对；完成后核对 Console URN，错误账户/未确认场景没有获得权限；
- Gateway 报告 agent_comm connected，Web 能读取 capabilities 并完成安全回显；
- 候选 v2 Agent 间消息另有签名策略、带外可信固定、双方披露状态和最终收件证据；缺少条件时明确记录拒绝原因，不将旧 v1、Web 控制通道或模拟授权算成真实合规验收；
- 重跑不创建第二个身份或无意扩权，未确认/过期 claim 不会被当作成功；
- 安装日志、配置备份和临时数据可定位并能安全清理。

---

## 推荐执行顺序

第一次建立完整测试时按以下顺序执行：

1. T00：环境、版本和隔离预检。
2. T01：组件和安全基线。
3. T02：两个临时 Agent 的协议闭环。
4. T12：从干净环境安装 agent-comm，Codex 按已约定脚本完成 claim；首次 UX 由你体验一次。
5. T03：Alice/Bob Web 账户、Agent 连接和 Console 配对。
6. T04：Web 添加联系人，Bob 接受和拒绝各一次。
7. T05：双向消息、已读和提醒。
8. T06：双方都需要决定的协作事项。
9. T07：真实 Hermes conversation。
10. T08：离线、断线、重启和恢复。
11. T09：撤销、过期和安全负向路径。
12. T10：通知、手机和键盘。
13. T11：staging 升级、备份、恢复、回滚，再做线上只读烟测。

任一测试出现以下情况就停止推进并保留现场：

- 一方显示成功，但另一方没有相同的 Agent 事实；
- 同一个稳定 ID 重放产生第二条业务记录；
- 用户已经拒绝，系统仍继续执行；
- 平台 ACK 被 UI 当成对方接受或业务完成；
- 过期/撤销后缓存仍可执行写操作；
- 无法从日志和快照还原两边用户分别做了什么决定。

每次测试最终写入 result.json，最少包含：

~~~json
{
  "run_id": "20260922-120000-ab12",
  "test_id": "T04",
  "environment": "E2-staging",
  "actors": {
    "alice_agent_urn": "...",
    "bob_agent_urn": "...",
    "alice_console_urn": "...",
    "bob_console_urn": "..."
  },
  "decisions": [
    {"actor": "alice", "kind": "submit", "id": "...", "at": "..."},
    {"actor": "bob", "kind": "accept", "id": "...", "at": "..."}
  ],
  "status": "passed",
  "evidence": ["screenshots/...", "logs/...", "snapshots/..."]
}
~~~
