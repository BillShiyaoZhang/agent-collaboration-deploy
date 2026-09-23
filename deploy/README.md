# 服务配置

| 路径 | 职责 |
| --- | --- |
| [nginx/nginx.conf](nginx/nginx.conf) | HTTPS、官网、下载目录与服务路由 |
| [nginx/docs-source.conf](nginx/docs-source.conf) | 官网文档原文的文本类型、扩展名和只读限制 |
| [platform/config.yaml](platform/config.yaml) | Registry、MQ、libp2p 和持久化配置 |

统一启动入口仍是仓库根目录的 [docker-compose.yml](../docker-compose.yml)。
Compose 的构建路径、命名卷和项目目录保持稳定，避免目录整理创建另一组空数据卷。
域名、证书路径及 libp2p 公网地址是现有部署配置；另建环境时按
[部署指南](../docs/operations/DEPLOYMENT.md)调整。

更新部署时，从根目录同步固定的仓库与子模块提交，先执行 `docker compose config --quiet`
确认配置挂载，再按[部署指南](../docs/operations/DEPLOYMENT.md)备份、升级和验收。
