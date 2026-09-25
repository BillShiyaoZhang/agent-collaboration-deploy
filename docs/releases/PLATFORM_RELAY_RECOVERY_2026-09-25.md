# 2026-09-25 Platform Relay 配置故障恢复

生产 ECS `i-0jleb7de83gsnoa0yuc2` 的管理台将 `relay_enabled: true` 保存至 `platform_data` 卷中的 `admin-policies.yaml` 后重启 Platform。当前已签名的 v2 策略为 `compliance` epoch 3、`allow_v1=false`；该模式不能使用透明 libp2p Relay。Platform 启动日志反复报出 `compliance v2 policy requires relay.enabled=false`，容器处于重启循环。公网 `/healthz` 与 `/admin/` 返回 502，官网首页和 Web 登录页仍返回 200。

## 恢复与验证

2026-09-25 10:02 CST，先将实时策略文件备份为服务器本地 `/var/lib/docker/volumes/agent-collaboration-deploy_platform_data/_data/admin-policies.yaml.before-relay-recovery-20260925T020206Z`，再只把 `relay_enabled: true` 改回 `relay_enabled: false`。随后使用基础 Compose 与 v2 覆盖文件重启 `platform`，对 nginx 执行 `nginx -t` 和 reload。未覆盖数据库、身份、签名策略或其他管理设置。

恢复后，`platform` 为 `running`，检查时重启数为 0；公网 `/healthz`、`/admin/`、`/api/v2/policy` 均返回 200。公开引导接口中的 Peer ID 仍为 `12D3KooWNApwdxwbXY27N44cGxTXY15Hn8yRx9m9Yw5St5A7kTpK`，公开策略仍为 `compliance` epoch 3、`allow_v1=false`。这些检查证明 HTTP 服务与原身份、策略恢复可访问；未据此声称 Agent 间业务消息完成，也未运行数据库一致性检查。

恢复操作没有更换生产镜像。检查时服务器根仓库提交为 `1869f2d`、Platform 子模块为 `b1526b5`，Platform 镜像为 `sha256:0372f06156656d4709b959a748d69aae0cf5d9058e161c7f82fdcdf8c743ad77`。管理台防复发校验已在本地源码完成并通过 Go 测试；只有实际发布新镜像后，线上预览和提交才会拒绝上述不兼容组合。回退本次恢复操作时应审查实时策略和当前签名政策，不能把会导致启动失败的 `relay_enabled: true` 原样恢复。
