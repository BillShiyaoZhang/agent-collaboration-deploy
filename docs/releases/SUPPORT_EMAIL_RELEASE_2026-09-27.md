# 人工客服邮箱启用记录

2026-09-27（Asia/Shanghai），域名所有者确认阿里企业邮箱已配置，并提供官方客服地址 `support@agent-communication.online`。本次已将该地址启用为网站客服入口和账户事务邮件 Reply-To。注册验证、密码找回、修改密码确认仍通过 Resend 发送，From 保持 `Agent Comm <accounts@notify.agent-communication.online>`。

## 发布版本与配置

| 项目 | 应用切换时的固定版本 |
| --- | --- |
| 部署仓库 | `25b81b340d8deb064fc6c612879b027270e3984d` |
| Web | `78c019bf132e7b55e31b5987ba11617a6ba15662` |
| Platform | `8382a74a881ded7d46241c9333ac06bb55fe078d` |
| SDK | `fb7fb916945a5c11c219c517f7ff20a1b2856105` |
| Web Linux/amd64 镜像 | `sha256:6e0c320f65a00266a2fc8c1df0ca7a21e80079604130bc0ce204a3a4e9a9db39` |
| 镜像归档 SHA-256 | `0b77b31e404254ffe73b558810b2ea0d829316965674d6f9d04fb12b5b54fa47` |

Web 的 `PublicFooter` 现在复用可选 `publicSupportEmail`，官网及文档阅读器增加中英文客服链接，沿用原有页脚的换行、44px 触达与键盘焦点样式。已有登录、注册、密码操作、邮件确认及工作台入口继续使用同一配置。自部署示例默认仍为空，配置无效时隐藏链接。

生产构建以 `NEXT_PUBLIC_SUPPORT_EMAIL=support@agent-communication.online` 生成浏览器与预渲染页面；服务器 `.env` 同时设置该公开变量及 `AUTH_EMAIL_REPLY_TO=support@agent-communication.online`。二者独立，构建变量显示网站入口，运行时 Reply-To 决定事务信回复目的地。Resend 密钥、From、每日 90 次预算、NEXTAUTH_SECRET 及 v2 配置均保留。开通及变更步骤见[邮箱运维指南](../operations/EMAIL.md)。

镜像在本机 Docker Desktop 的 Linux/amd64 引擎从固定提交构建，导出、上传并核对校验值后在 ECS 加载。服务器只重新创建 Web，并检查、reload nginx 上游。完成切换时间为 `2026-09-26T16:58:24.979207+00:00`（北京时间 2026-09-27 00:58）；本记录及索引的后续纯文档提交不代表再次切换镜像。

## 实际验证

- `node --test tests/unit/support-email.test.cjs tests/unit/account-email.test.cjs`：16/16 通过，包含官网页脚中英文、无效／空地址隐藏，以及 fake provider 的 Reply-To 和账户邮件行为；使用隔离 SQLite 与合成凭据。
- 生产镜像构建、类型检查通过；一次性本地容器的 8 个页面返回 200，均显示正确 mailto，运行时公开变量为空也不会覆盖已经构建的地址。未使用真实邮件密钥，检查后删除该测试容器。
- 服务器实际 Web 镜像与源码修订匹配，运行时 Reply-To 已核对；其余 Web ENV、持久卷和 v2 挂载均与部署前基线一致。
- 服务器及本机公网访问 `/`、`/docs/`、`/login`、`/register`、`/forgot-password`、`/verify-email`、`/reset-password`、`/confirm-password-change`，均返回 200 且包含 `mailto:support@agent-communication.online`。
- 四个数据库 `quick_check` 均为 `ok`；原有 47 个用户、41 个 agent 连接及其身份与密码指纹保留。Platform/nginx 容器、19 项受保护配置中除预期 `.env` 外的文件均保持基线；签名 compliance epoch 3、allow_v1=false 及策略摘要不变。
- 私有工作台和 agents API 未登录仍返回 401，历史发布文档原文路由仍为 404；切换完成后到核查时未见数据库锁、连接池超时或容器 fatal/OOM 错误。

DNS 读取确认根域 MX 为阿里 `mx1/2/3.qiye.aliyun.com`，SPF 包含 `spf.qiye.aliyun.com`。邮箱账号开通由所有者确认；本次部署没有登录 support 收件箱或发送真实测试邮件，不将配置与页面验证写成国内外邮箱实际送达、人工回复或业务问题解决的证明。双向收发仍按[邮箱验收步骤](../operations/EMAIL.md#15-收发验收后交给部署维护者)进行。

## 备份与回退

服务器发布目录为 `/root/agent-comm-releases/2026-09-27-support-email`，目录仅 root 可访问。`pre-cutover/` 保存四库各自一致的在线备份、受保护配置和身份指纹基线；安全摘要为 `preflight-summary.json`、`deployment-summary.json` 与 `verification.json`，私密基线和 ENV 不发布到 Git。

前一镜像保留为 `agent-collaboration-web:pre-support-email-20260927`，ID 为 `sha256:5a24a25533c120bbbbdc2c1f076b17ce7497064ea3d9c2faadfd5313279047a2`，已支持邮箱验证要求及会话撤销。需要回退时恢复本次私密清单中的原 `.env` 和前一源码组合，重新标记并部署该镜像、检查与 reload nginx、核对实际镜像／ENV／挂载。保留实时数据库及升级后的用户写入，不覆盖为旧备份。通用步骤见[部署指南](../operations/DEPLOYMENT.md#升级备份与回退)。
