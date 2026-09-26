# 官方邮箱与账户事务邮件

本项目使用 **阿里企业邮箱免费版 + Resend 免费套餐**。阿里邮箱负责 `support@agent-communication.online` 的人工收发；Resend 负责 `accounts@notify.agent-communication.online` 的注册验证、密码找回和修改确认。人工邮件不消耗 Resend 额度，Web 也不需要阿里邮箱密码或 SMTP 安全密码。人工邮箱尚未开通时，Reply-To 和网站客服入口均保持为空。

**域名所有者先完成第 1 节。** 若现有服务已配置 Resend，不必重新申请或替换其密钥；完成 support 收发验收后，告诉部署维护者公开地址和测试结果，再按第 4 节启用网站入口与事务信回复地址。不要提供阿里云账号密码、邮箱密码或手机验证码。本文是操作指南；实际开通、发布和投递结果应另行留存带日期的验收记录。

## 开通前准备

准备域名 DNS 管理权限、可接收验证码的手机、管理员恢复邮箱，以及安全保存凭据的位置。在 DNS 控制台导出或截图现有记录，特别是网站根域和 `www` 的 A/AAAA、根域 MX、SPF/DKIM/DMARC。邮箱使用同一域名不要求更改网站 IP、Web HTTPS 证书或 Platform 配置。邮箱 MX 不等于网站 A/AAAA。

