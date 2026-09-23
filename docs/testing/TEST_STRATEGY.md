# Agent Collaboration 系统测试方案

维护基准：2026-09-22。本文把 SDK、Platform、Web、Hermes 和部署入口放进同一套测试门禁，适用于本仓库当前固定的子模块版本。它定义环境、数据、用户旅程、自动化入口、真实验收和发布证据；组件内部的具体断言仍留在各自子模块。

## 1. 测试目标和判定原则

测试要证明：

1. **功能正确**：身份、加密收发、通讯录、好友握手、消息、协作事项、审批、远程会话和提醒都能完成，并且状态含义正确。
2. **权限正确**：Web 只能使用 agent 本机明确配对的方法；过期、撤销、越权、重放、伪造和跨账户访问必须失败。
3. **恢复正确**：网络中断、进程重启、数据库迁移、服务升级和结果不确定时，数据不丢失、不重复产生外部副作用，用户能继续核实原请求。
4. **体验可用**：用户能完成注册、添加连接、本机配对、网页添加联系人、接受/拒绝好友、发消息、标记已读和处理审批；桌面、手机窄屏、键盘和错误状态都可理解。

测试中必须区分这些状态：

~~~text
本机已接受  !=  Platform 已入队  !=  对方 agent 已收到
对方已收到  !=  对方已接受     !=  对方 agent 已完成业务工作
Web 显示旧快照 != agent 当前在线或当前配对仍有效
~~~

每一条端到端用例至少保存请求 ID、agent/console URN、时间、最终业务状态和日志路径。HTTP 200、submitted、accepted 或 MQ ACK 不能单独作为业务成功判定。

逐项执行步骤、每一步由 Codex 还是你完成、每项测试的 Mermaid 流程图和项目环节图见[测试执行指南](./TEST_EXECUTION_GUIDE.md)。本文保留测试分层和发布门禁，执行时以该指南中的 T00～T12 为准。

## 2. 测试拓扑

服务器上的测试部署必须使用独立 Compose project、独立命名卷、独立域名或子域名、独立 .env 和独立 Platform 身份；不能把测试身份写入生产数据卷。现有阿里云 ECS 可以作为 staging 主机：若该 ECS 专用于 staging，可以直接部署；若与生产共用，必须让现有 nginx 或负载均衡把 staging 子域名路由到独立 Web，并用 staging Compose override 移除/改名固定容器名、改用不冲突的端口、卷、数据库和密钥。当前根目录 Compose 固定了 agent-nginx、agent-web、agent-platform 三个 container_name，不能只加 `-p agent-staging` 就与生产并行启动。

~~~text
浏览器 / Playwright
        │ HTTPS
        ▼
测试服务器：nginx ── Web ── Platform(Registry/MQ/Relay)
                                      ▲
                                      │ HTTPS MQ / Registry
本机：Hermes A ── helper A ────────────┘
      （可选）Hermes B / helper B，或第二个临时 helper 身份
~~~

建议准备四个环境：

| 环境 | 目的 | 数据与身份 | 运行频率 | 发布门槛 |
| --- | --- | --- | --- | --- |
| E0 静态/单元 | 协议、策略、认证、数据库和 UI 契约 | 临时目录、临时 SQLite | 每次提交 | 全部通过 |
| E1 本地组合 | 真实 Go Platform + helper + Python runtime + 构建后的 Web | 随机端口、临时密钥和 SQLite | 每个合并请求/每日 | P0 全通过 |
| E2 服务器 staging | HTTPS、nginx、Docker 卷、真实本机 Hermes、干净接入设备 | test-* 账户、测试域名、独立 Platform 身份、可回滚备份 | 每个候选版本；接入包/连接方式变更时重跑 T12 | P0/P1 全通过 |
| E3 线上烟测 | 部署后健康、登录、连接、同步和撤销 | 单独 smoke 账户和短期身份 | 每次部署/定时 | 失败立即停止发布或回滚 |

