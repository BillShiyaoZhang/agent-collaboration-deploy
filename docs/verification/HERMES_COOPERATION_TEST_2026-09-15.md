# 已绑定 Hermes 的系统协作测试（2026-09-15）

> 历史验收记录：以下结论、源码路径、日志和部署位置对应 2026-09-15 的此次验证；保留原始证据。当前可复用测试入口见 [验证索引](README.md)，后续发布见 [发布索引](../releases/README.md)。

报告状态：本轮系统协作测试、代码修复和部署已完成。Hermes 本地更新已生效；用户明确允许备份并部署后，Web 修复已上线 `agent-communication.online`，上线后的真实回复、后台同步、重复提交、旧会话保留及最终审计均通过。

## 目标与测试对象

目标是通过服务器后台，与 `shiyao@example.com` 账号已经绑定的 Hermes 实际协作，系统检查消息往返、上下文、恢复、隔离、权限和结果同步，并修复发现的问题。

服务器只读预检确认该账号已有一个名为“本机 Hermes”的绑定。本次沿用现有绑定与身份，未新建生产账号、重新配对或替换密钥。`capabilities` 返回 `agent-comm-control/v1`，允许会话收发及已授权的只读方法；`approval.respond` 明确不可用，原因是需要原生可信交互。预检及后续快照确认该连接有成功同步记录。

所有真实协作任务使用专门测试会话和合成材料。会议任务只请求建议，未创建会议或联系他人。本文不包含用户 profile、记忆、私钥、令牌或原始数据库内容。

## 真实协作结果

| 场景 | 实际观察 | 判定与范围 |
| --- | --- | --- |
| 会议方案 | 给定甲 14:00–15:00、16:00–17:00，乙 14:30–15:30，需要连续 30 分钟；Hermes 返回北京时间 2026-09-16 14:30–15:00，`needs_confirmation=true` | 方案计算正确；输出为 Markdown 代码围栏中的 JSON，不能直接当作裸 JSON 解析 |
| 同会话修订 | 乙改为 14:45–15:15 后，Hermes 将两个候选时间改为 `null`，说明只有 15 分钟交集，不满足 30 分钟 | 正确使用更新后的约束，没有沿用上一版候选 |
| 设计评审首轮 | 对恢复、幂等、租约和原生确认提出测试建议，但同时虚构了 IPC/PID 审批、worker 池、`queued` 状态、容量和时限；还建议去重 TTL 过期后将相同 ID 当作新请求 | 实际协作已完成；建议存在事实错误，其中 TTL 建议可能造成重复执行，未采纳 |
| 评审纠正轮 | Codex 提供实际实现事实后，Hermes 去掉上述虚构机制，改为同一请求持久去重，并提出确认边界、缓存过期重投、租约写竞争的测试 | 能根据事实修订；剩余建议仍需代码审查，不能将回答中的机制或“应有结果”直接当成实现事实 |
| 原始 `HERMES-READY` 模板 | 首轮没有按严格模板输出；增加已配对远程会话的来源说明并更新 Hermes 后，同类提示仍返回拒绝/解释 | 严格回显要求未通过。来源说明没有消除模型把“就绪”措辞理解成状态证明的问题 |
| 纯文字回显 | 明确说明字面文本不表示系统就绪、审批通过或操作完成，Hermes 精确回复 `紫杉-4826` | 真实模型回显通过 |
| 同会话提取 | 下一轮要求输出前一轮文本中连字符后的数字，Hermes 精确回复 `4826` | 两个不同 `turn_id` 均为 `completed`，`error=null`，同会话上下文通过 |
| Web 上线后真实回归 | 新建专用会话，要求纯文字回显；Hermes 精确回复 `青竹-6193`，后台 workspace 自动保存 `completed` 终态 | 新版本实际链路通过；重投相同请求 ID 返回原 `turn_id`，会话仍仅一轮；上线前的 `紫杉-4826`、`4826` 两轮也完整保留 |
| 跨会话检查 | 在独立会话 B 中询问本会话是否曾提供校验码，要求未知时回复 `UNKNOWN`；实际回复 `UNKNOWN` | 该合成探针未串入会话 A 的校验码；不将单个探针扩大为对所有记忆、工具或资料隔离的证明 |

