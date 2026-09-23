# 发布记录

记录按日期与当日发布顺序排列，最近发布在前。它们保留发布当时的提交、镜像、源码清单、备份位置、检查结果和限制；目录整理本身不代表线上已更新，实际部署和安装包范围以每条记录为准。

| 日期 | 发布 | 记录内容 |
| --- | --- | --- |
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

最新源码组合由根仓库递归子模块引用确定，不能用较早记录的 “deployed” 或测试数量证明新提交的运行状态。本轮线上 Web 镜像对应的代码基线是 Deploy `125a8d0d223c4bceefae39de65dbe6c6522eb7e7`、Web `66bcef8900189560039b2fef41921e886240030b`；后续发布记录的提交只更新文档，不改变运行镜像。Platform 与官网安装包没有重发。官网安装包和源码 ZIP 仍为 `2026-09-23-testing-remediation-r2`，其中固定 Deploy 提交为 `30ed9aeb9e85f75b89a7170bfeeb7ad52a48d253`；确切提交与校验值以下载目录的 `release-manifest.json` 为准。GitHub v0.7.0 Release 保留原发布资产，没有被此次 Web 热修复覆盖。

新增发布记录应写清发布时的版本、检查范围、持久数据变化、运行结果和回滚位置；不将密钥、真实数据库或原始私人日志放入仓库。通用步骤在 [运维指南](../operations/DEPLOYMENT.md) 中维护。
