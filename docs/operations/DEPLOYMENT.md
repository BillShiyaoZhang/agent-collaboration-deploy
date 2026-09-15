# 部署与升级

从部署仓库根目录运行以下命令。Compose 组合运行 nginx、Web 和 Platform；Hermes 与 helper 在用户 agent 所在设备运行，见 [Hermes 接入](HERMES.md)。

## 组件与配置位置

| 项目 | 仓库位置 / 容器入口 |
| --- | --- |
| Compose | [`docker-compose.yml`](../../docker-compose.yml) |
| nginx | [`deploy/nginx/nginx.conf`](../../deploy/nginx/nginx.conf) → `/etc/nginx/nginx.conf` |
| Platform 配置 | [`deploy/platform/config.yaml`](../../deploy/platform/config.yaml) → `/etc/platform/config.yaml` |
| 官网 | [`agent-collaboration-web/site/`](../../agent-collaboration-web/site/README.md) → `/srv/site` |
| 公开安装包 | 根目录 `downloads/` → `/srv/downloads`，由发布流程准备 |
| ACME 验证 | 根目录 `acme-challenge/` → `/var/www/certbot` |
| 持久数据 | Compose 的 `platform_data`、`web_data` 命名卷 |

现有配置使用 `agent-communication.online`、`www.agent-communication.online` 与 `8.130.40.38`。部署到其他服务器时，同步修改 nginx 的域名/证书路径、Platform 的外部地址及 `.env` 中的 `NEXTAUTH_URL`。

nginx 将 `/` 交给官网静态目录，将 `/healthz`、`/api/v1/`、`/admin`、`/docs` 交给 Platform；其余路径，包括 `/api/auth/`，交给 Web。只修改已挂载官网的静态内容时无需重建应用，详见 [官网维护说明](../../agent-collaboration-web/site/README.md)。

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

```bash
docker compose config --quiet
docker compose up --build -d
docker compose ps
docker exec agent-nginx nginx -t
curl --fail https://agent-communication.online/healthz
docker compose logs --tail=100
```

确认 [官网](https://agent-communication.online)、[登录](https://agent-communication.online/login)、[工作台](https://agent-communication.online/dashboard) 和本次应发布的下载文件正常。未登录访问私有工作台 API 应被拒绝。首次部署没有现成 `downloads/` 产物时，按 [发布工具说明](../../tools/release/README.md) 准备。

| 端口 | 服务 | 用途 |
| --- | --- | --- |
| 80 | nginx | ACME 验证，其余 HTTP 请求跳转 HTTPS |
| 443 | nginx | 官网、工作台和公共 API |
| 45041 TCP / UDP | Platform | 公共 libp2p 网络 |
| 3000 | Web | Compose 内部服务端口 |
| 8080 | Platform | Compose 内部 HTTP API |

## 升级、备份与回退

升级前保留一致的 Web SQLite 备份、Platform 数据与身份、`.env`、配置和当前镜像，并记录回滚标识。Web 启动入口幂等应用 [`prisma/remote-console.sql`](../../agent-collaboration-web/prisma/remote-console.sql)，为远程控制与账户工作台增加所需结构；迁移保留历史业务表，不以清库方式升级。

在干净的服务器源码检出中，待部署仓库固定新版本后运行：

```bash
git pull --ff-only
git submodule sync --recursive
git submodule update --init --recursive
docker compose config --quiet
docker compose up --build -d
docker exec agent-nginx nginx -t
docker exec agent-nginx nginx -s reload
```

使用记录的子模块提交；`git submodule update --remote` 会选择另一组源码。现有服务器曾采用按清单部署的源码快照；若工作树有未提交改动，先核对 [对应发布记录](../releases/README.md) 中的清单、镜像和备份，不能直接重置工作树。

本次目录调整将根目录 `nginx.conf`、`config.yaml` 移到 `deploy/` 下，容器内部路径及数据卷不变。采用文件清单发布时必须同时部署新路径配置和更新后的 Compose；检查新挂载后再移除服务器旧配置副本。

升级后复查健康、身份、数据完整性、同步启动和登录。回退应用时恢复对应源码/配置及旧镜像，保留实时数据库；旧备份覆盖实时库会丢失升级后的用户写入和同步结果。具体镜像、备份目录和历史回退步骤见各次发布记录。

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