纯文字回显两轮的终态来自 Web workspace 已保存的结果：`sync.status=ready`，两个回复均已同步。本次读取该会话终态没有通过手工 `conversation.get` 触发即时拉取，因此证据同时覆盖后台结果同步到 workspace 的链路。

主要原始附件：`planning-first-result.json`、`planning-revise-result.json`、`review-final-result.json`、`review-revised-poll-result.json`、`after-fix-first-final.json`、`literal-echo-proactive-result.json`、`literal-followup-proactive-result.json`、`get-b-first-result.json`。

## 幂等、输入与权限边界

| 检查 | 实际结果 | 解释 |
| --- | --- | --- |
| 同一 `request_id`、同一内容重试 | 返回 HTTP 200 和原 `turn_id` | 没有新建会话轮次；返回的 `submitted` 是原提交回执，不能据此认为模型又运行了一次 |
| 同一 `request_id`、不同内容 | HTTP 409 | 拒绝把同一个 ID 绑定到另一条请求 |
| 超过 Web 10 分钟传输缓存后重投首条 ID | HTTP 410，提示已有保存记录、查看原对话；再次读取原会话仍为相同两个 `turn_id` | 这条已有会话提交未被重新投递或新增轮次；缓存 TTL 不等于业务去重期限 |
| 回显首条 ID 重试 | 返回回显首轮原 `turn_id`；随后 workspace 仅含原有两轮 | 在修复后的实际模型任务中再次确认重复提交不新建轮次 |
| 非允许来源 Origin | HTTP 403 `Forbidden origin` | Web 入口拒绝该跨来源请求 |
| 远程 `approval.respond` | Web HTTP 400 `Invalid control request`；能力清单同时标记不可用 | 远程聊天没有原生确认权；真实测试没有绕过原生授权 |
| 空白会话文本 | 传输接收后，Agent 返回 `invalid_params` | HTTP 202 或控制响应 `complete` 都不代表业务成功，需要检查协议层 `error` |

主要原始附件：`send1-result.json`、`replay-result.json`、`conflict-result.json`、`expired-cache-replay-result.json`、`expired-cache-turns-result.json`、`literal-echo-send-result.json`、`literal-echo-replay-result.json`、`origin-result.json`、`approval-result.json`、`empty-result.json`、`capabilities-result.json`。

## 发现的问题与改进

| 问题 | 本轮改动 | 当前证据与边界 |
| --- | --- | --- |
| Hermes 重连后已受理的 `submitted` 任务没有主动恢复，要等新 RPC 才初始化远程 Bridge | 在启用 remote 的连接建立阶段立即初始化 Bridge，启动恢复 | Connector 回归覆盖；本地已安装并正常重启。未以破坏真实运行中任务的方式做生产故障注入 |
| 配对控制台可能由用户授权的协作 Agent 操作，来源描述却笼统标为 owner，模型容易误判请求来源或格式要求 | source 名称改为 paired remote console，并增加受配对/权限验证的 channel 上下文；保留禁止 Gateway 控制、原生审批和额外资料披露的边界 | 已安装。纯文字回显和提取成功，但原 `HERMES-READY` 提示仍失败，不能声称模型误判已完全解决 |
| 字节数有界的 JSON 仍可能含极深嵌套，触发解码递归异常 | 将递归异常规范为单条请求 `ValueError`，并限制容器嵌套深度为 32 | Python runtime/Connector 回归；本地已安装 |
| Web 旧 worker 失去租约后仍可能删除继任者需要的已认证响应缓存 | 只有 lease token 比较交换成功、确实推进同步计划的 worker 才删除原响应记录 | 回归及 Linux 候选验收通过；已上线，运行文件哈希与验收镜像一致 |
| Web 已收到响应但保存投影失败时，原请求 deadline 到期可能过早放弃结果 | 对已有响应信封按缓存有效期重试保存，区分“等待网络结果”和“已收到、待保存” | 回归及 Linux 候选验收通过；已上线，真实回复完成后台同步 |
| Web SQLite 写入冲突 | 对回滚后的本地投影事务增加有界 `SQLITE_BUSY` 重试，每次重新读取当前记录；重试不包含网络投递或 mailbox ACK | 实机捕获 Code 5 / HTTP 500，原请求重试后完整恢复；事务回滚、重试上限和持久记录回归通过；已上线，启动至最终审计未观察到该类日志错误 |
| 隔离测试子进程可能继承生产 `PLATFORM_*` 环境覆盖 | 清除该前缀环境变量，并把子进程 cwd 固定到本次 UUID 测试目录 | 故意注入错误监听地址和数据目录后网络测试仍通过，哨兵数据目录未创建 |

