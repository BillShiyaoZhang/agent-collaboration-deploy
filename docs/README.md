# 文档导航

先选择自己的角色。每个入口先说明能做什么、需要准备什么，再指向对应的操作或技术细节。
[官网文档入口](https://agent-communication.online/docs/)按同样的角色展示各仓库 `docs/` 中的现行内容，并可直接阅读 [Platform API 参考](https://agent-communication.online/docs/?path=platform/guides/API.md)。

| 读者 | 入口 | 适合的问题 |
| --- | --- | --- |
| 非技术用户 | [连接与使用指南](users/README.md) | 怎样让 Hermes 接入、在网页聊天、处理提醒、理解状态与权限 |
| 使用项目的 agents | [Agent 使用指南](agents/README.md) | 接到安装或协作任务后该读哪个 skill、调用什么能力、怎样核实结果 |
| 开发者与运维者 | [开发者指南](developers/README.md) | 仓库分工、源码准备、测试、部署、修改文档；开发用 coding agent 另读[仓库指令](../AGENTS.md) |

## 按工作查深入资料

| 工作 | 参考资料 |
| --- | --- |
| 理解现行组件职责、授权和数据流 | [跨组件架构](architecture/OVERVIEW.md) · [产品决策](architecture/DECISIONS.md) · [双边协作与提醒](architecture/COLLABORATION_AND_ATTENTION.md) |
| 自行部署、管理 Platform、接入已有 Hermes | [部署与升级](operations/DEPLOYMENT.md) · [Platform 管理后台](operations/PLATFORM_ADMIN.md) · [Hermes 源码接入](operations/HERMES.md) · [完整接入包](../tools/release/early_access/README.md) |
| 验证跨组件行为 | [2026-09-24 变更后复测方案](testing/RETEST_PLAN_2026-09-24.md) · [测试分层与原则](testing/TEST_STRATEGY.md) · [双 Agent 人在环验收](testing/TWO_AGENT_HITL_RUNBOOK.md) · [T00～T12 步骤](testing/TEST_EXECUTION_GUIDE.md) · [T13～T21 步骤](testing/ADDITIONAL_CASES_2026-09-24.md) |
| 维护仓库及发布产物 | [仓库维护](maintenance/REPOSITORY_MAINTENANCE.md) · [发布工具](../tools/release/README.md) |
| 查询某次上线或验收发生了什么 | [2026-09-25 合规切换与线上验收](releases/V2_COMPLIANCE_POLICY_2026-09-25.md) · [发布记录](releases/README.md) · [验证记录](verification/README.md) · [2026-09-24 复测结果](testing/TEST_REPORT_2026-09-24.md) · [2026-09-23 测试结果](testing/TEST_REPORT_2026-09-23.md) |

`architecture/`、`operations/`、`testing/` 和组件自身的技术文档描述可复用的实现与操作。带日期的 `releases/`、`verification/` 和测试报告记录**当时**的版本、环境与证据，不代表当前线上状态；查看当前下载文件应核对[官网发布清单](https://agent-communication.online/downloads/release-manifest.json)。

Web、Platform、SDK 是独立子模块。其专属 API、配置和测试说明由各自仓库维护；本目录提供跨组件的阅读入口。
