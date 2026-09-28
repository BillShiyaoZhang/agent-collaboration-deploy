# 官网、控制台与 Admin 视觉更新及接入包配套发布（2026-09-28）

**状态：本轮部署与约定的全流程验收完成，四仓仅保留 `main`。** 官网、控制台、Admin 与 r7 Web 已部署；v0.9.5 GitHub 正式发布的 16 项资产及官网公网七个下载入口通过独立校验。原 Alice/Bob 已升级正式 v0.9.5 接入包，真实协作达到双方同一协议终态并精确清理四项合成任务；独立 Fresh 首装、两回合真实模型与精确清理、原 Alice/Bob 在 Fresh 后的只读保护复核及最终云端复核也通过。本记录不会将页面显示、请求提交、队列 ACK 或局部审批写成业务完成。

## 范围与版本

官网以大字和一组有光泽的绿色、淡紫色视觉素材讲述一个核心场景；示意内容明确标注。控制台采用暖白、墨绿与更清晰的层级，保留原有真实双侧栏、对话、连接、授权和归档入口。Platform Admin 采用同一暖白与墨绿色系，维持紧凑表格、状态和操作确认。业务数据仍来自真实服务，不填充设计稿示例数据。

| 仓库 | r5 Web 补丁部署所固定的提交 |
| --- | --- |
| 部署 | `b81e54eb065b6977282c310277379ad0f23046f6` |
| Web | `9f7ff445f3ea4097cd8a4d3c3f2ce6e4570afc3c` |
| Platform | `ba779d12c3e9d46393e22502ff2efa69da1d7cf8` |
| SDK | `9d3505335d2c50d19811ccef69cdd3f69926b851` |

r6 修复部署固定部署仓库 `c378884cac78c8b718bea92de8e73af6809b6d73`、Web `30b84550f8cb5a8b643ca2f2a21139c9335bc209`，Platform 和 SDK 提交仍为上表原值。这个固定源码版本是云端切换的凭据；后续验收文档提交不改变已部署的应用源码。

正式 v0.9.4 接入包是另一次固定源码快照：部署 `295d8fb90e1ad01d1c42347592324d48918cb7b3`、Web `32891c2ae1c24297350cd0280445c235e345d55d`、Platform `ba779d12c3e9d46393e22502ff2efa69da1d7cf8`、SDK `9d3505335d2c50d19811ccef69cdd3f69926b851`。后续 r3、r4、r5 Web 补丁未重发 SDK，也不改变正式包内部的 Web 源码版本。正式发布的 16 项 GitHub 资产、官网清单与五份 ZIP 已逐字节校验；旧公开邀请 PDF 保留。Mac 包经过归档、哈希和信任链校验，**本轮没有真实 Mac 首装**。

首次公开下载发布因暂存目录权限使 Nginx 无法读取清单，发布器回退至 v0.9.3 并保存失败暂存及回执。仅修正新公开目录的读取权限后，独立恢复回执绑定旧版、失败阶段和重试前容器；再次发布 v0.9.4 并通过公开下载检查。该恢复不重置用户身份或数据库。

## 本地构建和 r5 生产切换

Web Linux 测试 **388/388 通过**，生产构建通过。r5 标准镜像与复用 r4 精确基础镜像的紧凑增量镜像经过配置和完整文件系统对比；Docker 26 加载正、负例及固定源码包、四仓 Git bundle 审核通过。标准便携归档仍留在本地；云端只上传经校验的紧凑增量归档，不在云端构建源码。

| 固定产物或位置 | 值 |
| --- | --- |
| r5 Web 镜像 ID | `sha256:cdeb51ba610bbef04cd75a4fae1376ca229219597c730f4558a8bcd7a9918936` |
| 保留的 Platform 镜像 ID | `sha256:87799b78e0d51b067759c498bd1bb9deda900e8c0b243bb62be45d49cd7abea1` |
| 固定源码包 SHA-256 | `5a6c4954d0eea0861e66b55b263677c59ec09c8b944e96c2f4720a11267f3308` |
| 紧凑增量归档 SHA-256 | `f320b0ea054613fb1a333f5a990b720b822738d642880231bba5ad261898a7ef` |
| 云端私有发布目录 | `/root/agent-comm-releases/personal-software-style-20260927-r5/` |
| 原 Web 回滚镜像 ID | `sha256:c58050321ccbc96a4bc85b6238a7c00f0f31cf21a8f992cbf80061c9535540e7` |

