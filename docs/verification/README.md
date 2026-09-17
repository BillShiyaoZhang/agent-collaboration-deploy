# 验证入口与记录

## 已完成的历史验收

- [2026-09-18 Hermes 仅凭官网地址自动接入](HERMES_AUTONOMOUS_ONBOARDING_2026-09-18.md)：干净 Hermes、MiniMax China、官网安装入口、网页确认和本机自动配对；真实模型回复与完整验收结论以该报告为准。
- [2026-09-17 Agent / Web 能力一致性](AGENT_WEB_PARITY_2026-09-17.md)：好友握手、双端消息与已读、在线状态、绑定注册及配对聊天工具的本地修复和验收。
- [2026-09-16 安全检查与修复](SECURITY_REVIEW_2026-09-16.md)：部署、Web、Platform 与 SDK 的代码审查、依赖漏洞、回归测试及上线边界。

- [2026-09-15 通知与协作部署](ATTENTION_DEPLOYMENT_2026-09-15.md)：线上 Web、本机 Hermes、真实待办同步、数据保留与回滚；含系统弹窗和 GitHub 推送的验证边界。
- [2026-09-15 双边协作与用户提醒](COLLABORATION_ATTENTION_2026-09-15.md)：M1/N1 上线前源码、两个真实 helper 的协作闭环、持久提醒、Hermes 认证与 Web 浏览器验证。

- [2026-09-15 Hermes 系统协作](HERMES_COOPERATION_TEST_2026-09-15.md)：真实回复、上下文、重试、权限、后台保存、本机更新和 Web 上线。
- [发布索引](../releases/README.md)：各次发布的候选环境、浏览器、迁移及数据保留检查。

历史结果只支持记录中的版本和场景。模型文字、协议状态、后台同步和外部副作用应分别核对；合成响应或本地模拟不等于真实宿主/模型验收。

## 可复用源码入口

| 入口 | 覆盖范围 |
| --- | --- |
| [Hermes 接入生命周期测试](../../tools/release/early_access/tests/test_onboarding_lifecycle.py) · [签名授权测试](../../tools/release/early_access/tests/test_onboarding_grant.py) | 实际 Python/profile、后台生命周期、签名配对、权限与撤销恢复 |
| [Web 自动接入测试](../../agent-collaboration-web/tests/unit/onboarding.test.cjs) | 真实 SQLite、agent 身份证明、登录确认、轮询 secret、固定授权与回执 |
| [跨组件 remote 网络测试](../../tests/integration/test_remote_control_network.py) | 本地真实 helper/Platform 与 Python RPC、恢复、方法权限和撤销 |
| [SDK helper/Platform 测试](../../agent-comm-platform/agent-comm/tools/test_helper_platform.py) | 认证收发、离线队列、ACK、稳定 ID 和重启恢复 |
| [Web full-stack smoke](../../agent-collaboration-web/tests/integration/full_stack_smoke.py) | 真实本地 Go/Python/Web 注册、登录、控制身份和加密 RPC |
| [Web 同步 fixture](../../agent-collaboration-web/tests/integration/workspace-fixture.cjs) | 签名加密 fixture、账户隔离和页面打开前同步 |
| [Web 同步浏览器验证](../../agent-collaboration-web/tests/integration/workspace-browser.cjs) | 保存视图、页面恢复、会话及不同宽度布局 |
| [Web 同步恢复验证](../../agent-collaboration-web/tests/integration/workspace-resilience.cjs) | 离线保存、进程重启、重连和避免重放发送 |

运行参数和依赖以脚本帮助、[测试说明](../../tests/README.md)、[SDK README](../../agent-comm-platform/agent-comm/README.md) 与 [Web 技术参考](../../agent-collaboration-web/docs/architecture/TECHNICAL_REFERENCE.md) 为准。使用独立临时身份与数据目录；生成证据保存在忽略的 `build/` 中。
