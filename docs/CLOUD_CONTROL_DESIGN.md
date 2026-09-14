# Web 远程控制协议

更新：2026-09-14。旧版浏览器跨源向 helper 写入 self 联系人、以云端联系人授信，以及默认 Double Ratchet 的设计已移除。

当前实现使用 `agent-comm-control/v1` 签名加密请求，经 Registry/MQ 到达 agent 侧。控制台 URN 必须先通过本地 CLI 配对，并受方法范围、期限和撤销控制。Web 只保存账户、控制台凭据、连接记录与有限期 RPC 密文缓存；联系人、任务、审批、收件和会话结果从 agent 查询。

参见 [产品边界与扩展接口](ARCHITECTURE_AND_EXTENSION_PORTS.md)、[架构图](PROJECT_ARCHITECTURE_DIAGRAMS.md) 及 [runtime 接口与示例](../agent-comm-platform/agent-comm/python/README.md)。当前远程审批不开放，原生问题卡仍是 Hermes 协作授权入口。
