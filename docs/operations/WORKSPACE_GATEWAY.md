# Ambient Workspace Gateway 运维

适用于 `main` 中的可选 Workspace 组件。Ambient 侧已按[交接契约](../developers/AMBIENT_WORKSPACE_HANDOFF_2026-10-01.md)完成适配，独立结果见[验收记录](../verification/AMBIENT_WORKSPACE_ACCEPTANCE_2026-10-01.md)。当前代码支持独立注册域名及显式临时子域名两种模式；是否已启用以[发布记录](../releases/AMBIENT_WORKSPACE_DEPLOYMENT_2026-10-01.md)为准。原平台、Web 身份、数据库、NEXTAUTH_SECRET 与 v2 签名策略均须保留。只更新源码不能声称生产已启用。

## 域名、证书与配置

门户继续使用现有 HTTPS `NEXTAUTH_URL`。`WORKSPACE_GATEWAY_ORIGIN_MODE` 仅接受以下两个值，未知值启动或渲染失败：

- `separate-site`（默认）：控制 Host 与节点 wildcard 位于同一可注册域名，且与门户使用不同可注册域名，例如门户 `portal.example.com`、控制 `connect.example-workspace.com`、节点 `*.nodes.example-workspace.com`。完整 ICANN/PRIVATE PSL 校验继续生效。
- `same-site-subdomains`（显式临时选项）：三者共享可注册域名；门户 Host、控制 Host、每个节点 Host 仍须不同，门户必须位于节点命名空间之外。例如门户 `agent-communication.online`、控制 `gateway.workspace.agent-communication.online`、节点 `*.workspace.agent-communication.online`。控制名称不得匹配24位十六进制节点名称。禁止复用同一个 Host 或路径承载不同工作区。

临时模式必须同时部署新 Web 和 renderer 生成的门户 guard，不能单独放宽域名检查。Web 的六类 NextAuth Cookie 全部使用 `__Host-`、Secure、HttpOnly、SameSite=Lax、Path=/，没有 Domain；middleware 与认证库读取同一会话名，拒绝旧 Cookie，已有浏览器需要重新登录一次。账户、原 `NEXTAUTH_SECRET` 和配对身份保留。

门户 Web、认证和 `/admin` 在 public 路由之前拒绝 `Sec-Fetch-Site: same-site`、外来或 null Origin、带 Cookie 但缺失/非法 Fetch Metadata，以及带 Cookie 的非 GET/HEAD 请求缺少精确门户 Origin。外站仅允许页面 GET/HEAD 顶层导航，API、嵌入和子资源不享有该例外。cookie-free 原生 CLI 的签名/Bearer 请求保留；Platform `/api/v1/`、`/api/v2/` 与精确 `/healthz` 保持原行为。门户和节点设置 Origin-Agent-Cluster/COOP；无跨域凭据 CORS。www 页面正常导航重定向到规范门户 Host。

此选项要求支持 Fetch Metadata 与 `__Host-` 的现代浏览器。从工作区页面直接点击门户链接会被拒绝，请使用地址栏或书签回门户。同站恶意页面仍可能写入大量父域 Cookie，造成 Cookie 额度/请求头耗尽和重新登录；临时模式的可用性隔离弱于独立注册域名。稳定运行后切换 `separate-site`。替换示例域名，不把占位值当发布配置。

将[变量模板](../../deploy/workspace.env.example)合入服务器原私有 .env，生成独立 WORKSPACE_GATEWAY_SECRET（例如 openssl rand -hex 32）。控制和节点 DNS 指向入口服务器。申请包含控制 Host 与 *.节点域名的可信 TLS 证书；wildcard 使用 DNS-01。DNS服务凭据、私钥和真实 .env 不进入源码。

| 变量 | 用途 |
| --- | --- |
| WORKSPACE_GATEWAY_ORIGIN_MODE | 默认 separate-site；显式临时值 same-site-subdomains |
| WORKSPACE_GATEWAY_DOMAIN | 节点基域，不带 scheme 或路径 |
| WORKSPACE_GATEWAY_CONTROL_HOST | 精确公开 Connector Host |
| WORKSPACE_GATEWAY_PUBLIC_URL | 上述控制 Host 的 HTTPS origin，Web返回给用户 |
| WORKSPACE_NGINX_CONFIG_DIR | renderer 输出目录，绝对路径 |
| WORKSPACE_CONTROL_CERT_DIR、WORKSPACE_NODE_CERT_DIR | 分别挂载控制/节点 fullchain.pem 与 privkey.pem |
| WORKSPACE_INGRESS_SUBNET | 专用代理网络，默认172.30.80.0/29；不能与现有网络重叠 |
| WORKSPACE_INGRESS_NGINX_IP、WORKSPACE_INGRESS_GATEWAY_IP | 同网络静态地址，默认.2/.3 |

Gateway 的内部 URL 只供 BFF；不得作为公开地址展示。Compose 显式设置 WORKSPACE_GATEWAY_SERVICE_HOST=workspace-gateway:8090，只允许该 Host 上带服务 Bearer 的账户/指标路由；Connector 仍只接受公开 CONTROL_HOST。生产 overlay 设 WORKSPACE_GATEWAY_PORTAL_ORIGIN=NEXTAUTH_URL、HTTPS，并仅信任专网 nginx 地址/32。两个证书目录使用实际文件；LE live 目录的外部 symlink 会超出挂载范围，先复制到权限受限的独立目录。不得提交这些目录。

```sh
python3 tools/workspace/render_ingress.py --env-file .env
# 自定义 OpenSSL 用 --openssl /path/to/openssl；--output 必须与 WORKSPACE_NGINX_CONFIG_DIR 相同
docker compose -f docker-compose.yml -f docker-compose.v2.yml \
  -f docker-compose.workspace.yml -f docker-compose.workspace.production.yml config --quiet
```

