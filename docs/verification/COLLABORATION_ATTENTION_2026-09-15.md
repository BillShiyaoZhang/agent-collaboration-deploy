# 双边协作与用户提醒首版验证

日期：2026-09-15。对象为本地修改后的源码：runtime 0.1.1、Hermes connector 1.4.0 与配套 Web。未更新线上服务、公共下载包或现用 Hermes 配置，未向真实对端发送消息、调用私人模型或发送真实系统提醒。

以上为上线前验证范围。后续服务器与现用 Hermes 的部署结果见[通知与协作部署验证](ATTENTION_DEPLOYMENT_2026-09-15.md)。

## 已通过的验证

| 检查 | 结果与范围 |
| --- | --- |
| Runtime Python | 108 项通过；含 27 项 v2 协议测试，另覆盖 attention 持久性、状态版本、跨 owner 隔离、撤权后的取消提醒、崩溃待办和旧 v1 回归 |
| Hermes Python | 123 项通过；包括实际 Hermes 认证/profile 解析器与临时 Store 的隔离集成、原生确认恢复 |
| Hermes Desktop | 11 项行为测试通过；使用 fake host，验证纯提醒、多窗口 claim、分页中断、已读/待处理分离及 profile 切换 |
| Web | 124 项完整测试通过；包括通知账户隔离、静态加密、最新状态分页、源状态终结、稳定事项 ID、独立恢复项、原生呈现租约语义和只读同步游标 |
| Web 静态检查与构建 | TypeScript、lint、Prisma schema 校验通过；最终 production build 成功，随后在该构建上重跑浏览器验收 |
| 本地真实网络 | 真实 Go Platform + 两个 helper + Python runtime；双方不同本地 task_id 完成同版约定，attention 与协作状态经认证加密 RPC 读取 |
| Web 浏览器 | 真实 Edge、签名加密环回 fixture，8 项通过；全局入口、跨标签已读、待处理保留、通知 claim 去重、同源限制、v2 展示、390px 布局和源端解决后的收敛 |
| 包与安装 | 两个 wheel 构建成功，31 个包内源码条目比对通过；companion 从 wheel 导出通过；13 项隔离安装测试、5 项发布工具测试通过 |
| Mermaid | 实现说明的 3 张图解析、渲染通过 |

系统通知 API 在浏览器和前端测试中使用测试桩。结果支持通知逻辑与持久待办的正确性，不证明每种操作系统、通知偏好和后台状态下都会弹窗。Hermes 宿主集成使用真实公开源码接口及临时 profile，未在现用桌面中安装并点击 companion。

## 关键验收事实

- 旧 v1 仍可运行，v1/v2 业务操作共用任务预算；两个独立主人不能用同一份本地委托代替双方确认。
- 对端伪造 owner、替另一方接受、注入第三方接受证据、复用旧版本或事件 ID 均不能获得本方权限。
- 连续事件有缺口时等待/补取；每个 reducer 使用保存点，失败不会遗留部分业务副作用。
- 约定需有同版接受证据，成约顺序、撤回、取消与 ACK/回执分别处理；helper 的 accepted 不当作对方同意。
- v2 缺少可选外层 task_id 时，仍按已验证 packet 的 collaboration_id 和本机 owner 绑定进行收件及提醒路由。
- 旧原生问题卡的短呈现期限过期后，仍可在当前同主体原生会话重新呈现；通知阅读不授予权限。
- 授权撤销后旧业务方案失效，但对已存在约定的取消请求保持可处理；新的 900 秒一次性原生许可仅允许指定恢复事件。
- 完成后撤销维护许可不会重复产生完成提醒；同一任务的不同恢复待办不会互相覆盖。
- 未确定的硬崩溃发送保留原事实与恢复待办，不自动假定发送成功。

## 可重复入口与本机证据

- [Runtime 测试](../../agent-comm-platform/agent-comm/python/tests/)
- [Hermes 测试](../../agent-comm-platform/agent-comm/connectors/hermes-platform/tests/)
- [真实网络脚本](../../tests/integration/test_remote_control_network.py)
- [Web 浏览器脚本](../../agent-collaboration-web/tests/integration/notifications-browser.cjs)
- 本机日志：`build/collaboration-design/runtime-tests.log`、`installer-tests.log`。
- 真实网络结果：`build/integration/remote-control-network/c01a6b72-6009-40a3-b116-b176e3ecea70/result.json`。
- 浏览器截图与报告：`agent-collaboration-web/build/notifications-preview/`。
- Runtime wheel：`build/collaboration-design/dist/agent_comm_runtime-0.1.1-py3-none-any.whl`。
- Connector wheel：`agent-comm-platform/agent-comm/connectors/hermes-platform/build/attention-wheel/hermes_platform_agent_comm-1.4.0-py3-none-any.whl`。

证据目录按仓库约定忽略，不是发布目录。启用条件和实现边界见[首版说明](../architecture/COLLABORATION_AND_ATTENTION.md)。后台自动协商、日历执行、Web 远程批准、闭页 Web Push、自动续权及平台声誉仍属后续阶段。
