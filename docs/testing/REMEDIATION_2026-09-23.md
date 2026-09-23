# 2026-09-23 测试问题复核与修复记录

本记录接续[原始功能测试报告](TEST_REPORT_2026-09-23.md)。原报告保留当时的失败和警告，不把后续源码修复倒填为那一轮测试通过。本文件先记录修复时的本地验证；最终部署与重测结果见[2026-09-23 发布记录](../releases/TESTING_REMEDIATION_RELEASE_2026-09-23.md)。

| 问题 | 复核结论 | 本地修复与验证 |
| --- | --- | --- |
| D-01 自动首装拒绝 Web claim | 服务端时钟比本机约快 1 秒，严格的本机 `1800` 秒上界拒绝正常的 30 分钟票据；不是 Codex 中断造成 | 客户端只对上界容忍 10 秒时钟偏差，仍拒绝过期和异常长票据；接入相关测试 38/38 通过。修复版开发候选包在独立干净环境完成 Web 确认、自动配对、Gateway、真实回显和同身份重跑 |
| D-02 云端轮询 HTTP 500 / SQLite 锁 | 原请求确实返回过 500，日志同期有 `database is locked` 和超时；单条旧日志不足以确认唯一争锁语句 | 去除 control、Push、工作台读路径的无效写，复用进程内 PrismaClient，对可证明安全的写入做有限重试；r2 Web 178 项测试、lint、build 通过，现网重叠负载 154 次请求全 2xx，但仍有 4 次底层写锁与约 10 秒尾延迟 |
| 错误系统接入包被 `--check-only` 接受 | 安装器之前只校验摘要及 wheel，不对照 helper 的 OS/CPU | 普通校验现在要求 manifest 平台与宿主一致；发布构建器仅在只读校验时显式使用 `--cross-platform-check`；真实 Windows/Linux ZIP 和发布构建器测试通过 |
| 远程控制网络测试重复联系人 URN | 测试数据复用了已确认 Console URN，触发产品的合法去重规则 | 三个审批分支改用独立合成 URN；完整 17 个检查点通过，原双边协作断言保留 |
| Web lint 与 nginx HTTP/2 警告 | 分别是 Hook 依赖写法和旧的 `listen ... http2` 语法 | Web lint 无警告；nginx 改为 `http2 on;`，隔离容器与现网 `nginx -t` 通过；现网新容器无该弃用警告 |

## D-01：中断时间与失败时间

本机 Codex 运行记录中，**确实有更早的中断**：2026-09-22 13:50:39、13:54:17、13:55:37、14:13:25、14:50:11 UTC 的轮次因模型容量结束。最后一次结束前，浏览器已经完成测试账户 A 的创建与登录。测试任务在 23:35:03 UTC 进入后续新轮，继续处理 helper 端口和全新 venv；自动首装于 23:37:26～23:37:40 UTC 报 `Invalid short-lived pairing deadline`，23:38:35～23:38:44 UTC 又在单独请求中复现。报错区间有连续的工具与运行记录，没有同类轮次中断。现有记录无法确认用户记得的是哪一次中断，也不能证明所有 UI/网络环节从未短断。

关键的因果证据是[独立期限观测](../../build/test-runs/20260922-213955-692a4d/T12/deadline-observation.json)：请求耗时 0.206 秒，收到的过期时间比本机请求结束时间晚 **1801.054 秒**，而原校验要求最多 1800 秒。中断只会让票据剩余时间**减少**，无法使这个上界超出。因此，即使此前发生过中断，也不是 D-01 的原因。[时间线复核](../../build/test-runs/20260922-213955-692a4d/D01-interruption-review.json)保留了原始文件与独立重现的时间戳。

[修正后的期限校验](../../tools/release/early_access/onboard_hermes.py)允许服务器时间最多领先本机 10 秒，同时继续检查绝对过期、时区和异常长票据。[回归测试](../../tools/release/early_access/tests/test_onboarding_lifecycle.py)覆盖 1801.054 秒、边界、已过期和过长输入；测试环境中的 Hermes 源码发现断言已隔离已有 editable 安装，38 项接入测试稳定通过。

修复后又从**全新 Python venv 和独立 Hermes profile** 做了一次真实首装。安装前两个 agent-comm 包不可导入且没有旧配对；将当前修复脚本放入原 Windows 完整包、重新计算包内 SHA256，得到**仅用于本地验证的开发候选包**，并非官网已发布版本。安装器校验通过后生成 claim；使用合成测试账户在 Web 核对同一 Agent URN、列出的 Web 方法与 1 天期限并确认。`onboard_hermes.py --status` 随后报告 `connected`、`gateway_connected=true`，Web 显示本机配对完成和已同步工作台。Web 发出的无工具纯文字消息得到真实 Hermes 回答 `D01 自动接入成功 20260923`；再次运行相同接入命令后 URN 和 Console 配对不变，刷新页面仍只有一个 `completed` 回合。脱敏的[首装与回显结果](../../build/test-runs/20260923-d01-fix/D01-live-result.json)同时从本机配对库和登录后的 Web workspace 核对这些状态。

