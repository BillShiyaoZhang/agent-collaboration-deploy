# 旧部署包已退役

请勿从此目录安装 Hermes 插件。这里仅保留明确失败的安装和导入入口，原收发实现已移除。

在运行 Hermes Gateway 的 Python 环境，从部署仓库根目录执行：

```sh
python -m pip install --upgrade ./agent-comm-platform/agent-comm/connectors/hermes-platform
```

按 [SDK Hermes README](../../agent-comm-platform/agent-comm/connectors/hermes-platform/README.md) 配置实际 `HERMES_HOME`，使用本机 helper 和 `platforms.agent_comm.extra.platform_url=http://127.0.0.1:45042`。云端 URL 只用于 helper daemon。保留已有密钥、mailbox 和 receipts 数据，停用同名旧插件副本。完整迁移步骤见 [上级说明](../README.md)。