[阿里免费版](https://help.aliyun.com/zh/document_detail/446177.html)支持个人实名账号申请，当前提供 50 个账号、每邮箱 5 GB；一个阿里云账号最多申请一个免费实例，同一实名身份最多申请两次。完成实名认证后，到期自动延长一年，政策变更以官网公告为准。免费版海外投递使用中国服务器直连，须实测国内外收件箱；开放 API、自动转发和委托邮箱不在免费功能内，本方案先由你在邮箱网页或客户端处理客服信。

阿里企业邮箱用于日常通信，不将其外发配额当作网站验证码额度；阿里官方对[注册验证等系统邮件的说明](https://help.aliyun.com/zh/document_detail/189757.html)与[程序发信建议](https://help.aliyun.com/zh/document_detail/36687.html)也建议使用专门的事务发信服务。本项目继续使用已有 Resend HTTPS 接口，不接入阿里 SMTP 或免费版不支持的开放 API。

[Resend 免费额度](https://resend.com/docs/knowledge-base/account-quotas-and-limits)当前为每天 100 个收件人、每月 3,000 封，按 UTC 日重置，即北京时间 08:00。每次重发、验证、找回或修改确认均消耗额度；一个用户不等于一封邮件。本应用默认全局预算为每天 90 次发送尝试，失败的尝试也计入预算，预留 10 次供验收等用途。配置值仅允许 1～100；另外全局每分钟最多 10 次，同一收件人跨用途等待 60 秒，明确发送失败后至少等待 15 秒再试。Resend 同一团队其他应用或控制台发信共享提供商额度，应用预算不能代替提供商 Usage 检查。

## 1. 开通阿里免费人工邮箱（域名所有者执行）

### 1.1 申请免费实例

1. 登录你自己的阿里云账号并完成实名认证，个人实名可以申请。打开[企业邮箱免费版官方说明](https://help.aliyun.com/zh/document_detail/446177.html)，点击其中的“企业邮箱（免费版）-购买页”。
2. 选择**已有域名**，填入 `agent-communication.online`，购买时长选择 **1 年**。核对产品是“企业邮箱（免费版）”、订单金额为 **0 元**，再同意协议提交。无需重买域名；出现付费金额时返回核对版本。
3. 打开[阿里邮箱控制台](https://alimail.console.aliyun.com/)，在“全部邮箱”找到该免费实例，点击“管理”。保留购买账号，后续重置管理员密码和查看实例都使用它。

申请成功后须在 **7 天内完成域名解析并生效**，逾期会回收实例。不要先申请再长期搁置。

### 1.2 配置收发 DNS

进入该实例的“设置解析”，复制控制台要求的记录到域名当前的**权威 DNS 服务商**。域名在阿里云且使用阿里 DNS 时可按控制台一键添加；提交前核对将修改的记录。域名使用其他 DNS 时手动录入即可，无需迁移 DNS 服务商。记录字段与排查见[阿里添加邮箱解析说明](https://help.aliyun.com/zh/dns/pubz-add-mailbox-resolution)。

| 要配置的内容 | 操作与保留项 |
| --- | --- |
| 域名验证（如控制台要求） | 复制当次 TXT/CNAME 的完整主机名和值 |
| 根域收信 MX | 在 `@` 添加阿里控制台列出的全部目标及优先级；若根域已有其他邮箱，先安排迁移，不混用两家 MX |
| 根域人工发信 SPF | 按阿里要求配置；同一主机名只保留一条 `v=spf1`，已有发件源需要合并 |
| DKIM | 在邮箱后台按实际可用入口启用并取得记录；公钥和 selector 使用该实例给出的值 |
| DMARC | 先查现行策略，按第 3 节核查两个发件域的认证与对齐 |
| 现有网站与 Resend | 保留根域和 `www` 的 A/AAAA、现有网站 CNAME，以及 notify、DKIM、Return-Path 下的 Resend 记录 |

主机名 `@` 表示 `agent-communication.online`；DNS 界面若自动追加域名，填相对名称，避免重复后缀。DNS 生效后回到阿里邮箱控制台重新检测。首期直接使用官方网页登录和客户端服务器地址，`mail`、`imap`、`smtp` 等自定义 CNAME 不必作为客服开通前提。

### 1.3 创建客服账号

1. 在[阿里邮箱控制台](https://alimail.console.aliyun.com/)选择该实例 → 管理 → **重置密码**，给 `postmaster@agent-communication.online` 设置管理员密码。管理员**没有初始密码**，首次登录也从这里设置。[官方重置说明](https://help.aliyun.com/zh/document_detail/36725.html)
2. 打开[阿里邮箱网页登录](https://qiye.aliyun.com/)，用完整 postmaster 地址登录，进入域管后台。进入“组织与用户”中的“员工账号管理／邮箱管理”（按当前界面名称），点击“新建账号”。
3. 姓名填 `Agent Comm 支持`，邮箱前缀填 **`support`**，设置独立密码并按页面要求完成首次修改与恢复方式。保存后确认完整地址为 `support@agent-communication.online`，状态正常。[官方员工账号创建说明](https://help.aliyun.com/zh/document_detail/36734.html)
4. 退出管理员，用 support 登录同一网页。日常客服使用 support，管理员只用于管理；在邮箱设置核对发件显示名、签名和安全手机。

### 1.4 日常收发与可选客户端

先在 `https://qiye.aliyun.com/` 收发即可，邮箱域名无需 ICP 备案。要在 Outlook、Foxmail 或手机邮件 App 使用，再由管理员允许该账号第三方客户端登录和 IMAP/SMTP 权限。用 support 登录网页 → 设置 → 查看更多设置 → 账户与安全 → 账户安全，开启并生成**三方客户端安全密码**，只填到自己的客户端。[安全密码操作说明](https://help.aliyun.com/zh/document_detail/444269.html)

| 客户端字段 | 填写值 |
| --- | --- |
| 账号／用户名 | `support@agent-communication.online`（完整地址） |
| IMAP 收信服务器 | `imap.qiye.aliyun.com`，端口 `993`，SSL/TLS |
| SMTP 发信服务器 | `smtp.qiye.aliyun.com`，端口 `465`，SSL/TLS，开启身份验证 |
| 密码 | 给当前设备生成的三方客户端安全密码 |

以上为[阿里官方客户端参数](https://help.aliyun.com/zh/document_detail/36576.html)。直接使用官方主机名，避免自定义主机名的证书配置。启用安全密码后，客户端不能再填网页登录密码；只用网页时不需要开启这些协议。阿里密码与安全密码不进入本项目 `.env`。

### 1.5 收发验收后交给部署维护者

用你控制的 QQ、163、Gmail、Outlook 地址分别给 support 发信，再从 support 回复。每条路径检查收到、回复、垃圾箱与退信，记录日期和结果；至少验收一个国内和一个海外收件箱，其余未测路径如实注明。某一方向失败时先检查 MX、账号状态、SPF/DKIM/DMARC 和退信说明，仍不通时使用阿里后台在线支持。

完成后给部署维护者以下信息即可：**已开通的公开邮箱地址、通过双向收发的邮箱平台、未通过或未测试的路径**。维护者按第 4 节配置 Reply-To、重建镜像并验收网站客服入口。无需交出阿里云密码、邮箱密码或安全密码；在此之前继续保持两个公开客服配置为空。

## 2. 开通 Resend 事务发信

1. 在 [Resend](https://resend.com/)创建免费账户，进入 Domains 添加 **`notify.agent-communication.online`**，选定控制台可用的发信区域。只启用发信，保持 Receiving/inbound 关闭；Resend 不承担本方案的人工收信。
2. 在该域名的 Records 页面复制每一条记录的类型、完整主机名、值及优先级（如有），到域名 DNS 服务商逐项添加。DNS UI 若自动附加 `agent-communication.online`，按其规则填相对主机名，避免变成重复域名。
3. 特别核对 DKIM 和 Return-Path。Resend 官方说明：2026 年 8 月后创建的域名可能使用 CNAME，较早配置可能是 MX + TXT；必须照当次 Records 页面配置，不能照旧教程硬填某个区域的服务器或分配公钥。CNAME 所在主机名不能同时有其他类型记录；冲突时在 Resend 选择空闲的 Return-Path 子域，不删除网站记录。[官方记录冲突说明](https://resend.com/docs/knowledge-base/how-do-i-avoid-conflicting-with-my-mx-records)
4. 这些发信认证／退信记录应落在控制台显示的 notify、DKIM 或 Return-Path 主机名。**保留根域 `agent-communication.online` 的现有收信 MX**；阿里开通后根域 MX 由阿里负责，不要为了 Resend 验证覆盖它，也不要开启 Resend 根域收信。notify 子域无需配置 Resend inbound MX。
5. 在 Resend 点击 Verify，等待域名全部必需的发信记录显示通过。在域名设置关闭 Open/Click Tracking，保持密码和验证链接为本网站原始链接。[官方域名说明](https://resend.com/docs/dashboard/domains/introduction)
6. 在 API Keys 创建仅允许 Sending、限定该发信域名的密钥；复制一次并保存在服务器受保护的 `.env` 或密钥管理中。不放到浏览器、源码、工单、公开安装包或截图。
7. `accounts@notify.agent-communication.online` 是发件标识，无需在阿里另外开同名收件箱。人工邮箱尚未开通时不设置 `Reply-To`；邮件只用于网站账户确认，不承诺收件人回复能被人工处理。support 通过双向收发验收后，再配置 Reply-To 与网站客服入口。

## 3. DNS 核对与 DMARC

| 用途 | 必须核对的记录 | 值从哪里取得 |
| --- | --- | --- |
| 网站 | 根域和 `www` 原有 A/AAAA、CNAME（若有） | 变更前导出的现有网站配置；保留 |
| 阿里所有权与收信 | 阿里指定验证记录、根域 MX 目标与优先级 | 阿里控制台 |
| 阿里人工发信 | SPF、DKIM（按实际提供功能） | 阿里控制台 |
| Resend 发信 | notify 域名的 DKIM、Return-Path CNAME 或 MX/TXT | Resend Domains → Records |
| DMARC | 根域／notify 的 `_dmarc` TXT，检查策略及 From 对齐 | 当前域名策略与提供商 DMARC 指南 |

先查现有 `_dmarc.agent-communication.online`；没有现行策略时，可从 `p=none` 的监测策略开始，先在 Resend 的真实邮件头里确认（阿里开通后也须核查） SPF、DKIM、DMARC 结果和域名对齐后再评估 `quarantine`／`reject`。不要直接覆盖已有严格策略，也不要编造报告邮箱；需要 `rua` 报告时先准备真实可收信地址。notify 没有自己的 DMARC 时可能继承根域策略，必须一起核查。[Resend DMARC 指南](https://resend.com/docs/dashboard/domains/dmarc)

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

只改运行时 `.env` 后执行 `restart` 不会装入新环境变量；需要重新创建 Web 容器。`NEXT_PUBLIC_SUPPORT_EMAIL` 不属于可动态改变的运行时入口：Docker builder 通过 ARG/ENV 在 `npm run build` 前读取它，Compose 从 `.env` 传入 build args。以后阿里 support 通过验收后，设置 `AUTH_EMAIL_REPLY_TO=support@agent-communication.online` 与 `NEXT_PUBLIC_SUPPORT_EMAIL=support@agent-communication.online`，在构建主机使用相同的公开地址重建 Web 镜像，再部署该镜像并重新创建容器；只改服务器 `.env` 或 recreate 不能让旧镜像新增客服入口。新账户邮件迁移由 Web 启动入口执行，独立源码运行时使用 `npm run db:migrate`；先在一致性数据库备份副本上验证。nginx 文件已挂载时配置检查后 reload；挂载本身变化则按部署指南重建 nginx。禁止打印包含密钥的完整 `docker compose config`。

nginx 对账户写入和凭证登录共用每 IP 每分钟 5 次、突发 5 次、16 KiB 请求体规则；应用还有邮件全局预算及重发节流。token 页面使用 `no-store` 与 `Referrer-Policy: no-referrer`；nginx 访问日志省略 query 和 Referer，避免链接中的 token 进入访问日志。nginx 错误日志在代理故障时仍可能包含完整请求 URL；应限制错误日志访问及保留时间，分享诊断资料前删除 query/token，不复制原始链接。应用只记录安全错误代码；不要额外记录 API 请求体、token、密码、新密码 hash 或完整邮件正文。

## 5. 上线验收与日常检查

使用自己控制的真实邮箱和测试账户，留存日期、部署提交、供应商 Message ID 与去除敏感内容后的结果；不要在报告里保留验证／重置链接、密码或密钥。

1. **发信与可选人工客服**：先验收 QQ、163、Gmail、Outlook 能收到 Resend 事务邮件。人工邮箱未开通时网站不显示客服 mailto、邮件不声明回复会被处理；阿里开通后才追加 support 双向收发验收，并检查 Reply-To 及人工答复地址。
2. **新增账户**：注册后不能在验证前登录；邮件显示正确 From（启用人工邮箱后再核对 Reply-To），验证页面需本人明确确认，完成后能登录。验证链接有效期 24 小时，找回与修改确认链接有效期 30 分钟。重复使用、过期或篡改链接不能再次生效；失效后使用重发入口。
3. **旧账户**：原密码仍能登录，页面显示邮箱尚未验证；补验后才显示已验证。原控制台 URN、连接、配对、联系人和历史仍在，不能通过新建身份代替迁移。
4. **忘记密码**：登录页请求找回，页面不透露邮箱是否存在；收信后自行设置新密码。新密码可登录，旧密码不能登录，另一浏览器中的旧登录会话失效。没有邮件就检查垃圾箱和 Resend 状态，再按节流提示重试。
5. **登录后修改密码**：在账户设置输入旧密码及新密码；收到邮件并明确确认前旧密码仍有效，确认后新密码生效、旧会话失效。输错旧密码不能发送修改确认；别人替你点击不应成为自动确认。
6. **额度与故障**：在隔离环境检查发送预算、重发冷却和代理 429／413；生产不要为了测试耗尽额度。密钥为空、供应商拒绝或额度不足时，界面不能显示“验证已完成”。恢复后用户可重发，不能假装邮件已投递。
7. **日志与浏览器**：检查 nginx 不记录 query／Referer；token 页面响应有 no-store/no-referrer。邮件客户端的链接预览不能自动验证或改变密码，页面必须提交明确确认。

Resend API 接受请求与收件人实际收到是不同状态。初期在 Resend Dashboard 核查 sent/delivered/bounced/complained 及 Usage，并用真实收件箱验收；当前应用未接入回调时，不把控制台投递状态宣称为网页可追踪的送达状态。退信或投诉需人工检查收件地址和原因，不能持续重发。阿里支持邮箱的收到、回复与业务问题解决也应分别记录。

全新部署需要完成第 2～5 节的发信配置、发布与验收；已经配置 Resend 的现有服务保留其账号、notify DNS 和密钥，不因更换人工邮箱重做这些步骤。阿里 support 由域名所有者完成第 1 节后再接入网站；未实测的收发路径仍为**尚未验收**。普通使用步骤见[账户邮箱与客服指南](../users/ACCOUNT_EMAIL.md)。
