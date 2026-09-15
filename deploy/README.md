# 服务配置

| 路径 | 职责 |
| --- | --- |
| [nginx/nginx.conf](nginx/nginx.conf) | HTTPS、官网、下载目录与服务路由 |
| [platform/config.yaml](platform/config.yaml) | Registry、MQ、libp2p 和持久化配置 |

统一启动入口仍是仓库根目录的 [docker-compose.yml](../docker-compose.yml)。
Compose 的构建路径、命名卷和项目目录保持稳定，避免目录整理创建另一组空数据卷。
域名、证书路径及 libp2p 公网地址是现有部署配置；另建环境时按
[部署指南](../docs/operations/DEPLOYMENT.md)调整。

升级这次目录布局需从根目录同步完整仓库与子模块，然后执行 `docker compose config --quiet`
和 `docker compose up --build -d`，使新的配置挂载路径生效。
