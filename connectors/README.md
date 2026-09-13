# 部署仓库的旧 connector 已退役

本目录不再维护或安装 Hermes/OpenClaw connector。原来的重复实现调用旧密码学 CLI 和云端 MQ，不能与当前协议配套使用。保留的 `cli/bin/cli.js`、旧 Python 安装/导入入口和 OpenClaw 包入口会明确失败并提示迁移，不再执行旧安装或收发逻辑。

唯一维护来源是本仓库固定的 SDK 子模块：[`agent-comm-platform/agent-comm/connectors/`](../agent-comm-platform/agent-comm/connectors)。不要把本目录当作安装源，也不要通过任一仓库的旧通用安装 CLI 配置 Hermes。

## Hermes 的正确安装入口

以 SDK 的 [Hermes 插件安装说明](../agent-comm-platform/agent-comm/connectors/hermes-platform/README.md) 和 [本机 helper 合同](../agent-comm-platform/agent-comm/docs/HERMES_INTEGRATION.md) 为准：

1. 在部署仓库根目录执行 `git submodule update --init --recursive`，确保平台和 SDK 都使用仓库固定的提交。根据 helper 合同构建并启动该 SDK 的 helper，沿用原密钥目录、`mailbox.db` 和 WAL 文件。云端 HTTPS 地址传给 `agent-comm-helper daemon`。
2. 使用运行 Hermes Gateway 的同一个 Python 3.11+ 环境，从部署仓库根目录安装新版包：

   ```sh
   python -m pip install --upgrade ./agent-comm-platform/agent-comm/connectors/hermes-platform
   python -c "from hermes_constants import get_hermes_home; print(get_hermes_home())"
   ```

   如果 Gateway 使用专用虚拟环境，请将 `python` 换成它的解释器绝对路径。后一个命令用于确认实际 `HERMES_HOME`；不要假定它是 `~/.hermes`。按 SDK 说明选用 pip entry point 或用户目录插件，避免同时加载旧副本和新插件。
3. 按 SDK README 合并配置：启用 `plugins.enabled` 中的 `agent_comm`；将 `platforms.agent_comm.extra.platform_url` 设为本机 `http://127.0.0.1:45042`；使用 helper `/info` 返回的原 URN，并配置明确的 `allow_from`。**Hermes 插件不可填写云端平台 URL。** 保留现有 receipts 数据库；每个 helper inbox 仅运行一个活跃消费插件。
4. 按实际服务管理方式重启 Gateway，确认真实 SSE 连接为 connected，再进行 SDK README 中的验证。消息需处理成功并持久记录 receipt 后才 ACK，不能用旧插件的即时 ACK 或旧信封参数替代。

已经通过旧目录安装过插件的环境需要重新安装新版包；仓库更新不会自动替换其他 Python 环境中已复制的文件。用户目录下的同名旧插件也应按实际 profile 路径停用，保留身份与 receipts 数据。

## OpenClaw

根目录的重复 OpenClaw 实现和旧协议测试也已移除。其维护来源为 [SDK OpenClaw 目录](../agent-comm-platform/agent-comm/connectors/openclaw-channel)。本次 Hermes 迁移不提供自动 OpenClaw 安装；不要用已退役的根 CLI 写入旧的云端 MQ 配置。

## 验证退役入口

```sh
node --test connectors/cli/test/*.test.js
python -m unittest discover -s connectors/hermes-platform/tests -v
```

这些测试使用临时目录，检查旧入口失败且不修改配置、密钥、依赖或消息状态，不调用真实 helper、网络或 Gateway。