renderer 验证域名、私网、证书 SAN、密钥匹配和至少24小时剩余有效期，不能证明 DNS 正确或证书链受浏览器信任。检查输出后先在测试环境验收。没有 v2 的全新自部署省略 v2 overlay；现网不能省略。

生产 nginx 沿用原80/443入口，新增可选 include。控制 Host 只允许 pairings/state/approve/revoke/tunnel，内网账户接口不发布；节点只接受24位十六进制node_id。代理覆盖身份头，限正文时间和并发，禁含票据的访问/错误日志。控制及节点明文HTTP拒绝，现有门户ACME规则保留。生产入口每IP配对5次/分钟、state120次/分钟、其他控制动作30次/分钟，分别有burst；每IP32、整体240并发，上游应用预算还会更早拒绝。429带Retry-After:60，多节点共用NAT地址时也共用入口额度。日志关闭使故障诊断受限，使用不含票据或正文的内部指标及状态。

## 构建、发布与回退

从固定父仓库与子模块版本在足够内存的 Linux/amd64 主机离线构建 Web/Gateway 镜像，保存镜像ID、源码修订和SHA-256；不要在现有小内存ECS执行Web next build。依[部署指南](DEPLOYMENT.md)备份现有Web/Platform及身份，上传镜像并校验，再按完整overlay组合发布。带日期的发布记录说明实际启用状态。

默认应用预约预算为 256 MiB（`WORKSPACE_GATEWAY_BUFFER_BYTES=268435456`），容器上限仍为 384 MiB。Ambient 完整页面同时使用三条聊天 WS 和一条 Widget WS；此前 128 MiB 配置会拒绝第三条 WS。2026-10-01 的 Ambient 隔离验收在 256 MiB 下完成一个 Tunnel、四条浏览器 WS 与页面加载，Windows Gateway 工作集峰值约 61 MB。预约预算不是 RSS 上限，这份短时验收也不证明 Linux 满队列或多节点容量；上线监看实际 RSS、OOM、预约及背压，超额拒绝不得靠清空节点身份恢复。

```sh
docker compose -f docker-compose.yml -f docker-compose.v2.yml \
  -f docker-compose.workspace.yml -f docker-compose.workspace.production.yml \
  up -d --pull never --no-build workspace-gateway web nginx
docker exec agent-nginx nginx -t
docker exec agent-nginx nginx -s reload
```

新增挂载必须重建 nginx；reload 不会装入新挂载。容器重建后 nginx 上游地址可能变化，配置检查及 reload 必须执行。不得使用 down -v，也不重新初始化身份/密钥。Gateway单实例及SQLite持久卷不能同时启动两个共享路由实例。

退出本功能时移除 workspace overlays/可选配置挂载，恢复对应Web/Compose/nginx镜像及配置，保留原数据卷；旧Ambient可恢复原连接但匿名配对不能绕过新规则。应用回退保留实时数据库，不用旧快照覆盖新增写入。旧版本若不认识接入码/配额迁移，不作为无条件安全回滚版本；应选择已验证的兼容版本，必要时停止新接入后修复前进。

## 备份与删除状态

备份授权数据库必须包含 nodes、enrollments、sessions、launches、audit、deleted_accounts 及服务配置/秘密。不能只复制正在WAL模式运行的主SQLite文件。使用[在线备份工具](../../tools/maintenance/backup_workspace_gateway.py)，它通过SQLite backup API生成新文件、检查完整性、不覆盖已有备份：

```sh
python3 tools/maintenance/backup_workspace_gateway.py \
  --database /absolute/path/to/workspace.sqlite3 \
  --output /private/backups/workspace-20261001T120000Z.sqlite3
```

路径需对应实际持久卷，管理员可在安全环境执行；不把备份文件放公开下载目录。Linux输出0600，Windows需额外核对目录ACL。备份包含身份摘要和账户元数据，按私有状态保管并制定保留期。恢复前停止Gateway，核对数据库完整性和服务秘密；必须保留备份之后已受理的删除/撤销结果，不能因恢复让账户和许可复活。不覆盖现网数据来进行备份演练。

旧paired的token/grant/期限保留，旧pending/claimed迁移为expired。节点/审计会清理，deleted_accounts永久保留。审计不等于业务完成结果；业务正文不持久化不表示入口运营者看不到TLS明文。

## 验证与维护

```sh
python3 -m unittest discover -s tools/workspace/tests -v
python3 tools/workspace/check_ingress.py
python3 -m unittest discover -s tools/maintenance/tests -p test_backup_workspace_gateway.py -v
python3 tools/maintenance/check_structure.py
```

Ingress测试用合成证书与隔离Docker服务，不替代真实公网TLS。实际环境/结果见[验证记录](../verification/WORKSPACE_GATEWAY_CLOUD_2026-10-01.md)。发布后须真实验证登录与新接入、原paired身份、双向HTTP/WS、撤销/到期/删除关闭连接、无效Host、账户API不公开、代理头覆盖、资源拒绝与恢复，以及原Agent Comm/v2功能仍可用。

证书续期使用原DNS-01方法。人工 DNS hook 的证书不能靠原 webroot timer 自动续期；须在到期前重新完成 DNS-01，或配置受限 DNS API hook。成功续期后安全复制实际证书和私钥到挂载目录，重新运行renderer核对，然后nginx -t/reload；已有只读目录挂载无需为文件更新重建容器。复制与reload之间避免中间配置生效，私钥保持受限权限。新增证书续期不能假设门户原webroot续期自动覆盖wildcard。
