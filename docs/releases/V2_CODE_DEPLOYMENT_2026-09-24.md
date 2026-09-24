# 2026-09-24 v2 协议代码上线（兼容阶段）

本次将 Agent Comm v2 的已签策略、隐私握手、合规信封与回执、旧 Agent 升级提示，以及 Web 的政策披露和用户确认代码推送到四个 GitHub 仓库的 `main`，并在阿里云 ECS `i-0jleb7de83gsnoa0yuc2` 部署 Platform、Web 与 nginx。四个 GitHub 仓库检查时均只有 `main` 分支。**生产尚未签发或启用 v2 策略**：现网仍按旧协议兼容运行，`/api/v2/policy` 返回 404；不能把这次上线写成合规网关已可解密生产流量。

| 对象 | 本次运行版本 |
| --- | --- |
| Deploy 应用固定提交 | `b1e7bc0827b82c4f14d7391ee190259811d2f286` |
| Web 子模块 | `16a41d5df06e1651a8beb300d2300c98b4d0d078` |
| Platform 子模块 | `42e4b9636695ac39674f538f00b849b3486afa94` |
| SDK 子模块 | `810157cbce5f0d7e87e07383de2afbcc2255dc44` |
| Platform 镜像 | `sha256:4a064b4a5f5e624ac7096d6897a4f87e6296e5274c902495c31ec5fc7606d98d` |
| Web 镜像 | `sha256:69d962c9b3336b92881e6de36a61534635c78867c562c615b1aeb94bdb4e7c03` |
| nginx 镜像 | `sha256:311761cac6bbc23041f3f4302699b0b5d0614e0a4d28b70def415e7bf16050c1` |

## 备份与切换

切换前对 Platform 三个 SQLite 数据库和 Web 数据库使用在线 `.backup`，保存数据卷非数据库文件、原 `.env`、Compose、配置与旧镜像标签；SHA-256 清单及四个备份库的 `PRAGMA quick_check` 通过。备份仅在服务器 root 可读的 `/root/agent-comm-backups/2026-09-24-v2-code-320bf04/`。最终切换 Web 前又备份实时数据库至 `/root/agent-comm-backups/2026-09-24-v2-web-fix-b1e7bc0/`。这两处备份均未进入仓库。

首次切换时，Platform 新镜像启动正常，但 Web 在非 root 运行迁移时无法读取由服务器严格 `umask 077` 检出的 `prisma/remote-console.sql`。立即恢复旧 Web 镜像，确认登录和健康接口可用。Web 随后将所有运行时 `COPY` 完成后的代码与 Prisma 文件规范为可读权限，保留数据库和缓存目录的独立写权限，提交修复后重建镜像。新镜像在服务器上以 UID 1001 读取迁移文件、CLI 和 Next 文件，并在隔离 SQLite 数据库成功执行实际 Prisma 迁移，再切换生产 Web。原始失败记录及修复后的结果保存在服务器 `/root/agent-comm-releases/v2-code-20260924-320bf04/`；没有删除或重建原有身份与数据库。

## 验证范围

- 本地：SDK Go 全量测试、Python runtime 156 项、Hermes store 13 项、OpenClaw 集成 5 项；Platform Go 测试；Web 197 项测试、TypeScript 和生产构建；双 Agent、真实 Platform 进程的 v2 验收 10 项；文档结构检查 114 个 Markdown、0 错误；Compose 配置与各仓库 diff 检查通过。本机 Docker daemon 不可用，容器权限与 Prisma 迁移在服务器验证。
- 服务器：新 Web 镜像的 UID 1001 读取和隔离库迁移通过。最终切换后 Platform、Web、nginx 均运行且重启数为 0；登录、CSRF、v2 迁移文档返回 200，Platform 健康接口可用。Platform Peer ID 与切换前一致，四个在线 SQLite 数据库 `PRAGMA quick_check=ok`；新 Web 表 `UserPolicyConsent` 与 `UserControlPause` 已建立。v2 策略接口返回预期的 404。
- 发布范围：本次只推送 GitHub 源码并更新服务器镜像；官网现有安装包、Python wheel、GitHub release 资产未重发，不能宣称老用户已通过公开安装包升级。用户迁移和离线签发步骤见[合规模式迁移指南](../operations/V2_MIGRATION.md)。

开启生产 v2 私密或合规策略仍需独立核对 Platform 身份、离线保管策略根及网关密钥、发布签名策略、更新受管 Agent 与 Web 配置、告知已有用户并收集授权，再按迁移指南分阶段验收。普通代码回退应恢复保留的旧镜像并保留实时数据；备份数据库仅用于故障恢复，避免覆盖上线后的用户写入。本记录的纯文档提交不代表再次切换应用镜像。