本机只有一个 Hermes 时，E1/E2 用第二个临时 helper 身份模拟 Bob；只有涉及真实宿主会话、原生确认和模型回复的用例使用 Hermes A。若要验证双边真实 agent 行为，再为 Bob 建立第二个 Hermes profile，不能复用 Alice 的 profile、密钥、mailbox 或协作库。

### 2.1 两个 Agent 的隔离方式

两个 Agent 的最小隔离单元是“身份、进程、数据目录、端口和 profile”的组合，而不是两个 Web 账户。一次运行使用独立目录，例如：

~~~text
build/test-runs/<RUN_ID>/agents/alice/
  keys/ mailbox/ collaboration.sqlite3 remote.sqlite3 hermes-profile/ logs/
build/test-runs/<RUN_ID>/agents/bob/
  keys/ mailbox/ collaboration.sqlite3 remote.sqlite3 hermes-profile/ logs/
~~~

Alice 和 Bob 必须分别拥有 helper 密钥、Agent URN、Peer ID、mailbox、runtime 状态、远程配对记录、Hermes profile、Web 账户和 Console URN。helper 监听不同的 loopback 端口（例如 45042 和 45043），每个 inbox 只允许一个 active connector/consumer；`allow_from` 只写本次确实需要的 Agent 或 Console 明确 URN，不使用通配符。禁止复制另一边的 profile、密钥、SQLite 或 mailbox 来“快速生成”第二个 Agent。

Codex 可以创建和清理上述临时目录、启动两个 helper、分配随机端口并检查跨身份访问；你只需要提供或授权使用测试设备、测试账户和 staging 资源。需要两边都是真实 Hermes 宿主会话时，必须使用第二个 Hermes profile、虚拟机、容器或另一台机器；第二个 helper 身份只能覆盖协议和状态机，不等价于第二个真实用户宿主。

## 3. 测试数据和隔离规则

- 每次运行生成 RUN_ID=YYYYMMDD-HHMMSS-<random>，日志、截图、数据库和报告写入 build/test-runs/$RUN_ID/；build/ 已被忽略，不上传用户资料。
- 账户使用 owner-a@workspace.invalid、owner-b@workspace.invalid 等 .invalid 地址；密码只在测试环境生成，不从生产复制。
- Alice、Bob、Console 分配不同的 helper keys、URN、Peer ID、mailbox 和 runtime state。不要在测试中运行真实身份的 init，也不要删除真实 Hermes 数据目录来“清理”测试。
- 测试服务器保留部署前清单：Git 提交、子模块提交、镜像 digest、.env 指纹（只记录哈希）、卷名、DNS、证书有效期和备份路径。
- 故障注入优先停测试 helper、断开测试容器网络或暂停测试进程；不要对生产域名做限流、重放或故障注入。
- 模型输入只使用无副作用的纯文字任务，例如“原样回复蓝色纸船”。禁止让模型发送真实消息、修改真实文件、调用付费 API 或创建日历事件。

## 4. 分层测试入口

### 4.1 SDK、runtime 和 Hermes connector

在 agent-comm-platform/agent-comm 根目录：

~~~sh
go test ./...
python -m unittest discover -s python/tests -q
~~~

在安装了真实 Hermes 依赖的同一 Python 环境中：

~~~sh
python -m unittest discover -s connectors/hermes-platform/tests -v
~~~

重点覆盖身份/签名/加密、Registry、可靠消息、P2P/HTTP、helper inbox/outbox、重启和 ACK 顺序；Runtime 的 describe、state、inbox、资料、联系人、事项、动作、确认、发送、撤销和端口注册拒绝；五类业务能力 share_slots、share_resource、propose_meeting、accept_meeting、send_text；Hermes 的 host/context、原生问题卡、确认租约、会话隔离、完成回调、稳定 message ID、断线重连；好友请求、消息已读、presence、attention、worker 和跨 owner 隔离。

真实 Platform/helper 组合检查：

~~~sh
python tools/test_helper_platform.py \
  --helper build/agent-comm-helper \
  --platform /absolute/path/to/platform
~~~

agent/platform_real_test.go 只有在明确配置远端测试平台和测试 agent 时才开启；日常回归不得设置 TEST_REAL_PLATFORM=true。

### 4.2 Platform

