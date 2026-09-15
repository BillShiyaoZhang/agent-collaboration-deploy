# 通知与协作部署验证

日期：2026-09-15。部署到现有服务器，并升级已连接 Web 的本机 Hermes。

## 已部署版本

| 组件 | 版本 / 提交 |
| --- | --- |
| Deploy | `0c162e0e35437ec9dfd3139c8cba53fc27c36006` |
| Web | `dc3b4465ba97da5dbafa4f07b4059633098eeeae` |
| Platform 的 SDK 引用 | `97366a352b3a312aa022fee8944136ddf7298b90` |
| SDK | `14a8057e32303791d90fbe5029d9d81b7807bc6d` |
| 本机 runtime / Hermes connector | `0.1.1` / `1.4.0` |
| Web Build ID | `4l9U8Z3DCECtt__VzoJEx` |

Web 镜像：`sha256:0ceeb30ac2153538d02d36f8b2106f9bae52d25caf5f3dd3abd1b1c0db34c2a9`。
入口：[通知中心](https://agent-communication.online/dashboard/notifications)。

代码已保存为本机提交，并通过现有 Workbench 传到项目服务器。用户另行明确授权 GitHub 推送；截至本次记录，直连和现有本机代理均在 TLS 握手时失败，**尚未推送 GitHub**。打包快照内的 remote-tracking refs 不作为已推送证据。可选的快照 Git 跟踪信息清理被自动审批拒绝，未执行。

## 部署验证

- 服务器隔离候选使用 `--network none`、合成账号和合成数据库，未复制真实业务行。
- 新 SQL 连续执行两次，旧表行保持不变；四张通知表、外键和 SQLite 完整性通过。
- 沿用已核对版本的 Linux 运行依赖；补充的 Prisma 生成器与锁定官方 npm 包的 SHA512、文件字节一致。仅针对当前 Linux 架构生成客户端，原始 schema 保留。
- 生成器复制的 Linux 引擎与基镜像字节一致；当前构建及保留的旧静态资源共 201 个文件通过校验。
- 隔离候选通过登录、分片会话、账号隔离、通知筛选、非法输入拒绝、数据库 API、前端资源和后台同步验证。
- 北京时间 14:51 完成 Web 切换；线上健康检查、匿名接口 401、后台新同步、四张通知表和数据库完整性通过。
- 真实 User/Agent ID、原密钥、环境变量和数据卷保留；原登录会话可继续使用。Platform 与 nginx 容器未重建，nginx 仅重新加载。

## 本机与真实 Web 验收

升级前备份旧插件、配置和数据库，并在 Gateway 空闲后正常停止。升级后已验证唯一 connector 安装来源、Gateway 运行和提醒后端可读。

经用户明确确认，只为现有本人 Web 配对增加 `attention.list`，原身份、其他权限和到期时间保持不变。Web 的持久提醒基线已完成，真实连接状态为 `ready`。

使用五分钟自行到期的 self 待决任务 `attention-deploy-20260915T065314Z`，未新增联系人，未确认、未分发，操作数为 0。

| 实机检查 | 结果 |
| --- | --- |
| 新待办自动出现 | 通过；无需刷新，Bell 与通知中心显示 1 未读 / 1 待处理 |
| 已读不等于已处理 | 通过；标为已读后显示 0 未读 / 1 待处理 |
| 跨标签、刷新后保持 | 通过；仍为 0 / 1 |
| 定位具体问题 | 通过；打开对应任务并展开原生问题，没有 Web 批准按钮 |
| 自然到期及源端收敛 | 通过；北京时间 14:58:14 到期后，待处理降为 0，历史保留“已到期”；Hermes 源端及 Web 持久记录均为 `expired` / revision 2，执行操作仍为 0 |

已读按事项版本记录：原 open 版本已读后，源端 expired 新版本到达仍会产生一条未读更新（1 未读 / 0 待处理）。业务截止时待处理先归零，与随后到达的新版本未读是两个独立状态。阅读该终态后，两个标签均为 0 未读 / 0 待处理；保留通知中心，已关闭临时第二标签。

本次线上验证覆盖提醒闭环及协作任务的定位。双边协作 v2 的提议、双方接受、约定回执、取消和恢复，已在[此前隔离集成验证](COLLABORATION_ATTENTION_2026-09-15.md)通过；本次没有代替真实双方进行授权或作出业务承诺。

### 首轮部署时尚未通过的实机检查

- 当前 Codex 内置浏览器显示“浏览器已阻止系统提醒”，开启按钮不可用；没有验证真实浏览器系统弹窗。
- Hermes Desktop 的 `Agent Comm 待办` companion 已安装、后端已启用，但宿主输入保护阻止自动操作前端开关；没有绕过保护或声称桌面弹窗成功。
- 本版浏览器提醒要求页面运行，未实现关闭页面后的 Web Push。

### 追加系统弹窗验收（15:10 起）

使用 Computer Use 操作本机 Hermes，用户协助开启外部 Edge 站点通知并观察横幅。内嵌浏览器仍禁用系统通知；外部 Edge 的窗口读取超时，浏览器连接不可用。Computer Use 拒绝打开 Windows 设置，未绕过该限制。用户确认 Windows“请勿打扰”已关闭。

- Hermes 的全局通知、Plugin notifications 均开启；启用了协作待办插件的独立 Desktop 开关。
- Hermes 设置中的测试通知在 15:10:05 进入 Windows 接收、会话投递链；这不代表协作通知或横幅目测通过。
- 两条新的五分钟 self 待办分别在 15:40:14、15:42:58 创建，两端应用内均同步成功。用户报告没有看到系统横幅。
- Web 精确站点的“Agent Comm 协作提醒”于 15:43:59.057 进入 Windows 通知存储，随后投递到 session 1，TrackingId 14261。该网站的系统通知配置为 `s:banner=1`、`s:toast=1`。
- 截至 15:50:42，未检出上述两条源对应的 Hermes Windows 通知事件。应用前台等宿主门控可能抑制通知；尚不能确定本次的具体原因。
- 15:49 查询 Windows Shell 返回 `QUNS_BUSY`，仅代表该查询时刻的状态，不能当成“勿扰已开启”或更早未显示横幅的确定原因。
- 两条源均已自然到期，未批准，`operations=0`。

发现 Hermes 桌面端动态插件路由被 React Compiler 缓存：侧栏入口已出现，但 `ChatRoutesSurface` 丢弃 `useContributions` 的返回值，使晚加载插件的路由表未参与缓存依赖。已用实际安装编译函数、真实 React/ReactDOM/Router 与插件注册器复现；修正依赖后验证晚注册和重新扫描均可更新。15:56 通过正常“Reconnect gateway”刷新桌面连接，实机待办中心恢复显示，含已失效的三条测试历史。永久宿主补丁另行保存在本机验证目录，部署状态以最终记录为准。

另为 companion 的状态栏、应用内通知和系统通知点击补充了显式显示 workspace 面板的兼容处理，防止相同路由被会话面板遮挡。该修复已通过 Desktop 12 项测试并安装到本机；它不单独解决上述宿主路由缓存问题。

以上为前两轮结果，后续受控复测如下。追加证据位于 `build/system-notification-test/`，不包含其他站点的通知正文。

#### Hermes 最小化复测：通过

加载含安全诊断的 companion 后，实际界面确认 `Web Locks: available`、`secureContext: true`，无锁请求错误。诊断只记录通知阶段、计数、时间、前后台布尔值及固定错误名，不保存内容、身份、异常正文或堆栈。Hermes 的 Rescan 会跳过已知模块路径，最终通过窗口刷新确认加载了新代码，不能把点击 Rescan 本身当成新版本已生效。

16:03:45 创建新的五分钟 self 待办 `system-popup-hermes-20260915T080345Z`。创建前已通过原生最小化按钮将 Hermes 最小化，距离重新连接已超过启动静默期。

- 16:03:52.632，Windows 收到 `com.nousresearch.hermes` 通知；16:03:52.638 投递到 session 1，TrackingId 14263，完整事件 2416 → 2418 → 3052 → 3153。
- 用户明确确认“看到了 Hermes 系统横幅”。至此 Hermes 协作提醒的系统横幅验收通过。
- 实际插件诊断显示站内调用 returned、OS 调用 returned_unconfirmed、尝试 1 次，调用时 `hidden=true`、`focused=false`，无错误。OS 显示成功依赖上面的 Windows 事件与用户观察，不能由这个返回值单独推出。
- 16:06 实机再次核对待办中心：显示 1 未读 / 1 待处理、对应 task ID、恢复指令和原生对话入口；未点击批准或提交恢复指令。
- 16:09:03.931 复核最后一条测试源已自然到期，attention 为 `expired` / revision 8；task 从未批准，`authorized=false`、`operations=0`。
- 原生前台/偏好等门控保持生效。这次通过不能反推前两轮未弹出的唯一原因，但支持最小化后通知链正常。

最终验收范围：**Hermes 系统横幅通过；浏览器到 Windows 的接收和投递通过，但用户未确认看到浏览器系统横幅。** Browser 站点横幅设置已开启，用户确认勿扰已关闭；未查明该轮未显示横幅的确定原因。

Companion 导航及诊断共通过 19 项行为测试，当前安装文件 SHA-256 为 `6157a7148b690dcc2da05533b3ee6cae7dc35d8acb116ae22ee105039c8446ee`。Hermes 宿主永久路由修复的 renderer 候选已完成构建和真实编译回归，**未安装到宿主**；本次通过正常连接刷新恢复了现用详情页。[宿主源码补丁](patches/hermes-dynamic-routes-110baa0.patch)针对 `110baa095bc7135a0624557a9cc35df0f98ece0f`，候选与审查说明位于 `build/attention-deployment/hermes-route-patch/`。

## 备份与回滚

服务器 release：`/root/agent-comm-releases/attention-collaboration-20260915`。

服务器备份：`/root/agent-comm-backups/attention-collaboration-20260915-20260915T065118Z`，含旧镜像引用、原源码、环境文件及通过完整性检查的在线数据库备份。

**必须保留备份中的 `source`**：既有 nginx / Platform 的挂载仍引用其中原文件 inode。在将来明确重建这些容器前不可清理。回滚脚本只恢复源码和镜像，保留实时数据库；不要用旧数据库快照覆盖升级后新增事实。

Hermes 私有备份位于 `%LOCALAPPDATA%/hermes/backups/attention-deployment-20260915T062121Z`。应成对回退 connector/runtime，正常停止 Gateway，保留升级后产生的有效协作事实。

最后核验：三个生产容器均运行且重启计数为 0，SQLite 完整性为 `ok`、外键违规为 0。

本机详细证据位于忽略目录 `build/attention-deployment/`：`manifest.json`、`candidate-progress-v5-final.json`、`deploy-result.json`、`attention-baseline.json`、`final-attention-audit.json`、`local-install.json`、`local-deployment-record.md`、`local-pending-probe-latest.json`。真实浏览器记录为 `build/collaboration-design/production-attention-result.md`。其中不公开私人密钥或业务正文。
