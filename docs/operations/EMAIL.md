# 官方邮箱与账户事务邮件

本方案把两类邮件分开：Resend 负责 `accounts@notify.agent-communication.online` 的注册验证、密码找回和修改确认；腾讯企业邮箱基础版可在以后开通 `support@agent-communication.online` 的人工收发。可以先只启用 Resend，人工邮箱未开通时保持 Reply-To 和网站客服入口为空，邮件不承诺回复有人处理。腾讯人工邮件不消耗 Resend 额度。本文是开通与部署步骤，不是邮件已开通、DNS 已变更或现网已发布的证明。

## 开通前准备

准备域名 DNS 管理权限、可接收验证码的手机、管理员恢复邮箱，以及安全保存凭据的位置。在 DNS 控制台导出或截图现有记录，特别是网站根域和 `www` 的 A/AAAA、根域 MX、SPF/DKIM/DMARC。邮箱使用同一域名不要求更改网站 IP、Web HTTPS 证书或 Platform 配置。邮箱 MX 不等于网站 A/AAAA。

[腾讯官网](https://exmail.qq.com/)当前提供免费基础版，注册中的管理员及主体资料以实际控制台要求为准。[Resend 免费额度](https://resend.com/docs/knowledge-base/account-quotas-and-limits)当前为每天 100 个收件人、每月 3,000 封，按 UTC 日重置，即北京时间 08:00。每次重发、验证、找回或修改确认均消耗额度；一个用户不等于一封邮件。本应用默认全局预算为每天 90 次发送尝试，失败的尝试也计入预算，预留 10 次供验收等用途。配置值仅允许 1～100；另外全局每分钟最多 10 次，同一收件人跨用途等待 60 秒，明确发送失败后至少等待 15 秒再试。Resend 同一团队其他应用或控制台发信共享提供商额度，应用预算不能代替提供商 Usage 检查。

## 1. 可稍后开通腾讯人工邮箱

仅启用 Resend 时可以先跳过本节，不变更根域收信 MX、不显示人工客服地址。

1. 从[腾讯企业邮箱](https://exmail.qq.com/)选择基础版免费开通，建立管理员并按实际流程验证手机、恢复方式及要求的资料。不要误选专业版试用或付费购买。
2. 添加已有域名 `agent-communication.online`。根据控制台提示在实际权威 DNS 服务商创建域名所有权验证记录；主机名、类型、TXT/CNAME 值全部复制腾讯当次显示的值。
3. 进入域名的收信配置。把腾讯要求的根域 MX 目标及优先级逐项录入 DNS，核对主机名是否为根域（通常 DNS UI 显示 `@`）。若根域已有其他邮箱服务，先核实并安排迁移；不要混放两个提供商的根域 MX 期待邮件自动送两份。
4. 按腾讯控制台配置发信认证 SPF/DKIM；不要在同一个主机名建立两条 `v=spf1` TXT，已有 SPF 需要在提供商指导下合并。DMARC 见后文。具体记录以腾讯控制台为准，本文不提供可被误当作真实记录的样例目标。
5. 创建 `support` 成员邮箱，显示名设为 `Agent Comm 支持`。单人客服先用独立邮箱，不假定免费版有多人共享工单能力；团队扩大时再使用提供商支持的委派或共享邮箱。
6. 按腾讯控制台提供的网页登录、企业微信或 Foxmail 方式登录 support。管理员与日常客服密码分别保存；Web 项目不需要腾讯密码或 SMTP 授权码。
7. 用你自己控制的 QQ、163、Gmail、Outlook 地址分别给 support 发信，再从 support 回复，检查发件地址、内容、垃圾箱和投递结果。某一家失败就先处理该路径，不能以“全球收发”宣传替代真实验收。

## 2. 开通 Resend 事务发信

1. 在 [Resend](https://resend.com/)创建免费账户，进入 Domains 添加 **`notify.agent-communication.online`**，选定控制台可用的发信区域。只启用发信，保持 Receiving/inbound 关闭；Resend 不承担本方案的人工收信。
2. 在该域名的 Records 页面复制每一条记录的类型、完整主机名、值及优先级（如有），到域名 DNS 服务商逐项添加。DNS UI 若自动附加 `agent-communication.online`，按其规则填相对主机名，避免变成重复域名。
3. 特别核对 DKIM 和 Return-Path。Resend 官方说明：2026 年 8 月后创建的域名可能使用 CNAME，较早配置可能是 MX + TXT；必须照当次 Records 页面配置，不能照旧教程硬填某个区域的服务器或分配公钥。CNAME 所在主机名不能同时有其他类型记录；冲突时在 Resend 选择空闲的 Return-Path 子域，不删除网站记录。[官方记录冲突说明](https://resend.com/docs/knowledge-base/how-do-i-avoid-conflicting-with-my-mx-records)
4. 这些发信认证／退信记录应落在控制台显示的 notify、DKIM 或 Return-Path 主机名。**保留根域 `agent-communication.online` 的现有收信 MX**；腾讯开通后根域 MX 由腾讯负责，不要为了 Resend 验证覆盖它，也不要开启 Resend 根域收信。notify 子域无需配置 Resend inbound MX。
5. 在 Resend 点击 Verify，等待域名全部必需的发信记录显示通过。在域名设置关闭 Open/Click Tracking，保持密码和验证链接为本网站原始链接。[官方域名说明](https://resend.com/docs/dashboard/domains/introduction)
6. 在 API Keys 创建仅允许 Sending、限定该发信域名的密钥；复制一次并保存在服务器受保护的 `.env` 或密钥管理中。不放到浏览器、源码、工单、公开安装包或截图。
7. `accounts@notify.agent-communication.online` 是发件标识，无需在腾讯另外开同名收件箱。人工邮箱尚未开通时不设置 `Reply-To`；邮件只用于网站账户确认，不承诺收件人回复能被人工处理。support 通过双向收发验收后，再配置 Reply-To 与网站客服入口。

## 3. DNS 核对与 DMARC

| 用途 | 必须核对的记录 | 值从哪里取得 |
| --- | --- | --- |
| 网站 | 根域和 `www` 原有 A/AAAA、CNAME（若有） | 变更前导出的现有网站配置；保留 |
| 腾讯所有权与收信 | 腾讯指定验证记录、根域 MX 目标与优先级 | 腾讯控制台 |
| 腾讯人工发信 | SPF、DKIM（按实际提供功能） | 腾讯控制台 |
| Resend 发信 | notify 域名的 DKIM、Return-Path CNAME 或 MX/TXT | Resend Domains → Records |
| DMARC | 根域／notify 的 `_dmarc` TXT，检查策略及 From 对齐 | 当前域名策略与提供商 DMARC 指南 |

先查现有 `_dmarc.agent-communication.online`；没有现行策略时，可从 `p=none` 的监测策略开始，先在 Resend 的真实邮件头里确认（腾讯开通后也须核查） SPF、DKIM、DMARC 结果和域名对齐后再评估 `quarantine`／`reject`。不要直接覆盖已有严格策略，也不要编造报告邮箱；需要 `rua` 报告时先准备真实可收信地址。notify 没有自己的 DMARC 时可能继承根域策略，必须一起核查。[Resend DMARC 指南](https://resend.com/docs/dashboard/domains/dmarc)

在 PowerShell 查询公开解析，例如：

```powershell
Resolve-DnsName agent-communication.online -Type A
Resolve-DnsName www.agent-communication.online -Type A
Resolve-DnsName agent-communication.online -Type MX
Resolve-DnsName agent-communication.online -Type TXT
Resolve-DnsName _dmarc.agent-communication.online -Type TXT
Resolve-DnsName _dmarc.notify.agent-communication.online -Type TXT
# 再对控制台显示的每个完整 DKIM / Return-Path 主机名查询其对应类型。
```

Linux/macOS 可用 `dig <完整主机名> <记录类型> +short`。至少比较本地递归解析和权威 DNS 的结果，等 TTL 缓存生效后再次点击提供商验证。供应商显示 Verified 证明域名设置通过，不能单独证明邮件已进入用户收件箱。

## 4. Web 配置与发布

在服务器部署根目录已有 `.env` 中增加下列值，保留原 `NEXTAUTH_SECRET`、数据库与 v2 配置：

```dotenv
RESEND_API_KEY=<仅发信权限的真实密钥>
AUTH_EMAIL_FROM="Agent Comm <accounts@notify.agent-communication.online>"
AUTH_EMAIL_REPLY_TO=""
AUTH_EMAIL_DAILY_LIMIT=90
NEXT_PUBLIC_SUPPORT_EMAIL=""
```

`NEXTAUTH_URL` 必须为真实 HTTPS Origin `https://agent-communication.online`，账户链接从服务端该值生成，不从用户提交的 Host 生成。邮件服务需要到 `https://api.resend.com` 的 HTTPS 出站连接。`AUTH_EMAIL_REPLY_TO` 可空，控制事务信回复地址；`NEXT_PUBLIC_SUPPORT_EMAIL` 是可选的公开网站客服地址，默认空即隐藏入口。该值在构建时写入浏览器代码，只能放公开邮箱，不能放密钥。人工邮箱未开通时两项均留空。

空密钥可用于本地隔离检查；它不启用邮件。缺少必需的密钥、From、NEXTAUTH_URL，或生产 Origin 不是 HTTPS 时，邮件操作返回服务未配置；新用户不能完成验证注册、找回或修改密码，不得称这些流程已经上线。有效配置下，公开注册／重发／找回接口对账户不存在、提供商失败或限流仍使用统一中性提示，不能据此断言已发信；认证后的修改密码可显示明确的服务不可用或限流错误。已有迁移账户仍可按原密码登录，邮箱验证状态仍为未验证；账户页可发起补验。新增账户必须完成真实邮箱验证才能登录。

按[部署与升级指南](DEPLOYMENT.md#升级备份与回退)备份并发布固定组件提交。已启用 v2 的环境不能遗漏 `docker-compose.v2.yml`。以下只展示配置检查和重建已有服务，现有低内存服务器的镜像应按部署指南在另一主机构建、上传并校验，不能直接照此在 ECS 上构建：

```sh
docker compose -f docker-compose.yml -f docker-compose.v2.yml config --quiet
# 完成镜像准备、备份与源码/配置同步之后：
docker compose -f docker-compose.yml -f docker-compose.v2.yml up -d --pull never --no-deps --no-build --force-recreate web
docker exec agent-nginx nginx -t
docker exec agent-nginx nginx -s reload
```

只改运行时 `.env` 后执行 `restart` 不会装入新环境变量；需要重新创建 Web 容器。`NEXT_PUBLIC_SUPPORT_EMAIL` 不属于可动态改变的运行时入口：Docker builder 通过 ARG/ENV 在 `npm run build` 前读取它，Compose 从 `.env` 传入 build args。以后腾讯 support 通过验收后，设置 `AUTH_EMAIL_REPLY_TO=support@agent-communication.online` 与 `NEXT_PUBLIC_SUPPORT_EMAIL=support@agent-communication.online`，在构建主机使用相同的公开地址重建 Web 镜像，再部署该镜像并重新创建容器；只改服务器 `.env` 或 recreate 不能让旧镜像新增客服入口。新账户邮件迁移由 Web 启动入口执行，独立源码运行时使用 `npm run db:migrate`；先在一致性数据库备份副本上验证。nginx 文件已挂载时配置检查后 reload；挂载本身变化则按部署指南重建 nginx。禁止打印包含密钥的完整 `docker compose config`。

nginx 对账户写入和凭证登录共用每 IP 每分钟 5 次、突发 5 次、16 KiB 请求体规则；应用还有邮件全局预算及重发节流。token 页面使用 `no-store` 与 `Referrer-Policy: no-referrer`；nginx 访问日志省略 query 和 Referer，避免链接中的 token 进入访问日志。nginx 错误日志在代理故障时仍可能包含完整请求 URL；应限制错误日志访问及保留时间，分享诊断资料前删除 query/token，不复制原始链接。应用只记录安全错误代码；不要额外记录 API 请求体、token、密码、新密码 hash 或完整邮件正文。

## 5. 上线验收与日常检查

使用自己控制的真实邮箱和测试账户，留存日期、部署提交、供应商 Message ID 与去除敏感内容后的结果；不要在报告里保留验证／重置链接、密码或密钥。

1. **发信与可选人工客服**：先验收 QQ、163、Gmail、Outlook 能收到 Resend 事务邮件。人工邮箱未开通时网站不显示客服 mailto、邮件不声明回复会被处理；腾讯开通后才追加 support 双向收发验收，并检查 Reply-To 及人工答复地址。
2. **新增账户**：注册后不能在验证前登录；邮件显示正确 From（启用人工邮箱后再核对 Reply-To），验证页面需本人明确确认，完成后能登录。验证链接有效期 24 小时，找回与修改确认链接有效期 30 分钟。重复使用、过期或篡改链接不能再次生效；失效后使用重发入口。
3. **旧账户**：原密码仍能登录，页面显示邮箱尚未验证；补验后才显示已验证。原控制台 URN、连接、配对、联系人和历史仍在，不能通过新建身份代替迁移。
4. **忘记密码**：登录页请求找回，页面不透露邮箱是否存在；收信后自行设置新密码。新密码可登录，旧密码不能登录，另一浏览器中的旧登录会话失效。没有邮件就检查垃圾箱和 Resend 状态，再按节流提示重试。
5. **登录后修改密码**：在账户设置输入旧密码及新密码；收到邮件并明确确认前旧密码仍有效，确认后新密码生效、旧会话失效。输错旧密码不能发送修改确认；别人替你点击不应成为自动确认。
6. **额度与故障**：在隔离环境检查发送预算、重发冷却和代理 429／413；生产不要为了测试耗尽额度。密钥为空、供应商拒绝或额度不足时，界面不能显示“验证已完成”。恢复后用户可重发，不能假装邮件已投递。
7. **日志与浏览器**：检查 nginx 不记录 query／Referer；token 页面响应有 no-store/no-referrer。邮件客户端的链接预览不能自动验证或改变密码，页面必须提交明确确认。

Resend API 接受请求与收件人实际收到是不同状态。初期在 Resend Dashboard 核查 sent/delivered/bounced/complained 及 Usage，并用真实收件箱验收；当前应用未接入回调时，不把控制台投递状态宣称为网页可追踪的送达状态。退信或投诉需人工检查收件地址和原因，不能持续重发。腾讯支持邮箱的收到、回复与业务问题解决也应分别记录。

本地代码／配置检查完成后，仍需完成 Resend 账号、发信 DNS、密钥配置、发布与真实收信验收；腾讯账号及根域收信可稍后由域名所有者开通。没有发布并实测的能力状态仍为**尚未验收**，不因已经取得 API Key 而变成已上线。普通使用步骤见[账户邮箱与客服指南](../users/ACCOUNT_EMAIL.md)。