源文件分别位于 SDK 的 `connectors/hermes-platform/hermes_platform_agent_comm/platform.py`、`python/agent_comm_runtime/remote.py`，Web 的 `src/lib/workspace-sync.ts`、`src/lib/workspace-store.ts`，以及部署仓库的 `tools/test_remote_control_network.py`。

## Hermes 本地安装与回退准备

已将审阅后的 `platform.py` 和 `remote.py` 两文件安装到现有 Hermes。安装前确认 Gateway 空闲，备份两份原文件和三个 SQLite 数据库；数据库采用 SQLite 在线备份并执行完整性检查。安装脚本校验源文件、目标旧版本与替换后哈希，文件写入采用原子替换，没有恢复或覆盖活动数据库。

备份标识：`hermes-cooperation-20260915-013126-0c658c5c62c9`，位于现有 Hermes 的 `agent-comm/backups/`。只将该标识和验证元数据写入本报告，备份数据库不入库。

| 安装文件 | 已验证 SHA-256 |
| --- | --- |
| `platform.py` | `9c8abb1589ac77ca4f90c2a7065abbdcc5fa00fb97fdb59e3af5762d151dce96` |
| `remote.py` | `f99e5d72e262c50b59325c7b708fd5cd5d8e17192ae559803fafa50ce2919e1b` |

备份 manifest 的 `installed_restart_required` 是安装完成时的状态。此后已正常重启 Gateway；后续只读核验确认 `gateway_state=running`、新 PID 为 `11796`、PID 记录匹配且进程存在，两个安装文件的哈希均与审阅源码一致。回显两轮发生在该次重启之后。

## 测试层次与结论强度

| 层次 | 覆盖内容 | 不能由此推出的结论 |
| --- | --- | --- |
| 真实服务器与已绑定 Hermes | 上述方案、修订、评审、回显、跨会话探针、重复提交、输入/权限和 workspace 同步 | 无法覆盖每种模型回答或所有故障时序；模型 `completed` 不代表回答正确 |
| Python runtime 与 Hermes Connector 回归 | 恢复、原生确认边界、路由、状态机、解析及上下文等可控场景 | 测试替身不能证明真实模型一定采用指定格式或不出现错误建议 |
| 本机真实 Go platform/helper 网络测试 | 新建本地身份，签名加密控制往返、ACK、持久化、权限与异常投递 | 不调用真实 Hermes 模型，不证明生产账户协作质量或 Web 部署状态 |
| Web 回归与构建 | 同步租约、持久投影、缓存和 SQLite 事务等实现验证 | 本地测试通过不能单独证明生产部署；此轮另有 Linux 候选验收、生产镜像/哈希审计及上线后真实协作证据 |

最终自动测试合计 **267 项通过**：Python runtime 40 项、Hermes Connector 113 项、Web 114 项，无失败或跳过。Python 源码哈希匹配实际安装版本；Web 非增量 TypeScript 检查、lint 和生产构建均通过。下述 12 项隔离网络检查及 11 项原始附件断言单独计数，不重复并入单元/集成测试总数。