2026-09-28 02:29:16 UTC，r5 一次性部署回执为 `deployed`，并在切换流程内完成初始只读验证。审计、镜像预加载、新备份和部署四阶段均以实际子进程退出码 0、完整输出与持久文件校验通过。只替换 Web；Platform 和 Nginx 容器未作为本次切换目标，Nginx 仅重载配置。部署保留实时数据库，不使用旧备份覆盖切换后的写入。

本次新增**当前 Web 数据库在线备份**和 19 个受保护文件备份；原 r4 的 25 文件、r3 的 32 文件备份逐项核对并保留。Platform 未改变，其 Registry、MQ、审计数据库沿用 r3 时的备份引用；这些旧快照不能被描述成 r5 时刻的新 Platform 数据快照。回滚位置为上表私有目录中的 `pre-cutover/`、原 Web 镜像和原源码提交。具体恢复仍须先核对当前数据，不能盲目回写旧数据库。

## r6 修复构建与生产切换

r6 Web 的 Linux 全量单元测试 **388/388 通过**，真实 React/Chrome 组件回归 14 项断言、类型检查与相关单元测试 20/20 通过。固定源码包 SHA-256 为 `8b541ff6b9aceef8c9ff6d67bb8f8e8a8fb3aac1ed819b16d19f0c7643509d68`。发布 Web 镜像 `sha256:d541f6e75fa9db32c1a1fb4a2a4bd6a300f9364f11f8741c2ab84f0a288775fb` 经过与完整构建的配置和文件系统逐项核对：复用 r5 的 34 层，新增 4 层。紧凑归档 SHA-256 为 `d09a5585d208d6347123ceb005d8ea3736ac4d4916d552272bd926f794f62960`（162,562 字节）；独立 Docker 26.1.3 测试确认缺少 r5 基础镜像时拒绝加载，已有精确基础镜像时加载到预期镜像 ID。

云端私有发布目录为 `/root/agent-comm-releases/personal-software-style-20260927-r6/`。21 个上传文件经服务器端独立 SHA 与大小校验；审计、镜像预载、新备份、部署四阶段的持久回执均为 `finished`、退出码 0、`passed=true`。r6 新建当前 Web 一致快照并校验 19 个受保护文件，保留 r5/r4/r3 的 25/25/32 文件历史备份；Platform、Nginx 容器和原有数据库、身份未被重建。2026-09-28 04:13:49 UTC，Web 切换完成；初始只读验证 `verification_passed`，验证文件 SHA-256 为 `64f7aaf5955dc84ab4d4c88159ef379e1005d15b43f3a97bfea6c0983581ad0b`。这项门禁不代表合作任务或新用户首装已经完成。

## v0.9.5 正式包与 r7 生产切换

