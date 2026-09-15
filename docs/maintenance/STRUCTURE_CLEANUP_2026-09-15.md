# 项目结构与内容整理 · 2026-09-15

## 范围与结果

整理部署仓库及其固定的 Web、Platform、SDK 源码。现有仓库边界可支持当前维护与发布，
本次无需新增 GitHub 仓库。Apple 客户端是未纳入本部署工作区的外部仓库，本次没有修改其源码。
上传对象与顺序见[仓库维护](REPOSITORY_MAINTENANCE.md)。

| 范围 | 结构调整 | 内容清理 |
| --- | --- | --- |
| Deploy | 服务配置归 `deploy/`；文档分架构、运维、发布、验收、维护；工具分发布与维护，组合测试归 `tests/integration/` | 删除 5 份退役/重复交接设计，提炼有效决策；删除过时一次性 PDF 生成器 |
| Web | `src/lib/` 分 auth、protocol、control、workspace、shared；测试分 unit、integration、fixtures；文档分架构与运维 | 删除 7 个无引用 UI 组件、8 个无使用直接依赖；同步锁文件和全部导入 |
| Platform | 文档分 guides、architecture、maintenance，生产 Go 入口和 `internal/` 边界保持 | 删除旧网关设计、重复想法/问题和无签名接口的失效 Docker 测试 |
| SDK | 文档分 guides、architecture、planning、maintenance；cmd 归生产入口，示例与集成检查分开 | 删除误提交的约 33 MB bootstrap 二进制、一次性修补/提交脚本、过时网络实验及复制算法的调试程序 |

平台与 SDK 的逐项删除依据见各自 [Platform 记录](../../agent-comm-platform/docs/maintenance/REORGANIZATION.md)
和 [SDK 记录](../../agent-comm-platform/agent-comm/docs/maintenance/REORGANIZATION.md)。
旧内容可以从 Git 历史检索。

## 保留的维护资料和接口

- 七份已有发布/验收记录保留时点说明、原提交、镜像、校验值及回滚证据；历史路径不冒充当前路径。
- 公开 Go 包路径、helper/平台生产入口、Python 包路径和 SDK 根 SKILL 分发入口保持稳定。
- 数据库兼容迁移保留历史表及数据，源码整理没有触碰生产数据库、身份或配对。
- Compose 留在仓库根目录，服务名、端口和命名卷不变；仅配置文件挂载位置调整。
- 两个服务的 Docker 构建上下文排除 Git 元数据、本地依赖、缓存、私密环境配置及数据库生成物。

## 发布工具修正

- 发布内容读取干净 Git 提交的 blob，防止开发草稿或 Windows 换行混入源码包。
- 版本从 Python 项目 metadata 获取，清单记录源提交与文件 SHA256；保留 `.env.example`，排除私密配置和生成物。
- PDF 邀请函改为显式可选资产，移除过时固定文案、日期和本机字体依赖。
- Web 发布包使用完整源码快照，不再从未提交 diff 猜测服务器需要删除的文件。
- 新增离线结构/文档链接检查入口，避免后续目录变动留下失效导航。

## 本轮验证

| 检查 | 结果 |
| --- | --- |
| Web 现有自动测试 | 114 项通过，包含真实临时 SQLite、签名协议、账户隔离、同步与共享契约 |
| Web ESLint / 生产构建 | 通过，包含 TypeScript、页面生成及 standalone 输出 |
| Web 锁文件与导入 | 527 条 package 记录依赖闭合；保留包版本未升级，本地导入目标均存在 |
| 安装配置工具 | 13 项通过，使用临时 Hermes profile，安装过程由 mock 截获 |
| 发布工具 | 5 项通过，包含三平台 ZIP 校验、动态版本、无 PDF 构建、完整快照和可复现输出 |
| SDK Python 与 Hermes 协作回归 | runtime 40、policy 32、store 13、adversarial 31，共 116 项通过 |
| SDK Release 文档包 | 按更新后的工作流实际打包 27 份文档成功 |
| SDK / Platform Go | 两仓 `go test ./...` 全部通过，包含迁移后的 7 个示例和 2 个平台检查程序编译 |
| 文档与启动脚本 | 69 份 Markdown 链接检查通过；`bash -n run.sh` 通过 |
| Docker Compose | `docker compose config --quiet` 通过；迁移后的两份配置内容与原文件一致 |
| 真实本地 Web 组合测试 | 登录、控制台身份、Node/Go/Python 加密往返、联系人、持久化与撤销通过 |
| 真实本地远程控制组合测试 | 权限、关联验证、持久化失败重试、重启、撤销与本机数据隔离等 12 项通过 |

两个组合测试使用已有本机 helper/platform 测试二进制，配合本次重构后的 Web 和 Python 源码。
它们只创建临时身份、账户和数据库，不调用模型或向生产用户发送消息。
Web 首次通过依赖目录 junction 构建时遇到 Windows standalone 跟踪权限问题；
改用工作区实际依赖并清理过期构建缓存后，完整生产构建通过。
Go 使用校验下载的项目要求版本 1.25.7，最终测试显式设置 `TEST_REAL_PLATFORM=false`；
工具链和模块缓存全部位于工作区 `build/`，没有启用针对生产平台的可选测试。

运行命令见[仓库维护](REPOSITORY_MAINTENANCE.md)、[根测试说明](../../tests/README.md)
和[工具说明](../../tools/README.md)。本地验证不代表线上服务已更新。