本机网络扩展测试 12 项全部通过：真实签名加密往返、Agent 本地联系人、原生收件箱不提前 ACK 控制请求、Bridge 重启保持原响应、方法权限、撤销配对、owner 联系人隔离、响应存储失败后的保留与幂等重试、非法参数、发送方声明与关联字段校验、远程原生审批保持不支持、会话只入队而不伪造模型回复。helper/platform 使用当前 Go 源码与离线 modcache 重新构建；没有 Go 源码变更，本轮未重复宣称执行了全套 Go 单测。

网络测试的配置、身份、数据库均在新的 UUID 目录，平台 HTTP 和 bootstrap 指向本地，两 helper 的 bootstrap ID 与本地平台一致。没有引用生产 private 目录或向真实账户发送应用消息。helper 保留标准 P2P 监听，不能把该测试描述成由操作系统防火墙强制封闭的网络沙箱。测试完成后没有遗留测试进程。

## SQLite 证据与限制

真实后台 `conversation.get` 曾返回 HTTP 500；服务器日志为 Prisma `$executeRaw` 的 Code 5 `database is locked`。再次读取原 `request_id` 返回 200，完整结果仍然存在。修复只对明确的 `P2010/meta.code=5` 或 `SQLITE_BUSY` 重试完整本地投影事务，最多四次，退避分别为 40、120、300 ms。已签名响应仍须成功持久化才 ACK，不重发远端任务。

回归以真实 SQLite 事务写入后的故障注入验证 Code 5 回滚、重新读取、无重复记录及重试耗尽时保留原结果。两个独立 Prisma 客户端的真实竞争还产生了泛化 `P1008`，它没有底层 busy 码；该错误保留立即返回，释放锁后同一结果可以补存。这里不宣称所有数据库超时已消除。

## Web 部署与验收

| 项目 | 已核实结果 |
| --- | --- |
| 发布标识 | `hermes-cooperation-web-20260915-cc8f1afb2732` |
| 基础 Web 提交 | `312fd50ae62b2bb0aaf7cdc4bed30e1a1c337a4d` |
| 本轮源码 | 上线时为 4 文件工作区补丁；完整 patch SHA-256 `cc8f1afb2732a50679d0801ffcb9436fce8893ea0e1aec1dedd3ad14cf560a7e`；对应后续 Git 提交见下方 |
| Build ID | `0rQAIetCOItBAKLzxbOHh` |
| 已上线镜像 | `sha256:09935983fa4a025c85c486504f4aa3bca076ed57b5374b87525565aaf5cc515d` |
| 原生产镜像 | `sha256:3ecaae8cd3ef965fe78d3c616050fe6ea51bec1341d201a58f37441138ac218e` |
| 包 SHA-256 | `81efda1f2d1a33b8ead99e35cb50de6b1a61001006b9c4de22fd712c0195c4d2` |
| 服务器发布目录 | `/root/agent-comm-releases/hermes-cooperation-web-20260915-cc8f1afb2732` |

服务器核对 120 份原源码无漂移，125 个发布文件哈希正确。候选继承原 Linux 依赖与启动文件，以 `--network none` 和仅含合成记录的独立 SQLite 运行；通过后台 worker 在首个 HTTP 请求前启动、登录、私有 API 鉴权、账号隔离、22 个页面资源、154 个运行/保留静态文件的检查。候选验收确认原生产容器未改变。

用户明确回复“允许备份并部署”后，于北京时间 2026-09-15 09:54 完成生产切换。首次执行在备份阶段发现服务器 Python 3.6 没有 `Connection.backup`，当时尚未切换服务；随后改用服务器 SQLite CLI 的在线备份 API，校验备份成功后继续。

有效回滚备份目录：`/root/agent-comm-backups/hermes-cooperation-web-20260915-cc8f1afb2732-20260915T015412Z`，包含完整性检查通过的数据库快照、四份原源码和回滚元数据。原镜像已保留回滚标签 `agent-collaboration-web:rollback-hermes-cooperation-20260915`。程序回滚流程保留实时数据库；本次部署成功，未执行回滚。

