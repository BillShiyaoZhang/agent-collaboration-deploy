# 2026-09-24 Platform 管理台功能与界面更新

Platform 管理台更新了浅色响应式界面、导航、表格与弹层的键盘操作、焦点管理和中英文文案。界面改用运行时返回的 Registry TTL、MQ 单收件人上限和真实连接/队列数据；批量操作会逐项报告失败，配置输入不再被自动刷新覆盖。管理令牌仅保存在当前标签会话中。

管理 API 修复了节点与模式含义不一致的问题，并将 `store_user_data`、已确认信封保留天数持久化到现有 `platform_data` 卷的 `/data/admin-policies.yaml`。主配置仍为只读挂载。存储策略切换时先记录待重启状态，再清理 Registry；若重启中断，启动阶段会完成恢复。新的策略文件在首次管理操作前不存在，此时沿用主配置。

## 发布版本与回退位置

| 仓库 | 生产运行代码提交 |
| --- | --- |
| Deploy | `ebc2e45ea19b5918523dd4380d15d329e66ecc9d` |
| Platform | `13439b5f205c6b7ac4fbb9287bc72ee5c7d31329` |
| Web | `dfb3e7b8776971134f594d9206e6201e58c3f3bd`，本次未重建 |
| SDK | `d8adfade59cbf1b0bcc979c762eec2ad9d466c4c`，本次未重建 |

| 容器 | 切换后镜像 |
| --- | --- |
| Platform | `sha256:414fcb21a117819e328c9ab9a53d02a8abd878079398ea0c6b039e882ec2ea43` |
| Web | `sha256:270473f9f1c0ebcc02c44f63f3b15fb65c14c9c8d74e1032567827afdeaba9db` |
| nginx | `sha256:311761cac6bbc23041f3f4302699b0b5d0614e0a4d28b70def415e7bf16050c1` |

服务器切换前 Deploy 为 `dacd549683953896ea18ca4d8f36c34849cf72df`、Platform 为 `10d9a1a0c857dffa7b65a7acb77b6ab51cdea1f0`，旧 Platform 镜像 `sha256:ac39c494245b7672c9e385c067da28a1691b39df0b2753b08f8466c823a1ba80` 保留为本机标签 `agent-platform:rollback-20260924-admin-ui`。备份目录为 `/root/agent-comm-backups/2026-09-24-platform-admin-refresh`，权限 `0700`；包含四个 SQLite 在线备份、Platform 身份密钥及卷内其他文件、`.env`、配置、Compose 文件、摘要清单与版本元数据。备份与实时库的四个 `PRAGMA quick_check` 均为 `ok`，备份 SHA-256 清单逐项通过。

## 验证

- 本地：Node 管理台安全、功能与可访问性测试 11/11 通过；Go 1.26.8 容器内 `go test ./...`、`go test -race ./internal/api ./cmd/platform` 和 Linux amd64 构建通过；仓库文档结构检查 106 份 Markdown、0 错误。
- 生产：在阿里云 ECS `i-0jleb7de83gsnoa0yuc2` 上完成备份、固定提交检出、Platform 镜像构建，并仅重建 Platform 容器。三个容器均运行，重启数为 0；Web 和 nginx 容器 ID 未改变，Compose 与 nginx 配置检查通过。
- 公网只读检查：`/healthz`、`/admin/`、新 `/admin/console.css`、官网首页、`/docs/` 和下载清单均返回 200；无令牌管理概览返回 401。携带服务器现有令牌的只读请求验证了概览、配置、Registry、MQ、Peers 和日志端点均返回 200，且令牌在配置响应中被遮盖。
- 切换前后 Platform Peer ID、模式、存储及转发策略、保留天数一致；当时 Registry 为 17 条，MQ 待投递为 1 条。概览中的 Registry TTL 为 24 小时、MQ 上限为每 URN 500 条，与运行时配置一致。浏览器检查了新版窄屏授权入口。生产未执行会清理 Registry、消息或修改策略的管理操作。

本次只发布 Platform 服务及其内嵌管理台；官网公开安装包未重新生成。回退应用时，在核对实时策略后，将保留的旧镜像重新标记为 `agent-collaboration-deploy-platform:latest`，仅重建 Platform，并按上述旧提交恢复对应源码。保留当前生产卷、身份与回退后产生的新写入；不得直接用备份数据库覆盖实时库。若上线后已通过管理台修改存储或保留策略，回退前须先核对 `/data/admin-policies.yaml` 与旧程序的配置兼容性。
