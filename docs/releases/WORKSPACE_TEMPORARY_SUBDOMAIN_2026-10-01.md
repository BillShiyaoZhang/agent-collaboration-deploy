# Workspace 临时子域名发布（2026-10-01）

本记录承接[首轮 Web 部署](AMBIENT_WORKSPACE_DEPLOYMENT_2026-10-01.md)。按用户要求，采用显式 `WORKSPACE_GATEWAY_ORIGIN_MODE=same-site-subdomains`；默认 `separate-site` 及完整 PSL 校验保留。门户为 `https://agent-communication.online`，公开控制入口为 `https://gateway.workspace.agent-communication.online`，每节点使用 `https://<24hex>.workspace.agent-communication.online`。没有用同一个 Host 或路径复用不同节点。

## 源码与安全验证

Web 固定提交 `4abb3f34331f2d26be411cf0af60bd3827b26314`。Platform/SDK 仍为 `407ed72b4fdf1c42f25e3afe56e0de9308813c25` / `e2f6fce544f8dcf8523fcacb70184d51c3749a14`；Ambient 保持 `793da83ac263aebe26dc989d5e025d8b7c7c01de`。Gateway 热修代码固定提交 `152dea974f09e5dbca4d0da16867df1be9d3395e`；后续发布记录更新只改文档。

- Gateway 58/58（含精确控制子域两种模式回归）；renderer 13/13。
- 真实 Linux Docker nginx 与合成 TLS：默认模式12组、临时模式14组通过，覆盖无 Cookie 同站请求、缺失/非法/大小写 metadata、Origin、非安全请求、cross-site API 导航、www规范导航，以及 Platform 原签名 Host/头保留、节点隔离头不可被上游放宽。
- Web 定向相关55/55，补边界后31/31；TypeScript、生产构建、原默认模式真实 HTTPS Portal/Gateway smoke 通过。
- Windows 隔离真实 Chrome、保留 example.com 合成域名/loopback TLS、新鲜 SQLite、真实 Credentials 登录及 BFF 通过。验证 __Host/Secure/HttpOnly/Lax/Path 属性、旧 __Secure 会话拒绝、父域 Cookie 注入被浏览器拒绝、门户账户不变、同站 fetch/form/iframe及无 Cookie 请求403、节点 localStorage/Cookie 隔离。Fetch Metadata 来自 TLS 夹具实际收包审计，不使用伪造请求头；秘密、正文和query没有写入审计。自建进程与状态清理完成。

## 真实 DNS-01 证书

现有 DNS wildcard 和控制 A 指向 `8.130.40.38`。用户新增本次 TXT 后，两个权威 DNS 连续两次匹配，Certbot 实际签发成功。SAN 唯一 `*.workspace.agent-communication.online`，有效期 `2026-10-01T10:01:44Z` 至 `2026-12-30T10:01:43Z`；SHA-256 指纹 `F1:D2:40:CC:C7:AA:77:2A:80:17:DC:70:54:FD:EF:DB:94:A0:56:BC:4E:5E:FD:A7:E4:55:5D:5B:FF:9C:53:E4`。私钥匹配、服务器默认 CA 信任与控制域 hostname 验证通过。

独立私有目录 `/root/agent-comm-releases/workspace-samesite-20261001/acme` 保存订单、配置与证据；真实证书复制为同 release 下 `cert-control/`、`cert-node/` 的实际文件，目录0700、私钥0600。原门户证书及 renewal 配置发行前后字节相同；flatten 前后 timer/service hashes和timer状态未变，未操作原续期任务。

**新 wildcard 使用人工 DNS-01，尚未配置自动续期。** 原门户 webroot timer 不会发现独立 ACME 目录。须在到期前使用该目录执行人工 DNS 验证或补受限 DNS API hook，然后同步两个证书目录、renderer、nginx -t/reload；步骤见[运维](../operations/WORKSPACE_GATEWAY.md)。本次验证 TXT 值可移除，保留其他已有 TXT。

## 部署状态及限制

公网在北京时间 **19:20:02** 启用，Gateway 热修在 **19:34:51** 完成切换，**19:35:28–19:35:33** 合成公网端到端验收通过。服务器为 ECS `i-0jleb7de83gsnoa0yuc2` / `8.130.40.38`。此前首轮发布记录的“公网未启用”描述属于18:29时点。

| 组件 | 实际运行镜像 ID | 固定源码 |
| --- | --- | --- |
| Web | `sha256:c974855860cf9ef173bca1cc3df765dc4fbeaa9507f192652c426e1705b9b2dd` | `4abb3f34331f2d26be411cf0af60bd3827b26314` |
| Gateway | `sha256:bb265785e5d1c446f599712d3a06f9e028bae9d22b4d9e7659a653b688b1de8f` | `152dea974f09e5dbca4d0da16867df1be9d3395e` |
| nginx | `sha256:311761cac6bbc23041f3f4302699b0b5d0614e0a4d28b70def415e7bf16050c1` | 原镜像保留 |
| Platform | `sha256:7cafa719c1ddc0ef3e1a5f7ab44cc03277af1811e0aba9d4887fdc4841a2673b` | 原固定版本保留 |

初始 Web/Gateway 镜像归档 `workspace-images.tar.gz` 为243,768,633字节，SHA-256 `1c0524f7a10106aa3504f54fc5eaa270ca004f74139d96d3ff2dea717b5a0028`。独立 Gateway 热修归档 `gw-hotfix.tar.gz` 为52,054,193字节，SHA-256 `d33b08a023cca9e706693561f8c8e74adf3a5ec71cb1f06830ca60c636b0935e`。两者从固定 Git archive 离机构建，Docker gzip CRC、镜像 ID、Linux/amd64、源码 label 全部验证。服务器只删除已加载并核对的传输包，本机完整副本、旧镜像及所有备份保留；清理后根磁盘剩余1,573,720,064字节。

