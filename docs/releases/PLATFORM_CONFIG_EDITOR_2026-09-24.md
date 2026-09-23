# 2026-09-24 Platform 系统配置编辑

Platform 管理后台的“系统配置”页现在可点选或输入六项已接入运行逻辑的参数：Registry 注册有效期、MQ 新消息默认有效期和每个 URN 的消息上限，以及 Relay 的启用状态、最大预约数和单条电路时长。管理员先查看服务端计算的当前值、目标值、相关计数和影响，再二次确认；确认令牌五分钟后失效，配置版本变化则拒绝旧预览。写入 `/data/admin-policies.yaml` 后由守护进程重启 Platform，页面复读生效值。既有的存储、转发、已读历史保留策略继续从管理台操作。

已有注册和消息不会因这六项参数变更而追溯改写或删除。降低信箱上限可能拒绝后续写入；重启会短暂中断 HTTP、libp2p 和 Relay 连接，关闭 Relay 可能使依赖它的 NAT 后节点失联。身份密钥、数据库路径、监听、TLS、管理令牌和反向代理信任等高风险设置仍由服务器部署管理；当前无运行效果的主配置项没有被包装为可用开关。具体边界见[管理后台指南](../operations/PLATFORM_ADMIN.md)和 [Platform API](../../agent-comm-platform/docs/guides/API.md)。

## 固定版本与备份

| 项目 | 运行值 |
| --- | --- |
| Deploy 应用与指南提交 | `e07c626d44b57e6c03333e6a7f2f666c1d226e62` |
| Platform 子模块 | `1274b6458fd4442887267b2e72298b387629adba` |
| Platform 镜像 | `sha256:62b3247cfd5658160c9a97814f037170b6993883a8dc7efe6581faecd191134d` |
| Web 镜像 | `sha256:270473f9f1c0ebcc02c44f63f3b15fb65c14c9c8d74e1032567827afdeaba9db`，未重建 |
| nginx 镜像 | `sha256:311761cac6bbc23041f3f4302699b0b5d0614e0a4d28b70def415e7bf16050c1`，未重建 |

上线前 Deploy 为 `b0d8c08dbad82347e986c990fed1575559f09725`、Platform 为 `f04a0e738ff784eb5348e31dee4e8526ebc2f282`，旧镜像 `sha256:c4de25fc3ad1bc5e51eaaa073358dfa6a5301dcaacda4a253bdb58c28fa28474` 已标记为 `agent-platform:rollback-20260924-config-editor`。服务器备份目录为 `/root/agent-comm-backups/2026-09-24-platform-config-editor`，包含 Platform 审计、MQ、Registry 和 Web 数据库的在线 SQLite 快照、两个数据卷的非数据库文件（含身份与策略）、`.env`、Compose、主配置及 SHA-256 清单。四份备份数据库的 `PRAGMA quick_check` 和清单校验通过；这些机密备份未进入仓库。

## 验证与上线

- 开发环境：Platform 全量 Go 测试、API/配置/MQ 竞态测试通过；管理台 Node 测试 26/26 通过；根仓库文档结构检查 109 个 Markdown、0 错误；最终 Dockerfile 构建通过。隔离的真实 Platform 容器经无令牌拒绝、旧修订号拒绝、服务端预览、缺少令牌拒绝、确认保存和自动重启后复读，验证策略及 Peer ID 保持；覆盖文件权限为 `0600`。1440px 和 500px 管理台截图经人工检查，无横向溢出。
- 生产环境：阿里云 ECS `i-0jleb7de83gsnoa0yuc2` 从固定提交构建，仅重建 Platform。Compose 与 nginx 配置检查通过；三个容器均为运行状态、重启数均为 0。Web、nginx 镜像未变。平台 Peer ID 上线前后均为 `12D3KooWNApwdxwbXY27N44cGxTXY15Hn8yRx9m9Yw5St5A7kTpK`。
- 公网只读验收：`/healthz`、`/admin/`、部署和 Platform API 文档路由均返回 200；新页面包含配置编辑入口；无令牌读取新配置接口返回 401。有令牌读取六项字段、执行**不写入**的同值预览均成功，`restart_pending=false`；既有管理概览、MQ、Registry、审计及脱敏配置接口仍正常。验收时 `stores_user_data=true`、`forward_to_storage_platforms=true`、Registry 17 条、MQ 待收 4 条、历史 11586 条、已过期 4 条；这些业务计数是不断变化的快照。
- 切换后的 Platform 审计、MQ、Registry 三个实时数据库 `PRAGMA quick_check` 均为 `ok`；备份清单再次校验通过，服务器根仓库和 Platform 子模块工作树干净。生产未提交配置修改，也未对业务数据执行删除、驱逐或清空。

回退应用时使用上述旧提交与旧镜像，仅重建 Platform，保留实时数据卷及上线后的写入。**若管理员已经使用新界面保存六项参数，旧版无法解析覆盖文件中的新字段**：回退前先另行保留实时 `admin-policies.yaml`，按对应主配置审查并移除新字段，再切换旧版；不要用上线前备份直接覆盖实时数据库。此记录随后的纯文档提交不代表再次切换应用镜像。