在 agent-comm-platform 根目录运行 go test ./...，并纳入候选版本：

- Registry：签名注册、解析、TTL、所有权、重放、持久化和重启恢复。
- MQ：签名/加密消息、收发与 ACK、幂等 ID、容量/TTL、未授权访问、跨 URN 隔离、数据库恢复。
- Relay/libp2p：保留和释放、时长/数量限制、断线、错误路由和公网地址。
- HTTP/admin：管理令牌、审计、限流、请求体上限、代理头覆盖、错误码和数据脱敏。
- 部署配置：缺失 NEXTAUTH_SECRET、PLATFORM_ADMIN_TOKEN 或 NEXTAUTH_URL 时 Compose 必须失败；Platform 的 8080 不对公网开放。

在 agent-comm-platform/agent-comm 根目录运行指定测试 Platform 的传输验证：

~~~sh
go run ./tests/integration/platform_http -target http://127.0.0.1:8080
go run ./tests/integration/platform_p2p -target /ip4/127.0.0.1/tcp/45041/p2p/PLATFORM_PEER_ID
~~~

### 4.3 Web

在 agent-collaboration-web 根目录：

~~~sh
npm ci
npm run db:generate
npm test
npm run lint
npm run build
~~~

当前基线的 npm test 有 173 个测试，覆盖共享 client contract、协议签名/加密、NextAuth、Origin/输入大小、密码升级、真实 SQLite 迁移、远程控制、同步 worker、重试和推送；数量变化以源码为准，不能把数量当作覆盖率。

浏览器和本地 fixture：

~~~sh
node tests/integration/workspace-fixture.cjs
# 另一个终端
node tests/integration/workspace-browser.cjs
node tests/integration/workspace-resilience.cjs

# 变更用例：重新以 MUTATION_FIXTURE=1 启动 fixture
node tests/integration/workspace-mutations-browser.cjs

# 双边好友/消息/已读：以 SOCIAL_FIXTURE=1 启动 fixture
node tests/integration/workspace-social-browser.cjs

# 可访问性/窄屏
node tests/integration/accessibility-browser.cjs
~~~

这些脚本只监听 loopback、使用临时账户和 SQLite，不代替 E2 的真实 HTTPS 验收。Playwright 需要可用 Chromium；使用 PLAYWRIGHT_MODULE 和 CHROME_EXECUTABLE 指定现有安装。

### 4.4 跨组件本地组合

先构建 Web、Platform 和 helper，再运行：

~~~sh
python tests/integration/test_remote_control_network.py \
  --helper PATH_TO_HELPER --platform PATH_TO_PLATFORM

python tests/integration/test_agent_web_parity_network.py \
  --helper PATH_TO_HELPER --platform PATH_TO_PLATFORM

python agent-collaboration-web/tests/integration/full_stack_smoke.py \
  --helper PATH_TO_HELPER --platform PATH_TO_PLATFORM --node PATH_TO_NODE
~~~

三者分别验证真实加密 RPC、方法权限/撤销、自动注册、网页添加联系人、好友接受、双端消息、共享已读、在线状态、数据库投影和 Web 账户隔离；都不调用模型或生产服务。

### 4.5 部署安全和入口

在有 Docker 的环境运行：

~~~sh
python tests/integration/test_deployment_security.py
~~~

它验证缺少密钥时 Compose 拒绝启动、nginx 请求体和限流、代理头覆盖、Web 容器降权、旧卷文件保留和数据库属主。需要 Web 容器检查时设置 WEB_TEST_IMAGE；已有 nginx 镜像时设置 NGINX_TEST_IMAGE。

### 4.6 干净环境安装和首次接入

T12 使用一个没有 agent-comm helper、runtime、connector、mailbox、collaboration 数据库和 remote pairing 的新 Hermes profile；当前接入包的前提是 Hermes 本身已经能启动。如果连 Hermes 也要从零安装，应先单独准备操作系统/Hermes 安装测试，再执行 T12。

在与系统匹配的完整接入包目录中执行：