首个获用户明确批准的合成公网探针发现 `gateway.workspace...` 被误判为无效节点子域；该测试账户已删除。热修只让精确配置的 control Host 进入控制路由，未知子域、24hex节点 Host 和门户 Host 仍被拒绝，并补生产443端口回归。热修首次预检查写错状态路径，保护机制实际回滚了旧 Gateway；改为 `/v1/connector/state` 后重新切换通过。两次过程均保留实时数据库，Web/Platform/nginx未重建；保留失败证据，未把回滚当成功验收。

公开只读检查：门户 `/`、`/login`、`/docs/`、`/healthz` 为200；未登录工作区页面307、BFF401；门户同站、缺失metadata和外来/null Origin拒绝403，www规范导航308。控制 `/v1/connector/state` 未认证401，`/health`、`/v1/metrics`、账户路由和根路径404。Web、Registry、MQ、Audit、Gateway数据库 quick_check均为ok，所有容器restart_count为0；Platform沿用2026-09-29的启动时间。原 `.env`、NEXTAUTH_SECRET、v2策略和现有身份文件哈希不变。

## 公网合成验收的实际范围

在独立合成账户及严格回声 Connector 上，经公网可信TLS完成以下检查；客户端为Windows Python3.13.5 / httpx0.28.1 / websockets16.1，未关闭CA或hostname验证。真实浏览器检查属于上述隔离环境：

- 内部生成接入码 → 公开配对 → 内部同账户领取 → 公开本机批准 → 一个认证Tunnel。
- 单次打开票据换取303及host-only `__Host-` Cookie，票据重放401；节点可信TLS、合成前端及注入的节点上下文正确。
- 一次有界HTTP双向回声；一条带节点会话Cookie的WebSocket的上游主动推送、文本及二进制回声。
- 撤销关闭既有WS/Tunnel；旧Cookie401、新WS和Tunnel拒绝；finally只删除绑定的合成账户。

报告 `public-probe-hotfix-report.json` 保存在本机 ignored 构建目录和服务器私有release目录，不含token、ticket、Cookie值、服务密钥或业务正文。19:38:01以只读SQLite、精确合成账户聚合核对：永久tombstone=1，测试节点=1且已revoked，enrollments/sessions/launches均为0；没有新建连接或重复配对。永久tombstone及测试审计按现有保留规则保存。19:36:03的Gateway指标 Tunnel/HTTP/WS=0、queued_bytes=0；control=1、buffer_bytes=32768属于指标请求自身的预约，不能写成全局零。该短时探针不证明多用户容量。

19:36:03完成验收后Gateway在线备份：77,824字节，SHA-256 `8dd8b44db1405064b558ec2668a9c0d729a0757d8428f37be6de77afb4036380`，quick_check=ok，并保存同版私有配置。初始切换前Web在线快照及既有完整Platform/身份备份保留。没有覆盖现网进行恢复演练。

本次公网探针**没有使用真实生产门户账户或运行真实 Ambient、Widget、四条WS、模型调用、Run或完整断线恢复**；真实Chrome门户/BFF、Ambient四WS及Linux资源压力检查属于前述独立隔离环境证据。真实用户全流程仍需在用户自己的设备和授权账户上验收。

## 已部署配置、备份与回退

服务器源码 `/root/agent-collaboration-deploy`；私有发布目录 `/root/agent-comm-releases/workspace-samesite-20261001`。现网原 `.env` 未修改，新workspace参数在独立 `workspace.env`，固定镜像在 `compose-images.yml`。后续管理必须保留两个env文件和完整组合：

```sh
cd /root/agent-collaboration-deploy
docker compose --env-file .env \
  --env-file /root/agent-comm-releases/workspace-samesite-20261001/workspace.env \
  -f docker-compose.yml -f docker-compose.v2.yml \
  -f docker-compose.workspace.yml -f docker-compose.workspace.production.yml \
  -f /root/agent-comm-releases/workspace-samesite-20261001/compose-images.yml \
  config --quiet
```

Gateway应用预约256MiB、容器384MiB，持久卷 `agent-collaboration-deploy_workspace_gateway_data`。专用私网172.30.80.0/29，nginx=.2、Gateway=.3；公开入口经原nginx443，账户API只供内部服务。Gateway热修tag `agent-collaboration-deploy-workspace-gateway:samesite-hotfix-152dea9`，Web tag `agent-collaboration-deploy-web:samesite-4abb3f3`；使用已加载镜像，不能在该小内存服务器重跑Web构建。

备份在release的 `backup/`、`gateway-hotfix-backup/`、`gateway-public-acceptance-backup/`；原完整Platform备份在 `/root/agent-comm-releases/workspace-20261001/backup/`。数据库快照与对应workspace.env均按私有状态保管。Gateway热修回滚只恢复旧镜像override并重建Gateway、检查/reload nginx，实时卷和service secret保留；本次自动回滚实际执行成功。撤销整个功能依 `compose-rollback.yml` 恢复首轮Web/nginx的base+v2组合并停Gateway，保留所有卷；该整体退出步骤本轮未执行。旧数据快照不得覆盖验收后的删除和撤销结果。

临时模式需要现代浏览器并重新登录一次；账户、原 NEXTAUTH_SECRET、配对身份和实时数据保留。从工作区回门户应使用地址栏或书签。恶意同站页面仍可能写父域普通 Cookie 导致 Cookie/请求头额度耗尽，临时模式的可用性隔离弱于独立注册域。256 MiB 应用预算/384 MiB 容器限制目前按单张完整活动页面验收，不宣称多页面容量。独立注册域部署仍是长期方案。
