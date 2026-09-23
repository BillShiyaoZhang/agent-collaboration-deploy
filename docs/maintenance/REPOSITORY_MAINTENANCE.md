# 仓库与文档维护

这套系统的源码分在多个仓库。本部署仓库固定子模块提交，负责组合运行、跨组件测试和发布证据。修改前先从[开发者指南](../developers/README.md)定位所有者；多个任务并行时参考[worktree 整合流程](PARALLEL_WORKTREES.md)。

## 代码归属

| 仓库 | 维护内容 |
| --- | --- |
| `agent-collaboration-deploy` | Compose、nginx/Platform 部署配置、组合安装包、跨组件文档与验收 |
| `agent-collaboration-web` | Web 工作台、账户副本与同步、官网、共享客户端契约 |
| `agent-comm-platform` | Registry、MQ、Relay 和服务端 API |
| `agent-comm` | SDK/helper、Python runtime 和宿主连接器 |

`agent-comm-ios` 是独立外部仓库，不在本部署仓库的子模块中。组件改动应先在所属仓库验证，再由内到外固定 `agent-comm` → Platform → Web（可并行于前两者）→ 部署仓库的提交。父仓库只记录子模块提交；发布前确认引用的提交可从目标远端取得。具体组合部署与备份操作见[部署指南](../operations/DEPLOYMENT.md)。

## 文档分别为谁服务

- [用户指南](../users/README.md)回答如何连接、使用、理解状态和撤销权限，不要求读者理解源码或手工配对。
- [使用项目的 Agent 指南](../agents/README.md)负责任务路由；公开安装页和 SDK skill 是 agent 实际执行时的操作入口。
- [开发者指南](../developers/README.md)与根[AGENTS.md](../../AGENTS.md)解释代码归属、测试和开发用 coding agent 的约定。组件专属细节写在组件仓库。
- `architecture/`、`operations/`、`testing/` 保存可复用的实现与操作；`releases/`、`verification/` 和带日期测试报告保存历史证据。阶段提案完成后，将现行能力写入架构，尚未实现的约束写入[后续方向](../developers/FUTURE_DIRECTIONS.md)，移除会误导读者的旧提案。

行为或入口变化时，先更新对应读者会打开的主指南，再检查官网页面、安装包说明、Web 站内引导、SDK skill 和相关深层文档是否仍一致。不要把源码、GitHub Release、官网安装包与生产站点视为同一次自动发布；实际版本需核对发布记录及下载清单。

## 本地核对

从部署仓库根目录运行：

```sh
python tools/maintenance/check_structure.py
python -m unittest discover -s tools/release/early_access/tests -v
python -m unittest discover -s tools/release/tests -v
docker compose config --quiet
```

第一项离线检查四仓 Markdown 相对链接和指向这四仓默认分支的 GitHub 文件链接。其余命令按改动范围选择；Compose 验证需提供配置要求的环境变量。Web、Platform、SDK 内部测试与跨组件测试入口分别见各仓库文档和[本仓测试说明](../../tests/README.md)。

测试数据及生成物放在忽略目录，避免提交二进制、数据库、密钥、日志或用户身份文件。升级需保留原 helper 密钥、mailbox、connector receipts、协作状态和远程配对数据库；不能把重新初始化身份当成修复。
