# 跨仓库验证

本目录放需要组合 SDK/helper 与 Platform 的检查；组件自身的单元测试留在组件仓库。

- [远程控制链路](integration/test_remote_control_network.py)：真实本地 Registry/MQ/helper 与 Python runtime，
  用 `python tests/integration/test_remote_control_network.py --help` 查看二进制参数。
- Web 的完整登录、配对与同步验证位于 [Web 集成测试](../agent-collaboration-web/tests/README.md)。
- 安装包的隔离单元测试位于 `tools/release/early_access/tests/`。

先递归初始化子模块。网络检查使用临时身份和本地进程，结果存于忽略的 `build/`。
具体通过范围记录在 [verification](../docs/verification/README.md)，不能将纯本地检查当成线上验收。
