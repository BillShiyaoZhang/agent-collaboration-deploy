# 部署与升级

从部署仓库根目录运行以下命令。Compose 组合运行 nginx、Web 和 Platform；Hermes 与 helper 在用户 agent 所在设备运行，见 [Hermes 接入](HERMES.md)。

## 通过 Workbench CLI 连接

已配置凭证的维护者可按[阿里云官方文档](https://help.aliyun.com/zh/ecs/user-guide/connect-to-an-instance-through-workbench-cli/)使用 `workbench exec -i INSTANCE_ID --command 'hostname && docker ps' --output json` 检查实例。`exec` 每次是独立 shell，关联命令需在同一次调用中切换目录；检查返回的 `exit_code`。无需输出或复制本机 Workbench 凭证。

发布产物用 `workbench upload LOCAL_FILE REMOTE_PATH -i INSTANCE_ID` 上传到新的服务器发布目录，校验 SHA-256 后再使用。长时间部署在服务器保存脚本、日志、PID 和检查点，断开 CLI 后仍能检查实际结果。连接成功本身不表示部署完成；保留以下备份和验证流程。

## 组件与配置位置

| 项目 | 仓库位置 / 容器入口 |
| --- | --- |
| Compose | [`docker-compose.yml`](../../docker-compose.yml) |
| nginx | [`deploy/nginx/nginx.conf`](../../deploy/nginx/nginx.conf) 和 [`docs-source.conf`](../../deploy/nginx/docs-source.conf) → `/etc/nginx/` |
| Platform 配置 | [`deploy/platform/config.yaml`](../../deploy/platform/config.yaml) → `/etc/platform/config.yaml` |
| Web 公共页面与工作台 | [`agent-collaboration-web/src/app/`](../../agent-collaboration-web/src/app/page.tsx) → 同一个 Next.js Web 镜像 |
| 官网文档原文 | 四仓各自的 `docs/` → nginx 的 `/srv/docs/{deploy,web,platform,sdk}` 与 Web 的 `/app/docs-source/{deploy,web,platform,sdk}`，均只读挂载原文件 |
| 公开安装包 | 根目录 `downloads/` → `/srv/downloads`，由发布流程准备 |
| ACME 验证 | 根目录 `acme-challenge/` → `/var/www/certbot` |
| 持久数据 | Compose 的 `platform_data`、`web_data` 命名卷 |

现有配置使用 `agent-communication.online`、`www.agent-communication.online` 与 `8.130.40.38`。部署到其他服务器时，同步修改 nginx 的域名/证书路径、Platform 的外部地址及 `.env` 中的 `NEXTAUTH_URL`。

nginx 将 `/`、`/docs/`、登录与工作台交给同一个 Next.js Web 应用；`/docs/source/{deploy,web,platform,sdk}/...` 仍从对应仓库的 `docs/` 直接读取 Markdown。Web 应用也提供同路径的只读入口，供不经过 nginx 的本地运行使用。源文件 URL 保留仓库名和相对路径，不需同步第二份文档；两个入口都只允许现行的角色、架构、运维和指南 Markdown，发布、验证、测试历史记录继续在仓库中查阅。[Platform API 参考](https://agent-communication.online/docs/?path=platform/guides/API.md)由同一阅读器打开；旧 `/docs/api/` 和 `/guide/` 地址重定向到新入口。`/healthz`、`/api/v1/`、`/api/v2/`、`/admin` 交给 Platform，其余路径包括 `/api/auth/` 交给 Web。修改公共页面需重建 Web 镜像；只修改已挂载的公开 Markdown 原文无需重建应用。完整文档入口需要本 Compose 中四仓的只读文档挂载，详见 [Web 部署说明](../../agent-collaboration-web/docs/operations/DEPLOYMENT.md)。

## 准备源码与环境

服务器需安装 Docker 和 Compose v2；镜像构建使用本仓库内的固定子模块版本。

```bash
git clone --recurse-submodules https://github.com/BillShiyaoZhang/agent-collaboration-deploy.git
cd agent-collaboration-deploy
```

已有克隆先补齐两级子模块：

```bash
git submodule sync --recursive
git submodule update --init --recursive
```

在根目录创建 `.env`，填入独立生成的值：

```dotenv
NEXTAUTH_SECRET=<openssl rand -base64 32 的输出>
PLATFORM_ADMIN_TOKEN=<openssl rand -hex 16 的输出>
NEXTAUTH_URL=https://agent-communication.online
```

`NEXTAUTH_SECRET` 同时参与账户内容静态加密，升级时保留原值，备份时与数据库一起妥善保存。它与 `PLATFORM_ADMIN_TOKEN` 都不进入源码或公开安装包。

Compose 在上述两个密钥或 `NEXTAUTH_URL` 缺失、为空时拒绝启动，不再回退到 HTTP 公网地址。Web 镜像通过 HTTPS 软件源及锁文件安装依赖，启动入口仅以 root 修正 `/app/data` 旧卷属主，随后以 UID/GID 1001 执行迁移和应用；不会修改既有加密密钥。

当前 Compose 的 Web `DATABASE_URL` 使用 `connection_limit=1`，使单个 Web 进程的 Prisma 查询排队等待一条 SQLite 连接。读写都经过该连接；这是有超时的进程内缓冲，不是持久任务队列，也不协调多个 Web 副本。升级后监看控制轮询分段耗时、页面读取时延、SQLite Code 5 与连接池等待超时 `P2024`；多副本或持续高写入负载应改用适合并发写入的服务型数据库。变更和验收记录见 [Web SQLite 缓冲发布记录](../releases/WEB_SQLITE_BUFFER_RELEASE_2026-09-23.md)。

nginx 对注册与凭证登录共享每客户端每分钟 5 次、突发 5 次的限制，超额返回 429；认证请求体上限 16 KiB，`/api/v2/` 上限 2 MiB，其余请求上限 1 MiB。它覆盖传入的 `X-Real-IP`、`X-Forwarded-For`。Platform 的 `api.trusted_proxy_cidrs` 仅允许受信任代理提供客户端地址，组合配置兼容 Docker 默认 `172.16.0.0/12` 地址池。生产应收窄到实际 nginx 地址或专用子网，不向公网发布 8080，也不将不受信任容器加入该网络；自定义地址池必须相应调整配置。

账户密码开始使用 scrypt，旧 bcrypt 哈希在成功登录时升级。升级后的数据库不能直接交给仅支持 bcrypt 的旧镜像，否则这些账户无法登录；回滚版本必须包含新版密码验证器。历史 bcrypt 丢弃的 72 字节以后内容无法从旧哈希恢复，尚未登录的旧账户保留原验证行为。密码输入上限为 1024 UTF-8 字节。完整修复和验证范围见 [安全检查记录](../verification/SECURITY_REVIEW_2026-09-16.md)。

## DNS 与首次证书

现有服务的 DNS 配置为：

| 类型 | 名称 | 地址 |
| --- | --- | --- |
| A | `agent-communication.online` | `8.130.40.38` |
| A | `www.agent-communication.online` | `8.130.40.38` |

先用 `dig agent-communication.online +short` 核对解析，再申请证书。以下为 Debian/Ubuntu 系服务器示例；使用其他系统时安装对应 Certbot 包。

```bash
sudo apt update
sudo apt install -y certbot
# 已有 nginx 占用 80 端口时，先在部署根目录停止它。
docker compose stop nginx
sudo certbot certonly --standalone \
  -d agent-communication.online \
  -d www.agent-communication.online \
  --email your-email@example.com \
  --agree-tos --non-interactive
```

证书位于 `/etc/letsencrypt/live/agent-communication.online/`，Compose 只读挂载 `/etc/letsencrypt`。首次创建容器按下一节启动；已有服务申请证书后可执行 `docker compose start nginx`。

## 启动与验证

以下基础 Compose 命令用于尚未启用 v2 的全新自部署。已启用签名策略的现网必须使用[下方升级命令](#升级备份与回退)同时传入 `docker-compose.v2.yml`，否则会丢失 v2 挂载和配置。

```bash
docker compose config --quiet
docker compose up --build -d
docker compose ps
docker exec agent-nginx nginx -t
docker exec agent-nginx nginx -s reload
curl --fail https://agent-communication.online/healthz
curl --fail https://agent-communication.online/docs/
curl --fail https://agent-communication.online/docs/source/deploy/users/README.md
curl --fail https://agent-communication.online/docs/source/sdk/README.md
curl --fail https://agent-communication.online/docs/source/platform/guides/API.md
curl --fail --location 'https://agent-communication.online/docs/api/'
docker compose logs --tail=100
```

确认 [官网](https://agent-communication.online)、[文档入口](https://agent-communication.online/docs/)、[Platform API 参考](https://agent-communication.online/docs/?path=platform/guides/API.md)、[登录](https://agent-communication.online/login)、[工作台](https://agent-communication.online/dashboard) 和本次应发布的下载文件正常。`/docs/source/deploy/releases/README.md` 应返回 404，确保历史记录未进入官网文档路由；旧 `/guide/` 和 `/docs/api/` 链接应跳转至新入口。未登录访问私有工作台 API 应被拒绝。首次部署没有现成 `downloads/` 产物时，按 [发布工具说明](../../tools/release/README.md) 准备。

| 端口 | 服务 | 用途 |
| --- | --- | --- |
| 80 | nginx | ACME 验证，其余 HTTP 请求跳转 HTTPS |
| 443 | nginx | 官网、工作台和公共 API |
| 45041 TCP / UDP | Platform | 公共 libp2p 网络 |
| 3000 | Web | Compose 内部服务端口 |
| 8080 | Platform | Compose 内部 HTTP API |

## 升级、备份与回退

现网签名策略为 `compliance`、epoch 3 长期策略、`allow_v1=false`，Relay 禁用；策略摘要和技术到期时间见[迁移指南](V2_MIGRATION.md)与[长期策略记录](../releases/V2_PERSISTENT_POLICY_2026-09-25.md)。签名字段不变时无需例行续签；模式、密钥、平台身份或其他签名字段变化时，用离线根签发更高 epoch，并先处理旧策略下未读或待发的 v2 消息。生产升级须保留 [v2 Compose 覆盖配置](V2_MIGRATION.md#compose-v2-覆盖文件)和原有身份、数据库及在线密钥。普通服务升级不自动改变用户信息披露范围；策略变化必须重新告知并取得两端各自的本机授权，Web 账户另行确认。

Platform 管理后台的日常操作、权限和结果边界见[管理后台指南](PLATFORM_ADMIN.md)。管理台修改的存储、转发策略、历史保留天数，以及确认后保存的 Registry、MQ、Relay 运行参数均保存在 `platform_data` 卷中的 `/data/admin-policies.yaml`；升级与备份时须包含此文件。

升级前保留一致的 Web SQLite 备份、Platform 数据与身份、`.env`、配置和当前镜像，并记录回滚标识。主配置 `deploy/platform/config.yaml` 仍以只读方式挂载，首次升级没有覆盖文件时沿用主配置值。Web 启动入口幂等应用 [`prisma/remote-console.sql`](../../agent-collaboration-web/prisma/remote-console.sql)，为远程控制与账户工作台增加所需结构；迁移保留历史业务表，不以清库方式升级。

在干净的服务器源码检出中，待部署仓库固定新版本后运行。下面示例针对**已启用签名 v2 的现网**；无 v2 配置的首次自部署仍使用前述基础 Compose 命令，不能在现网升级时遗漏覆盖文件：

```bash
git pull --ff-only
git submodule sync --recursive
git submodule update --init --recursive
docker compose -f docker-compose.yml -f docker-compose.v2.yml config --quiet
docker compose -f docker-compose.yml -f docker-compose.v2.yml up --build -d
docker exec agent-nginx nginx -t
docker exec agent-nginx nginx -s reload
```

上述在线构建命令需要足够的内存。现有阿里云 ECS 仅有 1.8 GiB 内存；2026-09-25 的 Web `next build` 即使已有 swap，仍触发全局 OOM，杀掉 Docker 守护进程并停止所有线上容器。该主机升级 Web 时应在另一台 Linux/amd64 Docker 主机（本机 Docker Desktop 的 Linux 引擎也可）从**固定 Web 子模块提交**构建生产镜像，再 `docker save`、压缩并校验 SHA-256 后传到服务器。服务器先对 Web SQLite 做在线备份并保留旧镜像标签，校验上传文件，再 `docker load`、核对镜像 ID/架构/源码修订，将其标记为 Compose 使用的 `agent-collaboration-deploy-web:latest`，最后执行带 v2 覆盖文件的 `docker compose up -d --pull never --no-deps --no-build --force-recreate web`。立即对 nginx 执行配置检查与 reload，再验证公网、策略、Web 镜像和四库完整性。镜像加载同样需要磁盘与 swap 余量；本次实际回退和成功切换见 [v0.8.0 发布记录](../releases/V2_CLIENT_RELEASE_2026-09-24.md)。

nginx 使用静态解析的 Compose 上游地址。Platform 或 Web 容器重建后，旧上游 IP 可能仍留在运行中的 nginx 配置；先执行 `nginx -t` 并 reload，再从公网检查 HTTPS 健康和业务 API。2026-09-24 首次 v2 切换就因遗漏 reload 导致健康检查失败而自动回退；补上 reload 后重新切换成功。仅重载 nginx 不会重新装入新增的 Compose 挂载，挂载变化仍须按下文重建 nginx 容器。

四仓文档以只读方式挂载给 nginx 和 Web。若发布 shell 使用 `umask 077`，新检出的目录可能是 `0700`、Markdown 可能是 `0600`；nginx 用户或 Web 的 `nextjs` 用户会无法读取，文档原文可能返回 403 或 404。更新源码后，仅修复这四个公开文档目录树的目录遍历和 Markdown 读取权限，再以实际容器用户打开文件并验证 HTTP 路由：

```bash
find docs agent-collaboration-web/docs agent-comm-platform/docs agent-comm-platform/agent-comm/docs \
  -type d -exec chmod a+rx {} +
find docs agent-collaboration-web/docs agent-comm-platform/docs agent-comm-platform/agent-comm/docs \
  -type f -name '*.md' -exec chmod a+r {} +
docker exec --user nginx agent-nginx sh -c 'cat /srv/docs/deploy/users/README.md /srv/docs/web/README.md /srv/docs/platform/guides/API.md /srv/docs/sdk/README.md >/dev/null'
docker exec --user nextjs agent-web sh -c 'cat /app/docs-source/deploy/users/README.md /app/docs-source/web/README.md /app/docs-source/platform/guides/API.md /app/docs-source/sdk/README.md >/dev/null'
curl -fsS https://agent-communication.online/docs/source/deploy/operations/PLATFORM_ADMIN.md >/dev/null
curl -fsS https://agent-communication.online/docs/source/platform/guides/API.md >/dev/null
```

使用记录的子模块提交；`git submodule update --remote` 会选择另一组源码。现有服务器曾采用按清单部署的源码快照；若工作树有未提交改动，先核对 [对应发布记录](../releases/README.md) 中的清单、镜像和备份，不能直接重置工作树。

修改 nginx 的 Compose 挂载时必须重建 nginx 容器；仅执行 `nginx -s reload` 不会装入新挂载。若组合启动没有重建 nginx，执行 `docker compose up -d --no-deps --force-recreate nginx`，再运行 `docker exec agent-nginx nginx -t`。

若采用文件清单而非完整仓库部署，需同时复制 `deploy/` 下的 nginx 配置及 `docs-source.conf`、Platform 配置、与之匹配的 Compose 文件，以及四仓在对应固定提交的 `docs/` 原文件；启动前检查容器挂载路径。公开目录不能用缺失的目录挂载占位，否则官网文档会静默变成空目录。

升级后复查健康、身份、数据完整性、同步启动和登录。回退应用时恢复对应源码/配置及旧镜像，保留实时数据库；旧备份覆盖实时库会丢失升级后的用户写入和同步结果。具体镜像、备份目录和历史回退步骤见各次发布记录。

本次官网与文档页面迁入 Next.js 后，回滚到迁移前版本必须一起恢复旧 Web 镜像、旧 nginx 配置，以及旧 Compose 中 `agent-collaboration-web/site` 到 `/srv/site` 的只读挂载和对应 HTML 文件，再重建 Web 与 nginx 容器。只回退 Web 镜像会让新 nginx 把 `/`、`/docs/` 交给不含这些公开页面的旧应用；只 reload nginx 也不会恢复已移除的 `/srv/site` 挂载。回滚仍保留原有数据卷、`NEXTAUTH_SECRET` 与 v2 覆盖配置，随后检查首页、文档、登录、工作台和现有身份。

## 证书续期

现有服务器在 2026-09-14 发布时改为 Certbot `webroot` 续期：根目录 `acme-challenge/` 对 nginx 只读挂载，`/.well-known/acme-challenge/` 不跳转。新服务器首次通过 standalone 取得证书后，需要配置同样的 webroot 续期；仅创建挂载不会自动更改 Certbot renewal 配置。

现有服务器使用 `certbot-renew.timer`，其他系统的 timer 名称可能不同：

```bash
sudo systemctl enable --now certbot-renew.timer
sudo systemctl status certbot-renew.timer
```

成功续期后，部署 hook `/etc/letsencrypt/renewal-hooks/deploy/agent-comm-nginx.sh` 执行：

```bash
docker exec agent-nginx nginx -t
docker exec agent-nginx nginx -s reload
```

新服务器需安装该 hook、配置正确的 webroot 并完成续期演练。现有服务器的配置来源与初次续期证据见 [早期发布记录](../releases/EARLY_ACCESS_RELEASE_2026-09-14.md#https-续期修复)。