~~~sh
python install.py --check-only
python install.py
python onboard_hermes.py \
  --python PATH_TO_HERMES_PYTHON \
  --hermes-home PATH_TO_CLEAN_HERMES_HOME \
  --platform https://staging.example \
  --allow-web-actions \
  --pair-days 1 \
  --port 45042
python onboard_hermes.py \
  --python PATH_TO_HERMES_PYTHON \
  --hermes-home PATH_TO_CLEAN_HERMES_HOME \
  --status
~~~

Codex 负责检查系统架构、Python、包清单和 SHA256，执行安装、启动 helper、轮询 `/info`、注册、Gateway、SSE、capabilities 和状态报告；你负责提供或授权干净环境，打开 claim URL，在已登录 Web 中确认 Agent、方法和过期时间；Console URN 在完成后的配对状态中核对，并由你决定真实模型提示或费用。至少补做篡改校验值、错误系统包和打开 claim 但不确认三条失败路径；篡改/错误包必须在安装前失败，未确认 claim 即使 helper 已安装也不能建立有效配对或访问 Web 能力，且不能修改原 profile。

## 5. 能力到测试的追踪矩阵

| 能力/边界 | 自动化基线 | E2 真实验收 | 关键通过条件 |
| --- | --- | --- | --- |
| 身份、签名、加密、URN/Peer ID | Go、Web protocol、跨语言 fixture | 健康后注册 Alice/Bob，校验 Registry 签名 | 伪造字段、错目标、重放均失败且不 ACK |
| Registry / MQ / Relay | Platform Go、helper-platform、HTTP/P2P | 服务器重启后查询、存取、补拉 | 消息可恢复，ACK 顺序正确，TTL/限额生效 |
| Runtime 端口与策略 | Python runtime/worker/ports | Hermes 原生对话提出真实 scope 变化 | 未注册/未授权能力为 unsupported，越界询问或拒绝 |
| 远程配对/RPC | test_remote_control_network.py、Web control/onboarding | Web 创建 Console → 本机 pair → 连接检查 | 只允许明确方法；期限/撤销立即阻断后续读写 |
| Web 登录/账户隔离 | npm test、full-stack smoke | A/B 账户浏览器登录、刷新、换设备 | A 不能读取 B；匿名私有 API 返回 401 |
| 网页添加联系人 | mutation browser、parity network | Alice Web 填 Bob URN；Bob agent 接受/拒绝 | 请求只提交一次；刷新/断线保留原 ID；双方最终 connected 或 rejected |
| 消息和已读 | social browser、Python social、parity | Web→native、native→Web 往返并双端标已读 | inbox、Web 副本、attention 最终一致 |
| 协作事项/审批 | Python collaboration/attention、Web mutation | Hermes 原生确认 + Web approval.respond | 批准只改变具体审批；不伪造主人、不自动发业务消息 |
| Hermes conversation | connector tests、control tests | Web 发送纯文字，等待真实模型完成 | submitted 与最终回答分开；不确定重试复用同一 ID |
| 后台同步/离线 | workspace browser/resilience、sync tests | 停 helper、刷新 Web、恢复 helper | 保留旧快照并标离线；恢复后不重复发送 |
| 提醒/移动/无障碍 | push、accessibility browser | Chrome/手机宽度手工核一次 | 不泄露正文；键盘可操作；320/390px 不横向溢出 |
| 升级/备份/回滚 | migration、deployment security | staging 备份、升级、恢复和回滚 | 旧账户/卷/密钥保留；恢复后登录、同步和撤销可用 |
| 干净环境安装/首次接入 | 接入包 manifest/SHA256、`install.py --check-only`、onboarding 状态检查 | 新设备或新 profile 安装 agent-comm，完成 Web claim、连接检查和安全回显 | 篡改/错误包在安装前失败；错误平台或未确认 claim 不建立有效配对；原 profile 不被修改；最终只开放明确方法 |

## 6. P0 用户旅程验收

每个候选版本至少执行以下旅程。步骤中的“证据”要落成截图、HAR/请求摘要、服务日志和最终 JSON 报告，不能只在聊天里写“通过”。

### UJ-01 注册、登录和账户隔离

