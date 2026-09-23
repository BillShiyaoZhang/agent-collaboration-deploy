# 给开发本仓库的 coding agents

先读[开发者指南](docs/developers/README.md)，再按改动范围查看对应组件文档。本文件是**开发仓库**的工作约定；替用户安装或使用 Agent Comm 时，按[使用项目的 Agent 指南](docs/agents/README.md)和实际安装 skill 操作。

## 仓库边界

- 根仓库维护 Compose、部署配置、跨组件文档、发布工具和集成测试。`agent-collaboration-web/`、`agent-comm-platform/` 是独立子模块；`agent-comm-platform/agent-comm/` 是嵌套子模块。改动归属仓库后检查各层状态及固定提交，不把子模块当普通目录覆盖。
- 不凭源码更新声称线上服务或公开安装包已更新。带日期的发布、验收记录是当次证据；现行步骤以操作指南和实际配置为准。
- 不提交密钥、用户身份目录、mailbox、数据库、日志或构建产物。升级和测试保留现有身份与状态；不要靠重新初始化身份来掩盖问题。

## 修改与验证

1. 先确认代码所有者和用户能触达的入口：根文档、Web、Platform、SDK、官网公开安装页和 SDK skill 可能在不同仓库。
2. 更改行为时同步更新受影响的用户、使用 agent、开发者文档及必要的安装包说明。用户首装以一次性网页授权链接为主；手工配对属于已有安装与管理员流程。
3. 运行与改动范围相符的检查。文档改动至少运行 `python tools/maintenance/check_structure.py`；发布脚本用 `python -m unittest discover -s tools/release/early_access/tests -v`。跨组件验证入口见[测试说明](tests/README.md)。
4. 报告实际验证环境及未覆盖范围。`submitted`、MQ ACK、完成的安装和业务完成是不同状态；只有真实结果才能写成已完成。

常用入口：[文档导航](docs/README.md) · [仓库维护](docs/maintenance/REPOSITORY_MAINTENANCE.md) · [部署](docs/operations/DEPLOYMENT.md)。
