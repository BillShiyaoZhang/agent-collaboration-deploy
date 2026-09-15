# 仓库边界与日常维护

多个任务同时工作时，按[并行 worktree 的整合与发布](PARALLEL_WORKTREES.md)交接、合并与固定子模块。

## 当前分工

已有四个本地仓库足以支持当前独立构建和发布，无需新增 GitHub 仓库。

| 仓库 | 维护内容 | 不同项目之间的约定 |
| --- | --- | --- |
| `agent-collaboration-deploy` | Compose、nginx/平台部署配置、跨仓架构、运维、发布工具、组合验收 | 固定 Web 和 Platform 的提交 |
| `agent-collaboration-web` | 工作台、账户副本与同步、静态官网、共享客户端契约 | 官网可单独同步；契约以 npm workspace 维护 |
| `agent-comm-platform` | Registry、MQ、relay、管理 API | Go 依赖由嵌套 SDK 子模块固定 |
| `agent-comm` | Go 通信 SDK/helper、Python runtime、Hermes/OpenClaw 适配器 | 保留公共 Go 包路径和安装入口 |

`agent-comm-ios` 是独立外部客户端，本部署仓库未引用其源码或固定提交，本次未改动。
后续出现独立团队、独立版本周期或多个仓库直接发布同一模块的需求时，
再评估拆出 `client-contract` 或独立连接器；目前拆分会增加同步和安装步骤。

## 目录约定

- 根 README 提供用途、结构与入口；现行说明放 `docs/architecture/`、`docs/operations/` 或组件的 `docs/guides/`。
- 发布记录放 `docs/releases/`，包含日期、提交、验证、回滚证据；验收报告放 `docs/verification/`。
- 规划文件只能描述尚未实现的方向，不能作为当前安装或能力说明。
- 测试数据和生成物放忽略的 `build/`、`downloads/`、`output/`；不提交编译二进制、数据库、密钥或依赖目录。
- 删除废弃代码时同步检查入口、导入、文档、打包脚本；有价值的决策提炼后保留，旧实现通过 Git 历史查阅。
- 不删除现有生产数据库中的历史表来实现“源码清理”。数据迁移继续遵循组件升级指南。

## 本次需要上传哪些仓库

四个现有仓库均有本地整理，按以下顺序发布提交。无需新建远程仓库，也不要把子模块目录
当作普通文件夹整体上传到部署仓库。

1. **agent-comm**：上传 SDK 的整理提交。
2. **agent-comm-platform**：将 `agent-comm` 固定到上一步提交，上传平台整理提交。
3. **agent-collaboration-web**：上传 Web 的整理提交；可与前两步并行。
4. **agent-collaboration-deploy**：固定 Platform 和 Web 到已上传提交，再上传部署整理提交。

本地提交和远程上传是两个步骤。不要先上传引用了远程尚不存在的子模块提交的父仓库。
本次不自动更新线上服务；服务升级按[部署指南](../operations/DEPLOYMENT.md)执行。

检查各层状态和固定版本：

```sh
git status --short
git submodule status --recursive
git submodule foreach --recursive 'git status --short'
```

本次四仓使用同名本地分支 `codex/structure-cleanup-20260915`。在部署根目录审阅后，
可按顺序执行以下上传命令；这些命令需要维护者自己的 GitHub 推送权限：

```sh
git -C agent-comm-platform/agent-comm push -u origin codex/structure-cleanup-20260915
git -C agent-comm-platform push -u origin codex/structure-cleanup-20260915
git -C agent-collaboration-web push -u origin codex/structure-cleanup-20260915
git push -u origin codex/structure-cleanup-20260915
```

本次仅完成本地提交，尚未执行上述上传命令。维护者在各仓库审核分支并合并；部署仓库需最后合并。
若通过 PR squash 或 rebase 改变了子提交 SHA，父仓库必须重新固定到实际合并提交。

## 验证入口

从部署根目录运行：

```sh
python tools/maintenance/check_structure.py
python -m unittest discover -s tools/release/early_access/tests -v
python -m unittest discover -s tools/release/tests -v
docker compose config --quiet
```

从 Web 根目录运行 `npm ci`、`npm run db:generate`、`npm test`、`npm run lint`、`npm run build`。
Go/Python 组件测试命令见各仓库的 docs 索引。组合网络测试见
[根测试说明](../../tests/README.md)，发布操作见[发布工具](../../tools/release/README.md)。

`check_structure.py` 离线检查四仓边界及 Markdown 文件链接，包括指向本组织四仓 main/master 的
GitHub 文件链接；固定历史提交的 URL、锚点和外部网站不在检查范围内。
