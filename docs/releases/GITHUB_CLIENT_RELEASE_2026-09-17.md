# agent-comm v0.7.0 正式客户端发布 · 2026-09-17

2026-09-17 22:34（北京时间）发布 [GitHub Release v0.7.0](https://github.com/BillShiyaoZhang/agent-comm/releases/tag/v0.7.0)，随后通过阿里云 Workbench CLI 将同一批安装包同步到[官网](https://agent-communication.online/#start)。[GitHub Actions](https://github.com/BillShiyaoZhang/agent-comm/actions/runs/35233993168) 全部通过。

本次正式分发此前已完成的 [Agent / Web 能力一致性改动](AGENT_WEB_PARITY_RELEASE_2026-09-17.md)，更新客户端版本和发布工具，新增 Intel Mac 安装包。服务器应用继续运行上一条发布记录中的已验证 Web / Platform 镜像。

## 版本与产物

| 仓库 | 安装包与源码 ZIP 的固定提交 |
| --- | --- |
| Deploy | `8d71f186d71a0e5db355e53100b941325a537eb8` |
| Web | `44e8be5beea6f87755e0c1f08397c5f0ee828684` |
| Platform | `2ed906d28f27d76cbdcf463b4031d364aae63486` |
| SDK / `v0.7.0` | `ecf829dc31099ea889abf2633cbe47afd522eab5` |

runtime 为 **0.1.4**，Hermes connector 为 **1.5.5**，后者要求 runtime `>=0.1.4,<0.2`。版本标签是新建的固定标签，未移动旧标签或覆盖旧 Release。

GitHub 提供 16 项资产：4 个 helper、2 个 Python wheel、4 个完整安装 ZIP、1 个源码 ZIP、文档 ZIP、下载脚本、两份 manifest 和 `SHA256SUMS`。目标为 Windows amd64、Linux amd64、macOS Intel amd64、macOS Apple Silicon arm64。完整接入包包含对应 helper、两个 wheel、安装与配置脚本及说明；Hermes 需要预先安装。

官网提供相同的 4 个安装 ZIP 和源码 ZIP，其 `downloads/release-manifest.json` 与 GitHub 的 `early-access-manifest.json` 逐字节相同，SHA-256 为 `9ea6ee1dadd6dfb5c22cb1c6ef236d7dd20cc634f37898273432ba2f9483b680`。GitHub 的 `release-manifest.json` 是 SDK 下载器的资产清单，不能直接替代官网清单。此次未向 PyPI 发布包。

## 验证

- CI 通过全部 Go 测试、runtime 154 项、无宿主依赖 connector 84 项、桌面与恢复 55 项、发布/下载器 19 项、部署打包 5 项及安装配置 16 项测试。
- 四平台 helper 使用 Go 1.26.8 交叉编译，构建身份包含正确的 SDK 提交、目标系统和架构，`CGO_ENABLED=0`、`vcs.modified=false`。交叉编译和静态校验不等于四种操作系统上的真实 Hermes 验收；先前的宿主验收范围见能力一致性记录。
- 独立下载 GitHub 的全部 16 项资产，核对 GitHub API digest、长度、SDK 清单及 `SHA256SUMS`；核对四个接入 ZIP 的内部清单、CRC、helper 与独立 wheel 字节，以及源码 ZIP 的四仓提交，全部通过。
- 服务端切换前保存旧下载包、静态首页、四仓提交和容器基线。文件逐个原子替换，清单最后更新；服务器源码按已校验 Git bundle 快进到上表提交。容器 ID、镜像、启动时间、重启数、挂载与历史邀请 PDF 保持不变。
- 公网验收通过：官网四个平台下载入口均可见，首页、登录页和健康接口返回 200；6 个匿名私有 API 返回 401 和 `no-store`。官网清单与 GitHub 对应清单逐字节一致，5 个 ZIP 经完整流式下载验证长度和 SHA-256，均与 GitHub 一致。TLS 证书和主机名正常校验，全程仅匿名 GET，未创建生产测试账户或发送业务消息。

## 升级与回滚

已有用户按[升级步骤](../../tools/release/early_access/README.md#已有客户端升级)更新本机 helper、runtime 和 connector，保留原身份与数据目录。需要 Web 新增操作权限时，使用原控制台 URN 加 `--allow-web-actions` 重新配对；服务器发布不会替本机升级，也不会自动扩大旧配对的权限。

服务器公开发行暂存与操作记录在 `/root/agent-comm-releases/agent-comm-v0.7.0`，备份在 `/root/agent-comm-backups/agent-comm-v0.7.0`，备份目录权限为 `0700`。本地完整校验记录位于忽略目录 `build/releases/agent-comm-v0.7.0/`。如需撤回官网分发，按备份的 `baseline.json` 恢复原下载文件和静态入口，最后恢复下载清单；保持运行镜像、实时数据库、身份与环境配置不变。GitHub 已发布版本保留，不覆盖或删除既有发布资产。

后续只修改本文等文档的提交不改变上述产物或运行镜像。
