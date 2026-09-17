# 发布记录

记录按日期与当日发布顺序排列，最近发布在前。它们保留发布当时的提交、镜像、源码清单、备份位置、检查结果和限制；目录整理本身不代表线上已更新，实际部署和安装包范围以每条记录为准。

| 日期 | 发布 | 记录内容 |
| --- | --- | --- |
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

最新源码组合由根仓库递归子模块引用确定，不能用较早记录的 “deployed” 或测试数量证明新提交的运行状态。官网安装包和源码 ZIP 已更新为 `2026-09-18-onboarding-r2`，固定 Deploy 提交为 `cb0909d975e0b6e52ba9dd949fcc2753e0aaaa7b`；确切提交与校验值以下载目录的 `release-manifest.json` 为准。GitHub v0.7.0 Release 保留原发布资产，没有被此次官网接入包覆盖。

新增发布记录应写清发布时的版本、检查范围、持久数据变化、运行结果和回滚位置；不将密钥、真实数据库或原始私人日志放入仓库。通用步骤在 [运维指南](../operations/DEPLOYMENT.md) 中维护。
