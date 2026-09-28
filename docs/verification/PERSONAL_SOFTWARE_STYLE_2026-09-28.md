# 官网、控制台、Admin 与接入包验收（2026-09-28）

**结论：本轮部署和约定的全流程验收完成。** 视觉更新、v0.9.5 GitHub 正式资产与官网公网下载、r7 云端初验、原 Alice/Bob 正式接入包升级及真实双端协议终态和四任务清理、独立 Fresh 正式首装与两回合真实模型、原双方 Fresh 后保护以及最终云端只读复核均已通过。GitHub `main` 收敛待处理。下面分别记录构建、公开下载、云端只读状态与真实 Agent 行为，不以 `submitted`、队列 ACK、单层批准或 HTTP 200 推断业务完成。

| 层次 | 已核实结果 | 尚未覆盖或待完成 |
| --- | --- | --- |
| 本地与线上视觉检查 | 官网两语言、四种宽度与 200% 字体、键盘操作；控制台和 Admin 的真实页面与状态已进行浏览器检查。生产公网浏览器记录中，中文和英文官网图片正常、无页面或资源错误；Admin 七个真实 API 页面只读加载通过。r6 的桌面、手机和手机 200% 字体复核确认首页与登录页 HTTP 200、主图加载且无横向溢出。r7 中文首页桌面/手机和登录页桌面三页 HTTP 200、标题正确、无页面错误，三张截图已目视检查。 | 浏览器检查只覆盖实际执行的页面、视图及交互，不代替全站业务或安装流程。 |
| 官方 v0.9.4 公开下载 | GitHub 16 项资产、官网清单与五份 ZIP 的 SHA-256、大小、包内成员、源码固定引用和信任锚校验通过；初次权限失败回退及成功恢复有独立回执。 | Windows Fresh 只完成官方下载和 `install.py --check-only`；Mac 未做本轮真实首装。 |
| 官方 v0.9.5 GitHub 资产 | [正式发布](https://github.com/BillShiyaoZhang/agent-comm/releases/tag/v0.9.5)的 16 项资产逐项按 GitHub 声明的大小与摘要核对；不执行下载代码的离线校验通过正式清单、四种平台 ZIP、固定信任锚、源码 ZIP 的固定对象、文档与 wheel 成员。GitHub 清单 SHA-256 为 `2f844a6dcfd8c7a84d595a38fbf6319655b09272b2a3ebbc4fb6702bcd8bbc72`。 | GitHub 资产通过不等于原 Agent 已升级或 Fresh 已安装。 |
| 官网 v0.9.5 公开下载 | 发布器持久回执 `published`；公网 HTTPS 对五份 ZIP、网页清单与原邀请 PDF 共 7 个入口逐字节核对通过，网页清单 SHA-256 `779159687fc50116ac605cc2fedd636402714be11097fda03c77b42adaf29fe4`。旧 v0.9.4 私有备份及原邀请 PDF 保留。 | 下载可用与包完整性不代替本机安装、网页授权或业务完成。 |
| 原 Alice/Bob 官方包升级 | 两侧 runtime `0.1.10`、Hermes connector `1.5.12` 原位升级，升级及独立后验均 PASS；21 份一致 SQLite 备份逐库快速检查通过。原身份、配对、范围与协作状态稳定，单一连接消费者且无 active work；升级未提交业务请求、未恢复数据库或新建身份。 | 安装后验与后续 v5 真实业务分开核验。 |
| r5 云端只读门禁 | 一次性审计、镜像预加载、新备份、Web 切换四阶段均 exit 0 且持久回执匹配；r5 Web 镜像和四仓提交固定，初始只读验证通过。旧 r4 25 文件、r3 32 文件和本次 19 个保护文件留存。 | 最终云端复核须等真实业务与 Fresh 清理结束后另行执行。 |
| 原 Alice/Bob 业务 | 双模型真实完成和 108 项导航已有证据；原双向普通消息的精确审核与已读已完成。r5 新的拒展示消息在 Native 和网站两层均明确拒绝。r6 原任务已准备、逐方审核、邀请和加入，Bob 提议也经 Native 和网站两层审核。v5 两侧在同一协议终态关闭，四项限定合成任务逐项撤销；独立只读后验核对 21 当前库加 21 备份库、原身份配对和零 active work。 | v4 的原失败回执保留；v5 结果只覆盖这次有界合成流程，不代表 Fresh 首装或云端最终复核。 |
| r6 修复部署 | Web 提交 `30b84550f8cb5a8b643ca2f2a21139c9335bc209` 将协作能力读取改为稳定身份和权限依赖；真实 React/Chrome 组件回归 14 项断言、TypeScript 检查、相关单元测试 20/20、Linux 全量单元测试 388/388 通过。镜像、Docker 26 加载及云端四阶段初验均通过。 | 初始只读门禁不替代原 Alice/Bob 有限协作任务的实际完成与清理；后续 SDK 缺陷由 v0.9.5 单独修复。 |
| r7 固定发布与初验 | Web Linux 单元测试 388/388；新镜像与完整构建文件系统和配置一致，紧凑归档在 Docker 26 验证缺少精确基础镜像拒绝、存在时加载成功。新旧 Platform/SDK Go 输入和 Platform 可执行文件逐字节相同。云端审计、预载、当前 Web 新备份、部署四阶段 `finished`/退出码 0/`passed=true`，初始只读验证 `verification_passed`。 | 新 Python SDK 不在服务器的旧 Platform 容器中自动生效；原 Agent 升级已单独核对，业务终态及最终云端复核另验。 |
| 独立 Fresh 首装 | 原 Alice/Bob v5 后签发 READY；隔离新 Python 与新身份使用正式官网 v0.9.5 包完成首装。未知领取结果恢复后总计一次 claim POST；欢迎和 nonce 各一次真实 MiniMax API 调用并在页面刷新后保留完成状态。只删除 Fresh 新连接，撤销本机配对并停止三个 Fresh 进程，留存私有身份与数据库；19 项阶段哈希独立复核。 | 这次真实 Windows 隔离首装不代表 Mac 首装或真人邮箱、日历操作。 |
| Fresh 后原双方保护 | 独立只读报告再次核对原 Alice/Bob 当前 21 库和备份 21 库，身份、密钥、配对与范围不变，同一协议关闭、四任务撤销、该协作 Native 待审数为零、两侧单一连接消费者且无 active work。原 Web 连接集合对比仅绑定 Fresh 清理前后快照。 | 该检查不代替最终云端只读门禁；未额外登录原网站账户。 |
| 最终云端门禁 | r7 最终一次性只读验证 `verification_passed`；Web/Platform/Nginx 三容器运行且重启、OOM 均为零，四生产库 `quick_check=ok`，47 User/42 Agent 基线不变，v0.9.5 公网七文件字节、凭据/19 保护文件与历史备份链保留，监测的四类日志错误计数均为零。 | 只读门禁不单独证明业务完成；原双方与 Fresh 的实际业务分别由上方独立回执证明。 |
| 最终发布 | 当前生产运行 r7 固定 Web 镜像；Platform 保留旧镜像，有新旧构建输入及可执行文件相同的独立证明。v0.9.5 GitHub 正式包、官网公网七入口、原双方接入包升级与有限协作、独立 Fresh 首装和清理、原双方 Fresh 后保护及最终云端门禁均已校验。 | GitHub `main` 收敛及其与线上固定源码的关系待核；没有真实 Mac 首装或真人外部业务。 |

## 精确版本与安全门禁

r5 部署固定部署 `b81e54eb065b6977282c310277379ad0f23046f6`、Web `9f7ff445f3ea4097cd8a4d3c3f2ce6e4570afc3c`、Platform `ba779d12c3e9d46393e22502ff2efa69da1d7cf8`、SDK `9d3505335d2c50d19811ccef69cdd3f69926b851`；Web 镜像为 `sha256:cdeb51ba610bbef04cd75a4fae1376ca229219597c730f4558a8bcd7a9918936`。SDK 官网包内部署与 Web 固定提交仍分别是 `295d8fb90e1ad01d1c42347592324d48918cb7b3` 和 `32891c2ae1c24297350cd0280445c235e345d55d`，后续 Web 补丁没有修改它们。

审核版本同时核消息 ID、发送者、类型、完整正文与摘要。只有已确认的本机派生 `trust`、`unknown_sender` 和服务端投影字段按固定规则排除，其他语义字段仍参与摘要。Native 完整预览、网站具体审核行及其一次性预览令牌必须分别对应同一目标；旧的已批准版本不替新版本做决定，拒绝版本不会因另一个版本批准而解封。

r5 的原反向消息恢复使用精确 Website 行决策与单次 `inbox.mark_read`，将原消息已读绑定到认证控制回执、同请求 ID 的持久操作记录和 Web 账户快照；原发送及 Native 批准没有重放。有限流程的新拒展示消息已完成精确两层拒绝；之后的合作对象选择超时发生在当时的新任务提交之前。r6 Web 修复后，原 Alice/Bob 的一个正向任务与一个邀请、加入和提议均已真实落地，拒绝审批留下另两条待清理测试任务。v4 保存的最终 `FAIL` 回执显示 Bob 提议 Native 与 Website 审核和双方第二轮 worker 主人批准成功，10 分钟内协议仍未终结，也未做四任务清理。只读数据库证据显示待审提议与乱序缓冲均为空，但已持久化的 `peer_review_required` 没有清除；这是 SDK 恢复状态缺陷。先前 `FAIL` 不取消已发生动作；不能重发未知结果的请求或覆盖失败证据。

本地 r6 修复针对协作能力说明读取 effect 的不稳定函数引用。浏览器回归在实际 `GoalWorkflow` 上逐次更换内联函数引用，确认三项动作返回后合作对象选择框启用；同时检验权限撤销与恢复、Agent 和 Console 身份切换、旧读取迟到时不误显示旧能力。该源码已在云端固定部署；原 Alice/Bob 现场结果见后文真实 v5 与独立后验回执。

r6 部署固定部署仓库 `c378884cac78c8b718bea92de8e73af6809b6d73`、Web `30b84550f8cb5a8b643ca2f2a21139c9335bc209`、原 Platform `ba779d12c3e9d46393e22502ff2efa69da1d7cf8` 与 SDK `9d3505335d2c50d19811ccef69cdd3f69926b851`；Web 镜像 `sha256:d541f6e75fa9db32c1a1fb4a2a4bd6a300f9364f11f8741c2ab84f0a288775fb`，复用 r5 的 34 层并新增 4 层。服务器独立核对 21 个上传文件；审计、预载、当前 Web 在线备份、部署四阶段均 `finished`、退出码 0、`passed=true`。2026-09-28 04:13:49 UTC 的初始 `verification_passed` 文件 SHA-256 为 `64f7aaf5955dc84ab4d4c88159ef379e1005d15b43f3a97bfea6c0983581ad0b`。用户 47、Agent 42、19 个保护文件以及 r5/r4/r3 的 25/25/32 文件历史备份得到核对；Platform/Nginx 容器和原有数据库未重建。

r7 固定源码为部署 `a573f90955ffe5b3d6dba6e05e935978e317acdb`、Web `f7e49a138e7036f25ae8b537b79fa6915a3d0525`、Platform `afc7d6d8c641cf43af563382d70def3f3eb7afc9`、SDK `ff1419c156dee590d100ceeaea05aacf49c037e4`；源码包 SHA-256 `38d584e1f1a5362a261683431c9002867a02ef7efd0eb5a28f849ff24fb016eb`。新 Web 镜像为 `sha256:d47d5d4e19d6309f200efd3904eacd254f4ad6b41e3de657b018b963504231d3`，复用 r6 的 38 层并新增 4 层；78,469 字节紧凑归档通过 Docker 26 正负加载验证。Platform 线上镜像仍为 `sha256:87799b78e0d51b067759c498bd1bb9deda900e8c0b243bb62be45d49cd7abea1`：47 项 Platform 和 87 项 SDK Go 输入未变，候选与现有可执行文件 SHA-256 同为 `dd5f264d24e10e3bb8f4a69264c93b2c9434203f7e17dcf26e5492b3a961a696`。此处的 Platform/SDK 源码更新不等于服务器已运行新的 Python runtime，也不等于原 Alice/Bob 已安装正式包。

r7 私有发布目录 `/root/agent-comm-releases/personal-software-style-20260928-r7/` 的审计、预载、新 Web 备份与部署四阶段均 `finished`、退出码 0、`passed=true`；本次只替换 Web，四个生产数据库保留且快速检查为 `ok`，47 用户、42 Agent 和 19 个受保护文件在备份门禁内得到核对，r6/r5/r4/r3 的 25/25/25/32 文件历史备份继续保留。部署回执 SHA-256 为 `8df400f43c42ee2b9de7a7baa021861887d369e51bc368e7d004f0e2b4093a9c`，初始只读 `verification_passed` 文件 SHA-256 为 `60f22991c14707a91b6a07dcfd252f2f476f4d40a3f3fc333fc2a8904c7b4721`。这项初验未覆盖后续公开下载、真实合作或 Fresh 行为。

初验后官网发布器的持久 `published` 回执 SHA-256 为 `4404a1e3d1798bb5c46cd88ff9b334f1afda8fa12bc2f5808363633b2e729463`。公网七入口的 HTTPS 字节校验包括五份 v0.9.5 接入 ZIP、网页清单及原邀请 PDF；网页清单 SHA-256 `779159687fc50116ac605cc2fedd636402714be11097fda03c77b42adaf29fe4` 与 GitHub 正式发布清单是不同文件，不能混用。邀请 PDF SHA-256 `39b9acb820373e059cd58bba0a14dffe266c3b7324db6511e73c52991a5b06da` 未变，旧 v0.9.4 下载目录保存在私有备份。发布时 Nginx 容器重建，Web/Platform 容器未变。原 Alice/Bob 升级执行前，进程 ID 守卫曾发现与预检快照不符并停在零写入阶段；随后已用新只读进程核对和一致备份继续，正式结果见下段。

重新只读核对并固定预检后，原 Alice/Bob 正式 v0.9.5 升级回执 `upgrade_passed` 文件 SHA-256 为 `934811a3ce18b9dd2336af1c48720ab4a9cbe686991628dc8ac49ef20b247202`，runtime-ready 回执 SHA-256 为 `6e76194c30568f43e8b7c02f74810f795ff0e56ba42c1be079293e69f6f7c3d8`。独立后验 `upgrade_postcheck_passed` 文件 SHA-256 `74176759fbde17a026bbac4c617b8eed5774c1dfce22ab563b896b6dfb76fcf0` 再次核对两侧 runtime `0.1.10`、connector `1.5.12`、原身份与配对、单一消费者、无 active work、原任务和业务状态稳定；21 份一致备份逐库 `quick_check=ok`。升级未恢复数据库、创建新身份、改变范围或提交业务请求。此前被审批门禁挡住的 v5 尝试没有进入业务写入；用户随后明确授权限定的原双方协议消息及终态后仅四项合成任务撤销。

唯一 v5 正式续测 `PASS` 退出，60 项检查通过，原始报告 SHA-256 为 `02923e278c62c5b5242c7e09133c0012730099ed586e3c60b9be4522184fb577`。两侧协作均为 `closed/agreement_only_complete` 且同一协议 ID，worker 均处于 `paused/collaboration_complete`；两条正向任务返回 `revoked`，两条原拒绝任务的签名撤销请求均有 `complete` 回执和数据库 revision 增量，原拒绝批准继续 `denied` 且没有邀请派发，维护已撤销。逐项字段与回执核对通过，浏览器页面错误为零。没有把 `result=PASS` 本身当作四条任务终态。

独立 mode=ro 后验 `v5_post_invariant_passed` 文件 SHA-256 为 `51e15dbeac1e91d918f0dc82ae15d6529e273aca8742d35be12aa3aba07492ae`，固定上述 v5、升级和 runtime-ready SHA。它分别对 21 个当前 SQLite 数据库和 21 份一致备份执行 `quick_check`，读取两侧原 profile 的精确任务与协作记录，确认四项任务均已 `revoked`、两项拒绝审批仍为 `denied`、同一协议已关闭、维护撤销、待审对端协作内容为零。原身份配置哈希、配对的 Console URN 与 16 项方法范围不变；两侧各一个连接消费者且无 active work。这项后验只覆盖原 Alice/Bob，不能代替独立 Fresh 首装与业务后的云端复核。

Fresh READY 回执 SHA-256 `4ffc84087dedd9e8432e94fd2f8f5b3caf7f79bbda683e139acd0f0748e509bc` 在原双端协议终态、四任务清理和独立后验通过后签发。Fresh v0.9.5 终态摘要 `passed` 文件 SHA-256 为 `4d42f62c0de3bf6e5142b303578de5d851b9a6ad54f2014da496fbdb51329e18`，19 项阶段记录的文件哈希经根任务独立逐项复核。正式官网包落入隔离新 Python 和新身份；领取未知结果通过同一请求恢复，整个领取仅一次 POST。欢迎和 nonce 两次模型阶段各有一次真实 MiniMax API 调用，并在页面刷新后核对完成结果。最终只精确删除 Fresh 新连接、撤销 Fresh 本机配对并停止三个 Fresh 进程；Fresh 身份和数据库保留，失败及恢复证据没有覆盖。

Fresh 后原双 Agent 独立只读保护报告 `post_fresh_original_pair_preserved` 文件 SHA-256 `3762fa7e3fa83bc151bd5a7eb97a3b28240fffb0208ac6842132de1e01a9622f`，引用上段 Fresh 摘要和 v5 固定报告。当前与备份 SQLite 各 21 库逐库 `quick_check=ok`；Alice/Bob 原身份密钥、配对和方法范围保持，同一协议仍关闭、四项精确任务仍撤销、该协作 Native 待审数为零、维护停止且各侧无 active work。这轮只读审计没有应用写入和网络调用。Web 原连接集合恢复基于 Fresh 网站账户清理前后精确快照，未另行登录原用户网站账户。最终云端门禁随后单独执行并通过。

Fresh 与原双方保护完成后，r7 一次性云端最终验证本地观察文件 `web-preview-version-r7/observed-final-observe-4-r7.json` 的 SHA-256 为 `b5516bc238f02f0bcfe9f2f3d7a9c85e3dd9758cb7a25cf2e62d7bea562e6bb7`。远端 supervisor 的持久摘要 SHA-256 为 `73dbf75b95859e0f4151b5540477107f803ab4e0caee0df41e03eaaeba9feb52`，嵌套验证摘要 SHA-256 为 `e24ff6d1e0596d5ac4af235e141b900d9a605c623584070f359bcef951168609`；三者来源不同，不能互换。supervisor `finished`、`passed=true`、退出码 0，嵌套 `verification_passed`，公开包阶段为 `v0.9.5_after_publication`。

最终只读门禁再次核对线上 Web 镜像 `sha256:d47d5d4e19d6309f200efd3904eacd254f4ad6b41e3de657b018b963504231d3`、保留的 Platform 镜像 `sha256:87799b78e0d51b067759c498bd1bb9deda900e8c0b243bb62be45d49cd7abea1`，Web、Platform、Nginx 三容器均运行且无重启/OOM。v0.9.5 公网七文件逐字节检查、四个生产数据库 `quick_check=ok`、47 User/42 Agent 原基线记录、凭据和 19 受保护文件、r6/r5/r4/r3 备份链仍通过；所监测 `database_locked`、`fatal_or_panic`、`pool_timeout`、`upstream_error` 日志计数均为零。此处的只读门禁不替代原双 Agent 协议与 Fresh 真实模型的各自回执，也没有声称真实 Mac 首装或真人邮件、日历业务。

## 证据、环境和限制

本地证据位于忽略目录 `build/personal-style-release/`：r5/r6 原始回执，r7 的 `artifact/web-linux-unit-tests.log`、`artifact/platform-binary-parity.json`、`artifact/overlay-verification.json`、`docker26-loader-verification.json`、四阶段 `observed-*-observe-*-r7.json`、`observed-deploy-progress-3-r7.json`、`observed-public-v095.json` 与 `observed-final-observe-4-r7.json`，`official-v095/verification-official-v095.json`，`synthetic-v095-original-upgrade.json`、`synthetic-r6-v5-runtime-ready.json`、`synthetic-v095-original-upgrade-postcheck.json`、`synthetic-app-r6-terminal-continuation-v5.json`、`synthetic-r6-v5-post-invariant.json`、`fresh-v095-terminal-summary.json`、`synthetic-r6-post-fresh-preservation.json`，以及 `r7-production-ui-capture.json` 与三张 r7 截图。当前云端私有发布与备份目录为 `/root/agent-comm-releases/personal-software-style-20260928-r7/`；r6/r5/r4/r3 目录逐项保留。所有密钥、身份目录、数据库、私人原文和原始日志均留在受控环境，不进入本记录。

r5 初始验证是云端只读门禁，不代替真实业务写入后的最终复核。r3 旧 Platform 备份经哈希复核但没有在 r5 时刻重新生成；新 Web 在线备份是逐库一致快照，不代表跨库原子快照。模型输出、协议状态、账户快照和外部副作用应分别验证。本轮未执行真人邮件或日历操作，也未进行真实 Mac 安装。

**GitHub 待处理：** 四仓远端分支收敛到 `main` 后补记各合并提交，以及它们与线上 r7 固定源码的关系。部署及本轮约定的全流程验收已完成；纯文档或 PR 合并不代表线上再次部署。
