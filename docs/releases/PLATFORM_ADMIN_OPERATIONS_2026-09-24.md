# 2026-09-24 Platform 管理操作扩展

本次扩展 Platform 管理后台的日常处置能力：MQ 增加待收、已读历史和过期消息互不重叠的汇总；管理员可按任意收件人 URN 分页查看消息元数据、按需读取单封密文并只删除指定收件箱中的单封消息。页面显示操作状态及失败原因，删除前要求确认。存储与转发策略改为提交明确目标值，转发策略持久保存；存储策略切换后，页面等待服务恢复并核对目标状态。概览提供 `restart_pending`，用于区分已安排重启与重启完成。旧管理接口继续兼容，旧批量明细读取受到 100 条、2 MiB 载荷预算限制。

能力边界、日常操作和回退步骤见 [Platform 管理后台](../operations/PLATFORM_ADMIN.md)。管理令牌仅授权 Platform 持有的 Registry、加密信箱、策略、连接诊断和审计；不会赋予 Agent 本机的配对、审批或签名权限。

## 发布版本与备份

| 项目 | 本次运行值 |
| --- | --- |
| Deploy 根仓库 | `4dfa24b1f4b6ddb9dca6961f7d7bc5ecc1628406` |
| Platform 子模块 | `f04a0e738ff784eb5348e31dee4e8526ebc2f282` |
| Platform 镜像 | `sha256:c4de25fc3ad1bc5e51eaaa073358dfa6a5301dcaacda4a253bdb58c28fa28474` |
| Web 镜像 | `sha256:270473f9f1c0ebcc02c44f63f3b15fb65c14c9c8d74e1032567827afdeaba9db`，本次未重建 |
| nginx 镜像 | `sha256:311761cac6bbc23041f3f4302699b0b5d0614e0a4d28b70def415e7bf16050c1`，本次未重建 |

上线前服务器 Deploy 为 `ea02edb8ff2e75e83afe1f7bcef176c7854f7962`，Platform 为 `13439b5f205c6b7ac4fbb9287bc72ee5c7d31329`，旧 Platform 镜像 `sha256:414fcb21a117819e328c9ab9a53d02a8abd878079398ea0c6b039e882ec2ea43` 保留为 `agent-platform:rollback-20260924-admin-operations`。备份位于服务器 `/root/agent-comm-backups/2026-09-24-platform-admin-operations`，包含 Platform 的 Registry、MQ、审计和 Web 账户数据库的在线 SQLite 快照、身份及其他非数据库卷文件、`.env`、Compose、Platform 配置和 SHA-256 清单。四个备份数据库的 `PRAGMA quick_check` 均为 `ok`，清单校验通过。备份含机密数据，未进入 GitHub。

## 验证与上线结果

- 本地：Platform `go test ./...`、相关 API/MQ/配置模块竞态测试通过；管理台 Node 测试 18/18 通过；Linux amd64 生产 Dockerfile 构建通过；根仓库文档结构检查通过。以模拟 API 检查了 1440px 桌面和 500px 窄屏布局。
- 生产：阿里云 ECS `i-0jleb7de83gsnoa0yuc2` 从固定提交构建并仅重建 Platform。Compose 与 nginx 配置检查通过；Platform、Web、nginx 均为 `running`，重启数均为 0。Web 与 nginx 容器 ID 未变化，Platform 当前 Peer ID 为 `12D3KooWNApwdxwbXY27N44cGxTXY15Hn8yRx9m9Yw5St5A7kTpK`。
- 公网只读验收：`/healthz` 与 `/admin/` 返回 200，页面包含新分页消息入口；无令牌概览返回 401。使用服务器现有令牌读取概览、脱敏配置、MQ 汇总、空信箱分页、Registry 与审计均成功；配置响应不包含明文管理令牌。验收时 `restart_pending=false`、`stores_user_data=true`、`forward_to_storage_platforms=true`、Registry 17 条、MQ 待收 2 条、历史 11926 条、已过期 5 条。计数是验收时快照，会随业务变化。
- 四个实时 SQLite 数据库在切换后的 `PRAGMA quick_check` 均为 `ok`；服务器两个 Git 工作树干净。生产没有为冒烟测试执行删除、清空、驱逐或策略修改；真实多 Agent 业务完成不在这次只读验收范围内。
- 最终巡检发现部分仓库 Markdown 因此前的限制性检出权限为 `0600`，公开文档源码路由返回 403。已将四个只读挂载文档目录内的 Markdown 设为 nginx 可读；部署、Platform API 与本次新增的管理后台指南路由复查均返回 200，Git 内容未变。

回退应用前先核对实时策略文件与旧版本的兼容性，使用保留的旧镜像和对应提交仅重建 Platform。保留实时数据卷、身份与上线后的新写入；不把上线前数据库备份直接覆盖实时库。本次没有重发官网安装包。
