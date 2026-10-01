# Workspace 临时子域名发布（2026-10-01）

本记录承接[首轮 Web 部署](AMBIENT_WORKSPACE_DEPLOYMENT_2026-10-01.md)。按用户要求，采用显式 `WORKSPACE_GATEWAY_ORIGIN_MODE=same-site-subdomains`；默认 `separate-site` 及完整 PSL 校验保留。门户为 `https://agent-communication.online`，公开控制入口为 `https://gateway.workspace.agent-communication.online`，每节点使用 `https://<24hex>.workspace.agent-communication.online`。没有用同一个 Host 或路径复用不同节点。

## 源码与安全验证

Web 固定提交 `4abb3f34331f2d26be411cf0af60bd3827b26314`。Platform/SDK 仍为 `407ed72b4fdf1c42f25e3afe56e0de9308813c25` / `e2f6fce544f8dcf8523fcacb70184d51c3749a14`；Ambient 保持 `793da83ac263aebe26dc989d5e025d8b7c7c01de`。部署代码及镜像版本在实际切换后补充。

- Gateway 56/56；renderer 13/13。
- 真实 Linux Docker nginx 与合成 TLS：默认模式12组、临时模式14组通过，覆盖无 Cookie 同站请求、缺失/非法/大小写 metadata、Origin、非安全请求、cross-site API 导航、www规范导航，以及 Platform 原签名 Host/头保留、节点隔离头不可被上游放宽。
- Web 定向相关55/55，补边界后31/31；TypeScript、生产构建、原默认模式真实 HTTPS Portal/Gateway smoke 通过。
- Windows 隔离真实 Chrome、保留 example.com 合成域名/loopback TLS、新鲜 SQLite、真实 Credentials 登录及 BFF 通过。验证 __Host/Secure/HttpOnly/Lax/Path 属性、旧 __Secure 会话拒绝、父域 Cookie 注入被浏览器拒绝、门户账户不变、同站 fetch/form/iframe及无 Cookie 请求403、节点 localStorage/Cookie 隔离。Fetch Metadata 来自 TLS 夹具实际收包审计，不使用伪造请求头；秘密、正文和query没有写入审计。自建进程与状态清理完成。

## 真实 DNS-01 证书

现有 DNS wildcard 和控制 A 指向 `8.130.40.38`。用户新增本次 TXT 后，两个权威 DNS 连续两次匹配，Certbot 实际签发成功。SAN 唯一 `*.workspace.agent-communication.online`，有效期 `2026-10-01T10:01:44Z` 至 `2026-12-30T10:01:43Z`；SHA-256 指纹 `F1:D2:40:CC:C7:AA:77:2A:80:17:DC:70:54:FD:EF:DB:94:A0:56:BC:4E:5E:FD:A7:E4:55:5D:5B:FF:9C:53:E4`。私钥匹配、服务器默认 CA 信任与控制域 hostname 验证通过。

独立私有目录 `/root/agent-comm-releases/workspace-samesite-20261001/acme` 保存订单、配置与证据；真实证书复制为同 release 下 `cert-control/`、`cert-node/` 的实际文件，目录0700、私钥0600。原门户证书及 renewal 配置发行前后字节相同；flatten 前后 timer/service hashes和timer状态未变，未操作原续期任务。

**新 wildcard 使用人工 DNS-01，尚未配置自动续期。** 原门户 webroot timer 不会发现独立 ACME 目录。须在到期前使用该目录执行人工 DNS 验证或补受限 DNS API hook，然后同步两个证书目录、renderer、nginx -t/reload；步骤见[运维](../operations/WORKSPACE_GATEWAY.md)。本次验证 TXT 值可移除，保留其他已有 TXT。

## 部署状态及限制

证书和本地安全检查已完成；实际镜像构建、切换与公网结果将在执行后补入本节。此前首轮发布记录的“公网未启用”描述属于18:29时点。

临时模式需要现代浏览器并重新登录一次；账户、原 NEXTAUTH_SECRET、配对身份和实时数据保留。从工作区回门户应使用地址栏或书签。恶意同站页面仍可能写父域普通 Cookie 导致 Cookie/请求头额度耗尽，临时模式的可用性隔离弱于独立注册域。256 MiB 应用预算/384 MiB 容器限制目前按单张完整活动页面验收，不宣称多页面容量。独立注册域部署仍是长期方案。