1. 用 A、B 两个 .invalid 账户注册，退出后分别登录。
2. 访问登录前的目标页面，确认登录后回到原目标；直接访问私有 API 应返回 401。
3. 在 A 添加一条连接，在 B 登录并确认看不到 A 的连接。
4. 验证错误密码、超长密码、重复邮箱、跨 Origin POST、16 KiB/1 MiB 请求上限和登录限流。

通过条件：无跨账户数据；错误提示可理解；HTTPS staging cookie/session 正确；日志没有密码、私钥和明文消息。

### UJ-02 添加连接、控制台身份和本机配对

1. A 登录 Web，输入 Alice 的完整 URN；已注册和暂未注册 URN 各做一次。
2. 打开工作台，创建 Console URN，复制本机配对命令。
3. 在 Alice 本机用真实 Hermes profile 执行显式 remote pair，只开放本次需要的方法和短期过期时间。
4. Web 点击“重新检查连接”，核对 capabilities、联系人、事项和同步时间。
5. 分别测试未配对、错误 Console URN、allow_from 缺失、方法未开放、过期和本机撤销。

通过条件：保存连接本身不授予访问权；配对主体来自 agent 本机；Web 不接受浏览器传入的 owner/agent 作为权限来源；撤销后只保留旧快照并明确标记。

### UJ-03 网页添加联系人（最重要的 UX 主路径）

前置：Alice 已允许 contacts.add，Bob 使用第二个临时 helper 或 Hermes B 身份在线；两端均注册到 staging Platform。

1. A 打开 Alice 工作台的“联系人”，确认仅打开页面不会产生写请求。
2. 点击“添加联系人”，填写显示名、别名和 Bob 完整 URN；未勾选确认框时发送按钮必须禁用。
3. 提交一次，记录 request_id，确认界面显示“已提交/等待对方接受”，不能显示“已连接”。
4. 模拟网络断开并刷新，确认出现“重试本次添加”，重试沿用原请求和业务参数，不新建意图。
5. Bob 在本机查看好友请求，分别验收接受和拒绝；不能用伪造 Web 请求替代 native owner 决定。
6. 接受后等待双方同步，A/B 两端显示同一 contact_id、URN、连接状态和提醒终态；拒绝后显示明确拒绝且不可假装 connected。
7. 重复提交相同联系人、不同联系人 ID、无效 URN、自己的 URN、过期请求各做一次。

通过条件：本机 agent Store 是最终事实；Web 只提交明确动作并展示已认证结果；刷新、重启和重复投递不会增加好友请求或重复消息；陌生请求不自动授予执行权限。

### UJ-04 双端消息、已读和提醒

1. Alice 在 Web 发一条无副作用文本给 Bob，等待 Bob inbox 出现。
2. Bob 在 native agent 回复，等待 Alice Web 同步；Web 标记已读，确认 Alice agent 的 inbox/read 与 attention 一起变化。
3. 在 Web、native、后台 worker 同时轮询，确认不会重复 ACK、重复推送或重复插入。
4. 停止一端，发一条消息，恢复后补拉；检查已读旧消息不依赖最新 inbox 窗口。

通过条件：消息正文、收件人、时间、message_id 一致；“平台已收下”不会被 UI 翻译成“对方已完成”；无权限或撤销后不能 Web-only 标已读。

### UJ-05 Web conversation 与真实 Hermes

1. 用 Alice Web 发送纯文字回显请求；只使用 conversation.send 明确提交。
2. 看到 submitted 后轮询 conversation.get，分别记录 running、completed、failed 或 interrupted。
3. 模拟浏览器关闭、Gateway 重启和网络超时；恢复后核对同一 conversation_id/turn ID。
4. 对“结果不确定”的发送点击重试，确认复用原请求、原密文和原 ID；对于已认证终态不能再次发送。

通过条件：模型回复是真实 Hermes 产生并可追踪；提交回执、模型完成和业务副作用分开；后台同步绝不自动发送新的 conversation。

### UJ-06 协作事项、Web 审批与撤销