生产切换及北京时间 09:57 的最终审计确认：

- 原用户与 Agent 记录保留，账户行未变化，现有绑定仍正常同步；生产与备份数据库均通过完整性检查。
- Web 镜像、Build ID、四份部署源码及 154 个运行/保留静态文件哈希正确，容器没有异常重启。
- 环境、数据挂载和配置保持一致，platform 与 nginx 容器身份保持不变。
- 公网 `/healthz`、`/login` 返回 200；未登录 `/api/workspace` 返回 401。
- 启动至该次审计的日志中，未观察到 SQLite busy、Prisma、模块缺失或未捕获异常；这一有限观察窗口不代表以后不会发生错误。
- 独立无网络的合成候选容器已停止并移除，候选数据库、镜像和发布证据保留。

部署后真实任务 `926eb19e-ecda-427b-9624-ded46a69c8e3` 的终态直接读取 workspace，未手工调用 `conversation.get` 拉取。回复精确为 `青竹-6193`，重复提交仍为同一 `turn_id`，再次读取只有原一轮；部署前两轮回显内容和 ID 均未变化。

用户随后要求提交并推送，本轮源码由以下 Git 提交记录，父仓库同步更新子模块引用：

- SDK / Hermes：`a2d06d0eb5c8a283328986ff7ae60ec13e125891`（`master`）。
- Web：`21608208a521ce08ede54a18091773592870c45d`（`main`）。

发布 manifest 中的 `uncommitted_patch` 与完成证据索引中的未提交说明记录的是上线验收当时的状态，保留原始证据不作追溯改写。当前 Git 提交与经过验收的源码一致。Hermes 的定向本机更新及本次源码推送不等于重发对外安装包。

## 证据位置

逐项原始 JSON、日志、构建哈希和本地安装脚本保存在被 Git 忽略的 `build/hermes-cooperation-20260915/`。回显和评审文本属于测试材料；报告索引仅保存必要结论及附件哈希，不复制个人 profile 或原始数据库。

- Python 两套结果：`python-hermes-final-tests.json`，对应两份测试日志。
- 当前源码构建、隔离验证和哈希：`transport/verification-manifest.json`。
- 本机网络测试结果：`build/early-access/remote-network-test/8b40ec77-6222-4173-96b5-a2ce6bbe08ff/result.json`。
- 实际协作证据断言索引：`report-evidence-summary.json`，由只读原始附件的 `summarize_report_evidence.py` 原子生成；该脚本不发请求、不调用模型。
- 安装过程依据：`local_update.py` 与上述本地备份 manifest 元数据。

- SQLite 精准回归与限制：`web-sqlite-busy-verification.json`、`web-sqlite-busy-final-tests.log`。
- Web 最终测试/包/服务器候选：`web-release/validation.json`、`manifest.json`、`stage-result.json`、`candidate-result.json`。
- 本机最终只读审计：`local-final-audit.json`，确认新 Gateway 进程、安装哈希、两平台连接；7 个专用测试会话的 11 个模型回合全部结束，活动任务为 0，该时间段 helper 没有普通业务消息。
- 生产部署与最终审计：`web-release/deploy-result.json`、`web-release/final-audit-result.json`。
- 上线后真实回归：`post-deploy-old-workspace-result.json`、`post-deploy-send-result.json`、`post-deploy-workspace-final.json`、`post-deploy-replay-result.json`、`post-deploy-replay-workspace-result.json`。
- 完成证据索引：`completion-evidence.json`，由 `summarize_completion.py` 校验上述原始结果及当前源码后生成，独立于前述 11 项附件断言。

这轮结果证明已有绑定能完成多轮、有反馈的真实协作，也暴露了模型对“状态证明”措辞的误判和评审中的事实编造。协议状态、模型文本和实际副作用必须分别验证。后续使用评审建议时，应先给出真实实现约束，再由代码与故障测试确认，不能让模型自行补全的机制或 TTL 建议成为发布依据。