[SDK v0.9.5 GitHub 正式发布](https://github.com/BillShiyaoZhang/agent-comm/releases/tag/v0.9.5)含 16 项资产。下载回执逐项核对 GitHub 声明的摘要和大小；随后在不执行下载代码的离线校验中，正式清单、`SHA256SUMS`、四种平台接入 ZIP 的八项载荷及固定信任锚、源码 ZIP 的固定 Git 对象、文档 ZIP 和 wheel 成员均通过。GitHub 正式清单 SHA-256 为 `2f844a6dcfd8c7a84d595a38fbf6319655b09272b2a3ebbc4fb6702bcd8bbc72`；配套 runtime 为 `0.1.10`，Hermes connector 为 `1.5.12`。这些结果证明正式资产，不代表原 Agent 已升级。

r7 固定源码为部署 `a573f90955ffe5b3d6dba6e05e935978e317acdb`、Web `f7e49a138e7036f25ae8b537b79fa6915a3d0525`、Platform `afc7d6d8c641cf43af563382d70def3f3eb7afc9`、SDK `ff1419c156dee590d100ceeaea05aacf49c037e4`；源码包 SHA-256 为 `38d584e1f1a5362a261683431c9002867a02ef7efd0eb5a28f849ff24fb016eb`。Web Linux 单元测试 388/388 通过。新 Web 镜像 `sha256:d47d5d4e19d6309f200efd3904eacd254f4ad6b41e3de657b018b963504231d3` 与完整构建镜像的配置和文件系统核对一致，复用 r6 的 38 层并新增 4 层；78,469 字节紧凑归档在独立 Docker 26 中验证了缺少精确基础镜像时拒绝、基础镜像存在时加载到目标镜像。发布时没有向服务器上传 192 MB 便携归档。

Platform 与 SDK 的新固定提交进入源码包和官方接入包，但线上 Platform 容器继续运行旧镜像 `sha256:87799b78e0d51b067759c498bd1bb9deda900e8c0b243bb62be45d49cd7abea1`。新旧 Platform/SDK Go 构建输入逐项一致，固定源码构建的候选可执行文件与旧镜像内可执行文件 SHA-256 同为 `dd5f264d24e10e3bb8f4a69264c93b2c9434203f7e17dcf26e5492b3a961a696`；这项字节级证明支持保留现有 Platform 容器，不表示新 Python SDK 已自动安装到任何 Agent。

云端私有发布目录为 `/root/agent-comm-releases/personal-software-style-20260928-r7/`。审计、镜像预载、当前 Web 新备份与部署四阶段均有 `finished`、退出码 0、`passed=true` 的持久回执；只替换 Web，保留 Platform 服务和四个现有数据库，未恢复旧库或重新初始化身份。新备份核对了 19 个受保护文件，r6/r5/r4/r3 历史备份的 25/25/25/32 个文件仍在。切换后新 Web 镜像与保留的 Platform 镜像匹配固定发布设置；初始只读验证为 `verification_passed`，验证文件 SHA-256 为 `60f22991c14707a91b6a07dcfd252f2f476f4d40a3f3fc333fc2a8904c7b4721`，部署回执 SHA-256 为 `8df400f43c42ee2b9de7a7baa021861887d369e51bc368e7d004f0e2b4093a9c`。初验不代表官网公开下载、业务续测或最终不变性复核完成。

r7 初验后，官网发布器的持久 `published` 回执 SHA-256 为 `4404a1e3d1798bb5c46cd88ff9b334f1afda8fa12bc2f5808363633b2e729463`。公网 HTTPS 对五份接入 ZIP、网页清单与保留的邀请 PDF 共 7 个入口逐字节核对通过；官网清单 SHA-256 为 `779159687fc50116ac605cc2fedd636402714be11097fda03c77b42adaf29fe4`，旧邀请 PDF SHA-256 仍为 `39b9acb820373e059cd58bba0a14dffe266c3b7324db6511e73c52991a5b06da`。旧 v0.9.4 下载目录以私有备份保留。官网发布重建了 Nginx 容器，Web 和 Platform 容器保持不变；公开下载通过仍不代表原 Agent 升级或 Fresh 首装完成。

r7 公网浏览器还核对了中文首页桌面和手机视图、登录页桌面视图：三页均 HTTP 200，标题符合预期且没有页面错误；三张截图已目视检查。这只覆盖所拍的三个页面与视图，不代表全站交互或接入流程已通过。

原 Alice/Bob 的正式 v0.9.5 接入包升级回执为 `upgrade_passed`，SHA-256 `934811a3ce18b9dd2336af1c48720ab4a9cbe686991628dc8ac49ef20b247202`；两侧 runtime `0.1.10`、Hermes connector `1.5.12`。升级前的 21 份 SQLite 一致备份经独立后验逐库 `quick_check=ok`，未做数据库恢复、创建新身份、改变范围或提交业务请求。独立后验 `upgrade_postcheck_passed` 文件 SHA-256 为 `74176759fbde17a026bbac4c617b8eed5774c1dfce22ab563b896b6dfb76fcf0`，核对原身份与配对、单一连接消费者、无 active work、原协作任务及业务状态稳定；配套 runtime-ready 回执 SHA-256 为 `6e76194c30568f43e8b7c02f74810f795ff0e56ba42c1be079293e69f6f7c3d8`。这仅证明原位升级与升级后状态，不能代替有界协作的协议终态。

## 业务验收边界

这轮同时收紧了对端内容审核和权限准入。r3、r4 的修复已分别解决旧占位内容遮蔽原生回执、完整 Native 预览版本选择问题；r5 只排除已确认的本机派生字段，并把网页批准绑定到用户实际点击的审核行、Agent、消息和摘要。历史占位或旧版本批准不会自动批准新的规范版本。

原 Alice/Bob 已有双模型完成、108 项导航及原消息正反向审核和已读的独立证据。r5 有限流程在拒展示消息之后，于 Alice 选择合作对象时停止，当时未提交新的合作任务。r6 表单修复后，原双方在同一任务上真实完成了任务准备、分别审核、邀请和加入；Bob 的提议也经 Native 与网站两层审核，双方各自签发第二轮有限 worker 策略。第二轮 10 分钟上限内仍未形成协议终态，未做四任务清理。原提议、邀请、加入和审核均不能靠重放制造通过结果。原两套身份、密钥与配对范围必须保持；新 Fresh 测试使用独立身份。

本地分析将选择框持续不可用定位为协作能力说明的 React effect 依赖反复变化：`invoke` 与 `canMutate` 的函数引用会随状态刷新改变，读取在完成前被反复清理，三项必需动作没有稳定呈现在表单。r6 Web 提交 `30b84550f8cb5a8b643ca2f2a21139c9335bc209` 改为按 Agent、Console 身份和实际权限值触发读取；本地组件测试和上述云端初验已通过。原 Alice/Bob 现场有限协作最终以以下 v5 与独立后验回执验收。

后续 v4 有限续测保存了独立失败回执：Bob 原提议审核成功且双方第二轮主人授权成功；原双方 task 仍活跃，协作仍等待。只读持久状态显示没有待审提议或乱序事件，但 Bob 的 `peer_review_required` 等待标记未清，worker 因此停在等待对端。正式 v0.9.5 中的修复在入站审核清空后恢复状态，并在受信任 worker tick 中幂等修复已持久化的旧标记；临时 SQLite 回归及 Python 全量 200 项通过。升级首次预检因进程 ID 与快照不符停在零写入阶段，重新只读核对并固定预检后完成上述正式升级。用户明确授权限定的原双方协议消息及仅四项合成任务终态后撤销；唯一 v5 有限续测随后以 `PASS` 退出，60 项检查通过。报告 SHA-256 为 `02923e278c62c5b5242c7e09133c0012730099ed586e3c60b9be4522184fb577`：Alice/Bob 对同一 `agreement_id` 的协作均为 `closed/agreement_only_complete`，两侧 worker 进入 `paused/collaboration_complete`；两项正向任务 `revoked` 且维护已撤销，两项原拒绝任务的签名撤销回执 `complete`、任务 `revoked_verified`，拒绝批准没有改写或发出邀请，浏览器页面错误为零。此处以每侧每条任务回执判断，不以最终 `PASS` 字段替代清理检查。

独立原位后验 `v5_post_invariant_passed` SHA-256 为 `51e15dbeac1e91d918f0dc82ae15d6529e273aca8742d35be12aa3aba07492ae`，绑定上述 v5、正式升级和 runtime-ready 回执。它在只读模式核对当前 21 库及一致备份 21 库各自 `quick_check=ok`，逐侧确认同一协议关闭、四项精确任务确为 `revoked`、原拒绝批准仍为 `denied`、维护已撤销、原身份配置哈希与配对范围不变、单一连接消费者、无 active work。该后验不代替独立 Fresh 首装和最终云端复核。

## 独立 Fresh v0.9.5 首装与原双方保护复核

原双方通过后才签发 Fresh READY；固定候选回执 SHA-256 为 `4ffc84087dedd9e8432e94fd2f8f5b3caf7f79bbda683e139acd0f0748e509bc`。独立 Fresh 终态摘要 `passed`，SHA-256 为 `4d42f62c0de3bf6e5142b303578de5d851b9a6ad54f2014da496fbdb51329e18`；其 19 项阶段记录经根任务独立逐项哈希复核。正式官网 v0.9.5 包安装到隔离的新 Python 与新身份，网页领取在未知结果恢复后总计仅一次 POST。欢迎与后续 nonce 两回合分别有一次真实 MiniMax API 调用、完成的页面结果及刷新后保留的核对；这些状态分别有提交、模型完成和浏览器持久显示证据。

清理只精确删除 Fresh 新建的 Web 连接，撤销 Fresh 本机配对并停止三个 Fresh 进程；Fresh 私有身份与数据库留存以供审计，没有用重新初始化掩盖结果。原连接集合恢复的证据与该精确清理绑定，失败及恢复记录保留。Fresh 完成后，独立只读的原 Alice/Bob 保护报告 `post_fresh_original_pair_preserved`，SHA-256 为 `3762fa7e3fa83bc151bd5a7eb97a3b28240fffb0208ac6842132de1e01a9622f`。它核对原两侧当前 21 库和备份 21 库各自 `quick_check=ok`、原身份密钥与配对范围不变、同一协议保持关闭、四项任务仍撤销、该协作 Native 待审数为零、单一连接消费者且无 active work；未对原业务做额外写入或网络调用。原连接集合的对比范围是 Fresh 使用的网站账户清理前后快照，并非另一次原用户登录检查。最终云端只读复核随后以独立回执完成。

## 业务后的最终云端复核

Fresh 清理及原双方保护复核之后，r7 一次性云端最终验证的本地观察文件 `observed-final-observe-4-r7.json` SHA-256 为 `b5516bc238f02f0bcfe9f2f3d7a9c85e3dd9758cb7a25cf2e62d7bea562e6bb7`。远端 supervisor 持久摘要 SHA-256 为 `73dbf75b95859e0f4151b5540477107f803ab4e0caee0df41e03eaaeba9feb52`，嵌套验证摘要 SHA-256 为 `e24ff6d1e0596d5ac4af235e141b900d9a605c623584070f359bcef951168609`；supervisor `finished`、`passed=true`、退出码 0，嵌套结果 `verification_passed`，公开包阶段为 `v0.9.5_after_publication`。这些不同层的 SHA 分别对应本地观察文件、远端持久记录和验证摘要，不能互换。

最终只读门禁核对 Web 镜像 `sha256:d47d5d4e19d6309f200efd3904eacd254f4ad6b41e3de657b018b963504231d3`、保留的 Platform 镜像 `sha256:87799b78e0d51b067759c498bd1bb9deda900e8c0b243bb62be45d49cd7abea1`；Web、Platform、Nginx 三容器均运行，重启和 OOM 计数均为零。v0.9.5 公网七文件字节、四个生产数据库 `quick_check=ok`、原 47 User/42 Agent 全部基线记录、凭据与 19 个受保护文件、r6/r5/r4/r3 备份链继续通过；监测范围内 `database_locked`、`fatal_or_panic`、`pool_timeout`、`upstream_error` 日志计数均为零。该门禁本身是只读部署与发布复核，业务完成由前述原双方及 Fresh 独立回执支持。没有执行真实 Mac 首装或真人外部邮件、日历业务。

证据保存在忽略的 `build/personal-style-release/` 下，包括 `web-preview-version-r5/artifact/`、r6 与 r7 各阶段 `observed-*-observe-*.json`、`web-preview-version-r7/observed-deploy-progress-3-r7.json`、`web-preview-version-r7/observed-final-observe-4-r7.json`、`official-v095/verification-official-v095.json`、`r7-production-ui-capture.json` 和三张 r7 页面截图、`synthetic-v095-original-upgrade.json`、`synthetic-v095-original-upgrade-postcheck.json`、`synthetic-r6-v5-runtime-ready.json`、`synthetic-app-r6-proposal-continuation-v4.json`、`synthetic-app-r6-terminal-continuation-v5.json`、`synthetic-r6-v5-post-invariant.json`、`fresh-v095-terminal-summary.json`、`synthetic-r6-post-fresh-preservation.json` 及各自固定的阶段与恢复回执。各记录只支持各自阶段；私人凭据、数据库、原始消息与日志未提交。本轮没有真实 Mac 首装、真人邮件或日历操作。

**GitHub 收敛：** 根仓 [PR #2](https://github.com/BillShiyaoZhang/agent-collaboration-deploy/pull/2) 以普通 merge 合入 `main`，合并提交为 `5b85109fa5400c9b6e4d698db6a07c178eacdee3`，两个父提交分别为原 `main` `0c807a330d9c2e277ac9860fd72e8b537b68ecf1` 和最终验收文档 head `472dd4ec620be24b9a5cc9a8caee43ba3511edf8`。删分支后 Web、Platform、SDK 的远端 `main` 分别为 `7e154a3531e799c53b72d0bc80a24c966476a95c`、`b89792230bf28ce5862dff651fb3dceeb8827a5d`、`05d1b28220aa9b938361b35c8f8791da79026596`；四仓本地与远端均只保留 `main`，SDK `v0.9.5` 标签仍指向发布提交 `ff1419c156dee590d100ceeaea05aacf49c037e4`。这些 `main` 合并提交包含上线时固定的 r7 源码提交；本记录的纯文档补记不表示服务器再次部署。