1. 在 Hermes native 创建一个有明确联系人、能力、资料、时间范围、数量和期限的事项。
2. 对范围内动作验证自动允许；对全文、范围变化、资料版本变化验证具体审批卡。
3. 用 Web approval.respond 同意一次，用拒绝/过期/撤销各做一次；检查 late native callback 不会覆盖 Web 决定。
4. 撤销配对、事项或 worker 后再次执行，确认阻断；已披露内容不声称可召回。

通过条件：决定绑定 approval_id、版本、主体、事项和期限；Web 不能注入 owner、回答正文或任意 capability；批准不会直接宣称对方接受或创建日历事件。

### UJ-07 离线、恢复和数据保留

1. 先让 Web 同步完整联系人、消息和 conversation。
2. 停 helper 或隔离测试网络，刷新桌面和手机宽度页面。
3. 确认旧数据仍可读、显示最后同步时间和 offline/needs_pairing，不显示在线或成功发送。
4. 恢复 helper，等待后台 worker 自动同步；重启 Web/Platform 一次，确认没有重复发送和重复提醒。

### UJ-08 通知、手机和键盘

1. 在 Chrome 允许/拒绝系统提醒各做一次；测试提醒只含摘要，不含聊天正文或审批内容。
2. 在 320px、390px 和桌面宽度完成登录、联系人、消息、审批和提醒操作。
3. 用键盘完成导航、Tab/Enter、对话框关闭、通知 tab 切换和联系人提交；检查焦点可见和 role/aria-* 语义。

## 7. 服务器 staging 验收流程

在服务器准备 deploy-staging/，不要与生产 Compose project 共用卷。若同一 ECS 已有生产 Compose，先生成并检查 staging override（容器名、端口、域名、卷、数据库、Platform 外部地址和代理网段）；以下命令中的 `PATH_TO_STAGING_OVERRIDE` 不能省略，不能直接用根 Compose 与生产并行：

~~~sh
git submodule sync --recursive
git submodule update --init --recursive
docker compose -f docker-compose.yml -f PATH_TO_STAGING_OVERRIDE.yml -p agent-staging config --quiet
docker compose -f docker-compose.yml -f PATH_TO_STAGING_OVERRIDE.yml -p agent-staging up --build -d
docker compose -f docker-compose.yml -f PATH_TO_STAGING_OVERRIDE.yml -p agent-staging ps
docker compose -f docker-compose.yml -f PATH_TO_STAGING_OVERRIDE.yml -p agent-staging exec nginx nginx -t
curl --fail https://staging.example/healthz
~~~

接入包或连接方式变更时，先在独立设备/profile 完成 T12，再按 UJ-01～UJ-08 运行真实浏览器和 Hermes 流程，另外执行：

1. 记录 `docker compose -f docker-compose.yml -f PATH_TO_STAGING_OVERRIDE.yml -p agent-staging logs --tail=200 nginx web platform`、helper/Hermes 日志和所有请求 ID。
2. 备份 Web SQLite、Platform 数据卷、.env、nginx/Platform 配置和当前镜像 digest；只保存密钥文件的权限和哈希，不把 secret 写进报告。
3. 做一次无数据破坏的升级：替换固定子模块/镜像，运行迁移、重新登录、同步、消息、好友和撤销；再从备份启动隔离回滚环境验证旧数据可读。
4. 检查 HTTPS 证书、HTTP→HTTPS 跳转、ACME challenge、X-Forwarded-* 覆盖、注册/登录限流、请求体上限和 Platform 8080 不可公网访问。
5. 失败时保留现场和备份，停止发布；只有恢复验证完成后才允许清理 staging 数据。

E3 线上烟测只使用无副作用请求：/healthz、官网、登录/登出、smoke 账户工作台加载、已同步快照读取、撤销后的访问拒绝。真实好友请求、消息和模型回合只在 E2 staging 做。

## 8. 非功能测试

### 安全

每个候选版本至少执行：匿名 API、跨账户 IDOR、Origin/CSRF、伪造签名、篡改 envelope 字段、错目标、重放/冲突 ID、过期/撤销配对、管理员令牌、代理头、请求体、限流、日志脱敏、依赖审计和容器 UID/GID 检查。安全失败必须是 fail-closed，并且不能 ACK 未验证消息。

