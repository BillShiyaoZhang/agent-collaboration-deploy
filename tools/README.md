# 维护工具

工具按维护职责组织；构建产物、测试身份和日志写入被 Git 忽略的目录。

| 目录 / 入口 | 用途 |
| --- | --- |
| [release/](release/README.md) | 构建 Web 发布快照、接入 ZIP 和开发源码 ZIP |
| [release/early_access/](release/early_access/README.md) | 随安装包分发的安装与 Hermes 配置脚本 |
| `maintenance/check_structure.py` | 离线检查四仓边界和 Markdown 文件链接 |
| [../tests/integration/test_remote_control_network.py](../tests/integration/test_remote_control_network.py) | 真实本地 Go platform/helper 与 Python remote 的跨组件回归 |

## 本地验证

从仓库根目录执行，使用 Python 3.11+。接入脚本测试需要已递归初始化的 SDK 和 PyYAML；测试使用临时 Hermes profile，安装操作由 mock 截获。

```sh
python tools/maintenance/check_structure.py
python -m unittest discover -s tools/release/early_access/tests -v
python -m unittest discover -s tools/release/tests -v
```

网络回归还需要预先编译本机版本的 helper 与 platform，可通过两个参数指定任意构建位置：

```sh
python tests/integration/test_remote_control_network.py --helper build/agent-comm-helper --platform build/agent-comm-platform
```

Windows 使用相应的 `.exe` 路径。测试创建全新的本地身份，只启动 loopback 服务，不调用模型；结果与进程日志位于 `build/integration/remote-control-network/<UUID>/`。SDK 自身的测试由 SDK 仓库维护。
