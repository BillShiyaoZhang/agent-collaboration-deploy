# 架构与产品边界

- [当前架构](OVERVIEW.md)：组件职责、协作能力、扩展接口、远程协议和账户同步。
- [双边协作与用户提醒](COLLABORATION_AND_ATTENTION.md)：协议、授权边界、恢复和提醒流程。
- [流程图](FLOWS.md)：配对、读取、授权、投递和恢复。
- [产品决策](DECISIONS.md)：从早期探索中保留的身份、授权、记忆和持久状态原则。

[可验证的隐私与合规解密 v2](COMPLIANCE_GATEWAY.md)：初版源码、信任边界、本地验收与尚未实现的加强项；服务端代码已部署，现网签名策略尚未启用，公开安装包仍为 r2。

未实现的扩展约束见[后续方向](../developers/FUTURE_DIRECTIONS.md)。

实现和命令的归属见 [runtime](../../agent-comm-platform/agent-comm/python/README.md)、[Hermes connector](../../agent-comm-platform/agent-comm/connectors/hermes-platform/README.md) 及 [Web 客户端契约](../../agent-collaboration-web/packages/client-contract/README.md)。