### 可靠性

注入 helper/Platform/Web 进程重启、MQ retrieve 重复、ACK 丢失、响应已落盘但 ACK 失败、SQLite busy、网络超时、SSE 断线、投递 lease 过期和浏览器刷新。指标是：无丢消息、无重复外部副作用、同一稳定 ID 可核实、旧快照保留、退避不会忙等。

### 性能和容量

在独立 staging 运行基线压测，不把它混入功能门禁：并发登录/注册、每 URN 消息上限、MQ TTL、Registry TTL、Relay reservation、同步连接数、Web 数据库增长、100 条窗口合并和 push worker。记录 P50/P95/P99、错误率、CPU/内存、SQLite 锁等待和磁盘增长；先用配置中的实际上限作为通过线。

### 兼容性和可访问性

至少验证 Chrome/Edge 当前稳定版、桌面 1440px、390px 和 320px；若产品声明支持 Safari/iOS，再在真实 Safari 做登录、联系人、消息、通知权限和恢复。自动化 accessibility 检查不能替代键盘和真实手机手测。

## 9. 门禁、报告和完成定义

### PR/合并门禁（E0）

- Web npm test、npm run lint、npm run build。
- Platform/SDK go test ./...、Python runtime tests、connector tests（依赖可用时）。
- 不允许新增失败、未解释的 skipped test、类型/构建错误或安全测试回归。

### 候选版本门禁（E1 + E2）

- test_remote_control_network.py、test_agent_web_parity_network.py、full_stack_smoke.py 全通过。
- test_deployment_security.py 全通过。
- UJ-01～UJ-08 中 P0 全通过，至少保存 UJ-03、UJ-04、UJ-05 的浏览器截图和请求/日志证据。
- staging 升级、备份和回滚演练通过；镜像、子模块、配置和数据库版本可追踪。

### 部署后门禁（E3）

- /healthz、官网、登录、smoke 工作台和已同步快照读取通过。
- docker compose ps 全部 healthy/running，nginx 配置测试通过，错误日志无新的启动/迁移/认证异常。
- smoke 完成后撤销测试 Console 和删除测试账户；保留报告和必要的故障证据。

每个运行写一个 result.json，最少包含：

~~~json
{
  "run_id": "20260922-120000-ab12",
  "commit": "<deployment commit>",
  "submodules": {"platform": "<sha>", "web": "<sha>", "sdk": "<sha>"},
  "environment": "E2-staging",
  "cases": [{"id": "UJ-03", "status": "passed", "evidence": ["..."]}],
  "services": {"nginx": "...", "web": "...", "platform": "..."},
  "started_at": "...",
  "finished_at": "..."
}
~~~

完成定义是：P0 功能和权限全通过；关键用户旅程有真实证据；升级/恢复和撤销通过；没有把 ACK/提交回执误报成业务成功；已知限制（例如没有 conversation.list、已同步内容不能召回、当前 Hermes 不后台唤醒私人对话）在报告中明确记录。

## 10. 推荐执行顺序

第一次建立测试体系时按这个顺序落地：

1. 给 staging 服务器创建独立域名、Compose project、卷、凭据和备份目录。
2. 先跑 Web、SDK、Platform 和 helper 的 E0/E1 自动化基线。
3. 在本机生成 Alice/Bob 临时身份，完成 T02 协议闭环。
4. 用新 Hermes profile 完成 T12 干净安装、Web claim 和连接检查。
5. 构建 Web，跑 fixture、mutation 和 social 浏览器检查；再把 Alice helper 接到 staging Platform，完成 UJ-01/UJ-04。
6. 在真实 Hermes profile 重做 UJ-05/UJ-06，输入只产生文字回复的模型任务。
7. 关闭 helper、重启 Platform/Web、做备份恢复，完成 UJ-07/UJ-08。
8. 固化 result.json、截图、日志和版本清单；把稳定步骤接入 CI/发布脚本，把依赖真实 Hermes/浏览器的步骤保留为 staging release checklist。
