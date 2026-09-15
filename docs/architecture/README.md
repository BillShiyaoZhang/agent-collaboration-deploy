# 架构与产品边界

- [当前架构](OVERVIEW.md)：组件职责、协作能力、扩展接口、远程协议和账户同步。
- [双边协作与用户提醒首版](COLLABORATION_AND_ATTENTION.md)：M1/N1 已实现能力、授权边界、恢复和 3 张 Mermaid 图。
- [流程图](FLOWS.md)：配对、读取、授权、投递和恢复。
- [技术实现详解](TECHNICAL_IMPLEMENTATION_WALKTHROUGH.md)：13 张 Mermaid 图，解释调用链、状态机、数据模型和扩展接口。
- [产品决策](DECISIONS.md)：从早期探索中保留的身份、授权、记忆和持久状态原则。

整体与后续设计见 [人—Agent—Agent—人的协作与授权设计 v1](../planning/HUMAN_AGENT_COLLABORATION_V1.md)（M1/N1 已实现，包含 11 张 Mermaid 图及后续阶段）。

实现和命令的归属见 [runtime](../../agent-comm-platform/agent-comm/python/README.md)、[Hermes connector](../../agent-comm-platform/agent-comm/connectors/hermes-platform/README.md) 及 [Web 客户端契约](../../agent-collaboration-web/packages/client-contract/README.md)。
