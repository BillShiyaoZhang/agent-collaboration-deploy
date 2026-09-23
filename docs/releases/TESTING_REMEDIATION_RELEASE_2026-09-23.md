# 2026-09-23 全栈测试修复与官网接入包 r2

2026-09-23 已将测试发现的自动首装期限误判、错误系统接入包误收、Web SQLite 争锁路径以及 nginx HTTP/2 旧语法修复部署到现有阿里云服务器。公开下载清单为 [`2026-09-23-testing-remediation-r2`](https://agent-communication.online/downloads/release-manifest.json)，包含 Windows、Linux、macOS Intel、macOS Apple Silicon 四份接入 ZIP 和源码 ZIP。历史邀请 PDF 保留。SDK 与 Platform 源码未变，本次没有移动或覆盖 GitHub `v0.7.0` Release 标签和资产。

| 项目 | 当前值 |
| --- | --- |
| Deploy 源码 | `30ed9aeb9e85f75b89a7170bfeeb7ad52a48d253` |
| Web 源码 | `55aab52e89633e31f147d537fb45af65396aa58b` |
| Platform 源码 | `2ed906d28f27d76cbdcf463b4031d364aae63486` |
| SDK 源码 | `ecf829dc31099ea889abf2633cbe47afd522eab5` |
| Web 镜像 | `sha256:6f016ab9d87df8fb79c85499c91ffb79b8c80deec8cdf60670b779e568e5e02a`，`linux/amd64` |
| 接入包内容 | runtime `0.1.4`、Hermes connector `1.5.5`、四平台 helper |
| 服务器备份 | `/root/agent-comm-backups/2026-09-23-testing-remediation-r2/`，权限仅 root |
| 服务器上传与校验 | `/root/agent-comm-releases/2026-09-23-testing-remediation-r2/` |

发布前，Web 178 项单测、lint 和生产构建通过；SDK Python runtime 154 项、Hermes connector 142 项、两套 Go 测试、接入测试 38 项、发布构建器 5 项、远程控制网络 17 项、双 Agent/Web 一致性 4 项及新镜像部署安全 3 项通过。四份正式 ZIP 均经过 `--check-only --cross-platform-check`，wheel 与当前源码逐文件一致。部署前在线备份 Web/Platform 四份 SQLite 数据库并逐一运行 `quick_check`，同时保存配置、Platform 密钥、旧下载目录和旧 Web 镜像回滚标签；上传文件在服务器上逐一核对 SHA-256。Platform 容器与镜像保持原样。

部署后，公网 HTTPS 首页和健康接口返回 200，TLS 校验通过；服务器核对运行中的 Web 镜像 ID、递归子模块提交、Nginx `nginx -t`、公开 Windows ZIP SHA-256 以及下载清单。nginx 新容器无 HTTP/2 弃用警告。正式 r2 包从**全新、独立的 Hermes venv/profile** 经公网下载完成安装前校验、Web 一次授权确认、Gateway 连接、能力读取、真实 Hermes 回显及 Web 工作台持久核对；同身份重跑仍只有一个配对，最终同步恢复为 `ready`。错误系统包和篡改 wheel 在安装前被拒绝。合成配对已撤销，隔离进程和临时凭据已清理。

与首装活跃同步重叠的双账户现网探针共 154 次请求，全部为 2xx：控制请求建立 2、控制轮询 60、工作台读取 64、总览 2、同步调度 20、认证 6。Nginx 5xx、Web 后台同步重试告警与传输错误均为 0。此前 r1 首装时两次未吸收的 SQLite Code 5 促成 r2 补丁：只对四条独立、幂等的工作台 SQL 做有限重试，真实第二 Prisma 连接持锁测试覆盖每条路径。r2 重叠压力窗口仍记录 4 次 SQLite Code 5，但请求成功、最终首装同步为 `ready`；两次合成账户的控制轮询分别约 10.7 秒和 9.9 秒，明显慢于通常的亚秒响应。现有日志不含 SQL 语句，尚不能把尾延迟唯一归因于某一写操作；这项性能风险继续保留，不宣称锁竞争已经消失。

另在隔离的生产模式 fixture 中对比 Prisma 默认连接池（25）与 `connection_limit=1/2`：相同的双账户、90 次控制请求、92 次工作台读取、24 次同步调度和 12 并发下，三组均无 HTTP 错误或 Code 5；控制轮询最长耗时分别为 3.75、1.50、1.20 秒。限池改善了本机尾部，但没有复现现网争锁，且本机与服务器 CPU 条件不同，因此没有凭这一次对照直接改变现网连接池。后续应先增加控制路由、Platform 调用及数据库事务的分段计时，再定位约 10 秒的停顿。

现网 Prisma 内嵌 SQLite 为 3.45.0，当前仍使用 `journal_mode=delete`。本轮没有直接改成 WAL：该版本落在 [SQLite 官方 WAL-reset 数据损坏问题](https://www.sqlite.org/wal.html#wal_reset_bug)影响范围。后续若升级 SQLite 并考虑 WAL，应重新测试迁移、备份和回滚。

本轮只在 Windows 原生环境执行完整 Hermes 首装；Linux/macOS 包完成交叉构建与完整性校验，未在对应原生宿主运行。双账户现网压力探针复用的旧 A/B 本机配对已撤销，因此它验证了 Web/Platform 轮询和工作台稳定性，不代表两个活跃 Agent 同时消费请求；真实单 Agent 首装/回显由独立 T12 覆盖。原测试中用户排除的 T05、T06、T07、T10 主观/人工环节未补测。原始失败记录和复核证据见[测试报告](../testing/TEST_REPORT_2026-09-23.md)与[修复记录](../testing/REMEDIATION_2026-09-23.md)。

回滚应先使用上述备份中的旧提交、`agent-collaboration-deploy-web:rollback-2026-09-23-testing-remediation-r2` 镜像标签和 `downloads-before-switch`，强制重建 Web/Nginx；下载目录是 nginx bind mount，目录切回后必须重建 nginx 才会读取新的目录 inode。数据库快照用于故障恢复，不应在普通代码回滚时覆盖部署后的新用户写入。完整命令与服务依赖按[部署指南](../operations/DEPLOYMENT.md)执行。