本轮测试随后撤销唯一的临时 Console 配对、结束该隔离目录的 Gateway/helper/worker，移除复制的 `.env`、`auth.json`、模型配置及其备份和含 poll secret 的 onboarding 状态；[清理记录](../../build/test-runs/20260923-d01-fix/cleanup.json)显示剩余测试进程为 0。浏览器已退出合成账号并关闭标签页。合成 Web 连接与测试对话保留用于追溯，但本机授权已撤销。OS 开机自启和其它原生 OS 的首装仍不属于本次验证。

## D-02：降低 SQLite 写锁竞争

原报告的[服务器错误证据](../../build/test-runs/20260922-213955-692a4d/cloud-web-errors.json)能证明控制轮询附近确有 SQLite 锁/超时，但不能把那次 HTTP 500 唯一归因到某一个 SQL 语句。进一步代码检查发现：control 请求和邮箱轮询每次都清理缓存，Push worker 每 3 秒即使无投递也执行多条无效写，工作台状态读取也会执行 `INSERT OR IGNORE`；生产模式的 instrumentation 与 route 还可能各自创建 PrismaClient。这些路径共同增加单写者 SQLite 的竞争。

修复位于 Web 子模块的 `src/lib/control/control-service.ts`、`src/lib/notifications/push-store.ts`、`src/lib/workspace/workspace-store.ts`、`src/lib/shared/db.ts` 和 `src/instrumentation.ts`：清理改为每分钟后台检查、过期记录按需要删除；Push 空闲轮次先读候选；已有工作台状态不再做无效插入；同进程复用数据库客户端。投影事务只在 **P1008 发生于回调开始前** 时重试，避免重复执行业务写入。r2 又对四条可单独重试、幂等的工作台 SQL 加入有限 SQLite Code 5 重试，不对提交结果不明的事务盲目重试。已有[真实 SQLite 写锁测试](../../agent-collaboration-web/tests/unit/push.test.cjs)覆盖空闲 Push 不等待写锁，[工作台测试](../../agent-collaboration-web/tests/unit/workspace-store.test.cjs)覆盖已有状态无效写、事务启动重试和第二连接持锁时四条 SQL 的安全重试，[控制测试](../../agent-collaboration-web/tests/unit/control.test.cjs)覆盖轮询不再删缓存。r2 Web 单元测试 178/178、lint 无警告、生产 build 通过。

2026-09-23 的[现网只读诊断](../../build/test-runs/20260922-213955-692a4d/D02-20260923-readonly-diagnostic.json)在测试负载停止后未再发现锁/超时；这不能替代双账户活跃同步下的升级复测。原报告的 T08 仍保留当时的“部分通过”，本次上线结果另记，不覆盖历史结论。

另用本机隔离的**生产模式** Next 进程、独立 SQLite 与签名 Registry/MQ fixture 跑了[并发复测](../../agent-collaboration-web/build/d02-prod-smoke/result.json)：两个登录账户、三个 Agent、一个活跃 Push 订阅和一条已关闭投递同时存在；60/60 次 `collaboration.state` control RPC 完成、60/60 次工作台读取成功、15 次同步调度后各连接均为 ready。HTTP 错误为 0，日志中 `database is locked`、P1008、超时和后台重试均为 0。这个结果覆盖生产构建下的并发路径，但 fixture 不是真实阿里云 Platform，也不等于现网升级验收。

## 其余问题与发布边界

[安装器](../../tools/release/early_access/install.py)现在拒绝错误 OS/CPU 包；[发布构建器](../../tools/release/build_early_access.py)可跨平台执行只读完整性校验。原始完整 Linux ZIP 在 Windows 普通 `--check-only` 返回非零，显式跨平台校验返回成功；当前 Windows ZIP 普通校验成功。发布构建器测试 5/5 通过。

[网络测试](../../tests/integration/test_remote_control_network.py)对三个待审批联系人使用不同 URN，完整[17 项检查结果](../../build/integration/remote-control-network/bab62643-f0d0-435d-b71c-8a705b865584/result.json)通过。[nginx 配置](../../deploy/nginx/nginx.conf)使用新 HTTP/2 指令；部署安全测试 3/3 通过，隔离的 Nginx 1.30.4 容器配置检查和 ALPN `h2` 通过。[通知页面](../../agent-collaboration-web/src/app/dashboard/notifications/page.tsx)消除 Hook 依赖警告。

本记录的初始阶段只描述本地修复。随后已发布官网接入包 `2026-09-23-testing-remediation-r2` 并部署新 Web/nginx；正式公网 ZIP 的 T12 自动接入、真实回显和清理通过。与 T12 活跃同步重叠的双账户现网探针 154 次请求全部为 2xx，HTTP 5xx 与后台重试告警为 0，但底层仍记录 4 次 SQLite Code 5，两个轮询约 10 秒；旧 A/B 测试 Agent 未在线，故不能把该探针算作两个活跃 Agent 的完整闭环。细节、备份和回滚位置见[发布记录](../releases/TESTING_REMEDIATION_RELEASE_2026-09-23.md)。原测试流程已在[步骤说明](TEST_EXECUTION_GUIDE.md)同步更新 OS/CPU 校验规则。
