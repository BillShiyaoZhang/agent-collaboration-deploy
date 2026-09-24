# 发布记录

记录按日期与当日发布顺序排列，最近发布在前。它们保留发布当时的提交、镜像、源码清单、备份位置、检查结果和限制；目录整理本身不代表线上已更新，实际部署和安装包范围以每条记录为准。

| 日期 | 发布 | 记录内容 |
| --- | --- | --- |
| 2026-09-24 | [Agent Comm v0.8.0 客户端与官网下载发布](V2_CLIENT_RELEASE_2026-09-24.md) | GitHub 16 项资产、官网五份 ZIP、固定策略信任锚、生产新镜像；旧 r2 与 v0.8.0 双 Hermes 线上验收 |
| 2026-09-24 | [生产 v2 私密兼容策略启用](V2_PRIVATE_COMPAT_POLICY_2026-09-24.md) | 签名 private/allow_v1、首轮 nginx 上游故障回退、线上 r2 与 v2 双 Agent 验收及续签期限 |
| 2026-09-24 | [v2 协议代码上线（兼容阶段）](V2_CODE_DEPLOYMENT_2026-09-24.md) | 四仓 main、云端固定镜像、备份与权限修复；v2 策略尚未启用 |
| 2026-09-24 | [Platform 系统配置编辑](PLATFORM_CONFIG_EDITOR_2026-09-24.md) | 六项运行参数预览确认、隔离重启验证、生产备份与只读验收 |
| 2026-09-24 | [Platform 管理操作扩展](PLATFORM_ADMIN_OPERATIONS_2026-09-24.md) | MQ 汇总与分页、单封处置、明确目标策略、生产备份和只读验收 |
| 2026-09-24 | [Platform 管理台功能与界面更新](PLATFORM_ADMIN_REFRESH_2026-09-24.md) | 管理台响应式改版、运行时数据与策略持久化、生产备份和验收 |
| 2026-09-23 | [Platform API 文档归并](PLATFORM_API_DOCS_CONSOLIDATION_2026-09-23.md) | 云端 API 契约迁入 Platform `docs/`、中英双语、旧网址兼容跳转及生产复核 |
| 2026-09-23 | [官网文档入口统一](DOCS_UNIFICATION_2026-09-23.md) | `/docs/` 按角色阅读、`/docs/api/` Platform API、四仓原文只读挂载、备份、上线与 API 文案补丁复核 |
| 2026-09-23 | [Web SQLite 单连接缓冲与慢轮询观测 r3](WEB_SQLITE_BUFFER_RELEASE_2026-09-23.md) | Web 进程内查询缓冲、慢轮询分段计时、阿里云 Web 镜像更新与真实双 Agent 验收；官网接入包保持 r2 |
| 2026-09-23 | [全栈测试修复与官网接入包 r2](TESTING_REMEDIATION_RELEASE_2026-09-23.md) | D-01 首装、D-02 SQLite 争锁处理、正式包重建、阿里云部署及重叠压力验收 |
| 2026-09-20 | [网站字号与可访问性修复](ACCESSIBILITY_RELEASE_2026-09-20.md) | 字号、键盘焦点、响应式布局、触摸目标及官网静态链接可读性修复 |
| 2026-09-18 | [Hermes 官网自动接入](HERMES_AUTONOMOUS_ONBOARDING_RELEASE_2026-09-18.md) | 官网接入包 r2、单命令安装、网页一次确认、签名授权与本机后台自动配对 |
| 2026-09-17 | [agent-comm v0.7.0 正式客户端发布](GITHUB_CLIENT_RELEASE_2026-09-17.md) | GitHub 四平台 helper、完整安装包、Python wheel 与官网同源同步 |
| 2026-09-17 | [Agent / Web 能力一致性上线](AGENT_WEB_PARITY_RELEASE_2026-09-17.md) | 本机数据权威、好友与消息闭环、跨端已读、在线状态、配套接入包及 Linux 候选验证 |
| 2026-09-17 | [安全修复上线](SECURITY_RELEASE_2026-09-17.md) | 四仓安全修复、正式镜像重建、密码升级与上线验收 |
| 2026-09-15 | [并行 worktree 整合与磁盘清理](WORKTREE_INTEGRATION_2026-09-15.md) | 四仓合并、组合验证、固定版本部署、备份回滚与构建缓存清理 |
| 2026-09-15 | [Hermes 真实协作及 Web 修复](../verification/HERMES_COOPERATION_TEST_2026-09-15.md) | 真实多轮协作、恢复/租约/SQLite 修复、本机安装、Web 切换和后续源码提交 |
| 2026-09-14 | [官网分离](INTRODUCTION_RELEASE_2026-09-14.md) | 静态官网归属 Web，nginx 路由、独立运行和多端介绍 |
| 2026-09-14 | [账户持久化与主动同步](WORKSPACE_SYNC_RELEASE_2026-09-14.md) | 账户加密副本、启动同步、迁移和恢复验证 |
| 2026-09-14 | [工作台 UI/UX](UI_UX_RELEASE_2026-09-14.md) | 应用式导航、响应式布局、Linux 候选与公网检查 |
| 2026-09-14 | [首次早期试用](EARLY_ACCESS_RELEASE_2026-09-14.md) | 公开安装包、首次工作台、增量迁移和证书续期修复 |
| 2026-09-13 | [Registry ownership](REGISTRY_DEPLOYMENT_2026-09-13.md) | HTTP/libp2p 身份所有权修复、数据保留与恢复位置 |
| 2026-09-13 | [HTTPS 登录修复](HTTPS_LOGIN_FIX_2026-09-13.md) | 安全及分块 cookie、认证回归和生产验证 |

最新源码组合由根仓库递归子模块引用确定；线上运行提交和镜像须以最近一条**完成核对**的发布记录及服务器实际状态为准。[v0.8.0 发布记录](V2_CLIENT_RELEASE_2026-09-24.md)列出当前公开客户端、生产镜像和校验范围；[生产 v2 私密兼容策略记录](V2_PRIVATE_COMPAT_POLICY_2026-09-24.md)保留策略首次切换及 r2 验收；先前的[协议代码上线记录](V2_CODE_DEPLOYMENT_2026-09-24.md)保留未启用策略时的状态。发布记录本身的纯文档提交不代表服务器再次切换应用代码。公开客户端版本和校验值以[官网发布清单](https://agent-communication.online/downloads/release-manifest.json)为准。

新增发布记录应写清发布时的版本、检查范围、持久数据变化、运行结果和回滚位置；不将密钥、真实数据库或原始私人日志放入仓库。通用步骤在 [运维指南](../operations/DEPLOYMENT.md) 中维护。
