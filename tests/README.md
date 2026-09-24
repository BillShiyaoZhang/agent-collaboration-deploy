# 跨仓库验证

完整的环境分层、能力追踪、网页添加联系人用户旅程、Hermes 真实验收和发布门禁见[系统测试方案](../docs/testing/TEST_STRATEGY.md)；两个 Agent 与两边用户的逐步操作见[双 Agent 人在环 Runbook](../docs/testing/TWO_AGENT_HITL_RUNBOOK.md)；按编号执行的测试清单见[测试步骤说明](../docs/testing/TEST_EXECUTION_GUIDE.md)。

本目录放需要组合 SDK/helper 与 Platform 的检查；组件自身的单元测试留在组件仓库。

- [远程控制链路](integration/test_remote_control_network.py)：旧 v1 协议回归，使用旧版 helper 二进制、真实本地 Registry/MQ 与 Python runtime；新版 helper 的普通 v1 发送入口会按迁移规则拒绝。用 `python tests/integration/test_remote_control_network.py --help` 查看二进制参数。
- [v2 隐私与合规网关](integration/test_v2_gateway_network.py)：使用离线签名策略、真实本地 Platform 和双 helper，验证握手、两种加密、网关回执、私密兼容期的 v1 准入、切换后的旧队列隔离与升级提示、跨 epoch 原回执重试及 v1 失效门禁；需先构建 Platform、helper 和 `cmd/v2-policy` 三个二进制，用 `--help` 查看参数。
- [Agent / Web 能力一致性](integration/test_agent_web_parity_network.py)：旧 v1 协议回归，使用旧版 helper 二进制，验证自动注册、好友往返、双端消息、共享已读与好友在线状态；新版 helper 的 v2 路径由上述新验收覆盖。参数同上。
- Web 的完整登录、配对与同步验证位于 [Web 集成测试](../agent-collaboration-web/tests/README.md)。
- 安装包的隔离单元测试位于 `tools/release/early_access/tests/`。
- [部署安全入口检查](integration/test_deployment_security.py)：运行 `python tests/integration/test_deployment_security.py`，用 Docker 隔离容器验证缺少密钥时启动失败、nginx 实际认证限流、请求体限制和代理头覆盖；可用 `NGINX_TEST_IMAGE` 指定已有 nginx 镜像，设置 `WEB_TEST_IMAGE` 为本地构建的 Web 镜像后额外验证迁移/服务降权及旧卷文件保留。

先递归初始化子模块。网络检查使用临时身份和本地进程，结果存于忽略的 `build/`。
具体通过范围记录在 [verification](../docs/verification/README.md)，不能将纯本地检查当成线上验收。
