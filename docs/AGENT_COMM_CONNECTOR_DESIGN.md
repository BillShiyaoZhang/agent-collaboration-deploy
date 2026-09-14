# Agent Comm 适配与安装来源

更新：2026-09-14。通用协作内核位于 SDK 的 `python/agent_comm_runtime/`；Hermes 插件位于 SDK 的 `connectors/hermes-platform/`。根部署仓库的旧 connector、安装 CLI 与旧联调脚本已移除。

```mermaid
flowchart LR
    H["用户宿主"] <--> C["宿主 / 记忆 / 交互适配器"]
    C <--> R["通用 runtime + 本地状态"]
    R <--> HP["本机 Go helper"]
    HP <-->|"HTTPS"| P["Registry / MQ"]
```

从源码接入时，先安装 SDK 的 `python/`，再在同一宿主 Python 环境安装 `connectors/hermes-platform/`。helper 云端地址用于 daemon 参数；插件的 `platform_url` 只能是本机 loopback helper。

升级需保留密钥、mailbox、receipts、collaboration 和 remote 配对数据库。停用真实 profile 中同名的旧插件副本后，按正常方式重启 Gateway；一个 helper 只能有一个活跃的 connector/standalone 消费者。

当前 Hermes 插件提供实际宿主会话、原生确认与受配对约束的远程会话。其它宿主使用四类 [扩展接口](ARCHITECTURE_AND_EXTENSION_PORTS.md) 接入；现有 SDK OpenClaw 基础 connector 不因此自动具备新的个人协作能力。

参见 [runtime README](../agent-comm-platform/agent-comm/python/README.md) 与 [Hermes README](../agent-comm-platform/agent-comm/connectors/hermes-platform/README.md)。
