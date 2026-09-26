# 开发、测试和部署 Agent Comm

本指南是跨仓库开发入口。普通使用者从[用户指南](../users/README.md)开始；要让 agent 安装或使用已有能力，读[Agent 使用指南](../agents/README.md)。在本仓库工作的 coding agent 还应读根目录的[AGENTS.md](../../AGENTS.md)。

## 先定位要修改的仓库

| 改动内容 | 归属仓库 | 技术入口 |
| --- | --- | --- |
| Compose、nginx、组合安装包、跨组件测试和发布 | 本部署仓库 | [部署指南](../operations/DEPLOYMENT.md) · [发布工具](../../tools/release/README.md) · [测试入口](../../tests/README.md) |
| 网页、官网、账户副本与客户端契约 | `agent-collaboration-web/` | [Web 文档](../../agent-collaboration-web/docs/README.md) |
| Registry、消息队列、Relay 和服务端 API | `agent-comm-platform/` | [Platform 文档](../../agent-comm-platform/docs/README.md) |
| helper、SDK、Python runtime、Hermes/OpenClaw 连接器 | `agent-comm-platform/agent-comm/` | [SDK 文档](../../agent-comm-platform/agent-comm/docs/README.md) |

这三个组件是嵌套 Git 子模块，父仓库记录的是**固定提交**。组件代码或文档改动应在所属仓库完成并验证，发布时从内到外更新子模块引用；仅修改父仓库的文字不会更新线上组件或接入包。Apple 客户端在独立仓库，不在本次源码树中。

## 取得源码

```sh
git clone --recurse-submodules https://github.com/BillShiyaoZhang/agent-collaboration-deploy.git
cd agent-collaboration-deploy
```

已有检出缺少子模块时运行 `git submodule update --init --recursive`。不要用 `git submodule update --remote` 代替固定版本；它会选择另一组提交。目录边界和提交顺序见[仓库维护](../maintenance/REPOSITORY_MAINTENANCE.md)。

## 从哪一层验证

1. **文档与目录：** `python tools/maintenance/check_structure.py` 检查四仓 Markdown 文件链接及边界。
2. **安装包脚本：** `python -m unittest discover -s tools/release/early_access/tests -v`；构建与清单检查见[发布工具](../../tools/release/README.md)。
3. **跨组件行为：** 从[测试入口](../../tests/README.md)选择对应的集成检查；完整环境、双 Agent 验收和发布门禁见[测试方案](../testing/TEST_STRATEGY.md)。
4. **组件内部变更：** 按 Web、Platform 或 SDK 各自的测试说明运行测试。只有隔离测试通过不能声称真实 Hermes、浏览器或生产环境已通过。

本仓库的 Compose 组合 nginx、Web 和 Platform；Hermes、helper 在用户的 agent 设备运行。自行部署、升级、备份与证书操作见[部署指南](../operations/DEPLOYMENT.md)，从固定源码接入 Hermes 见[Hermes 运维指南](../operations/HERMES.md)。

## 查实现和历史

产品设计提案：[Web 聊天与 agent 协作设计](../design/WEB_CHAT_AND_COLLABORATION.md)从 Persona、storyboard 推导功能与状态；仅供设计评审，不是现行功能或发布承诺。

- [跨组件架构](../architecture/OVERVIEW.md)：谁持有身份、权限与数据；[产品决策](../architecture/DECISIONS.md)解释信任与授权边界。
- 单 Platform 的 URN 首联同时涉及 SDK helper 的 Registry 身份验证与未确认握手、Python runtime 的好友申请/接受和消息门禁，以及 Web 的状态文案；改动时一起核对[SDK v2 协议](../../agent-comm-platform/agent-comm/docs/architecture/PROTOCOL_V2.md)和[当前架构](../architecture/OVERVIEW.md)。通讯录连接、现实身份判断、通信信任、协作授权和合规披露是不同状态。
- [尚未实现的扩展方向](FUTURE_DIRECTIONS.md)：外部执行、代表权、关系事实与声誉的设计约束，不是现行功能承诺。
- [发布记录](../releases/README.md)、[验证记录](../verification/README.md)：只证明相应日期和环境的结果。部署前核对实际提交、镜像和[公开下载清单](https://agent-communication.online/downloads/release-manifest.json)。
- [文档维护规则](../maintenance/REPOSITORY_MAINTENANCE.md)：修复行为时同步更新该读者会查找的操作说明；不要把过时的阶段计划写成现行能力。
