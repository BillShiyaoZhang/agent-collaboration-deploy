# Ambient Workspace 云端实现验证（2026-10-01）

范围是部署仓库及 Web 的 `codex/ambient-workspace-review-20261001`，未合入 main、未部署云服务器、未发布 Ambient。原提案审查见[历史记录](../architecture/WORKSPACE_GATEWAY_REVIEW_2026-10-01.md)，客户端适配与后续门禁见[交接](../developers/AMBIENT_WORKSPACE_HANDOFF_2026-10-01.md)。

## 源码与环境

父仓库承接提案 `94aeccbbf82aa855a2d430b6e34193789a99bff1` 和审查提交 `065e91e`，Web 基线为 `fc271b6b4093fa23b334869d22c0edee11b27da4`。新 Web 固定提交为 `fa55096cc66f88f17f1b6191a5bc41d046cd08e8`，已推送同名分支并由父仓库 gitlink 固定。Platform 固定 `407ed72b4fdf1c42f25e3afe56e0de9308813c25`、SDK固定 `e2f6fce544f8dcf8523fcacb70184d51c3749a14`，两者未修改。

本机 Windows，Gateway/配置/备份测试使用已有 Python 3.13.5（Anaconda），隔离临时SQLite/合成账户，无真实身份/业务状态。Linux Web全套使用Docker临时目录与Node24.21.0、禁网络。Ingress使用Docker Desktop Linux、与基础Compose相同的nginx精确镜像digest、缓存python:3.13-slim mock上游及自签合成TLS。

Gateway离线PSL来自官方ICANN+PRIVATE列表，快照 `2026-09-30_20-56-07_UTC`，上游提交 `714ac1bf5f2d038161c7419478cc3207431d706d`，文件SHA-256 `73c95828f5f62a3fce06d3fa9b2efd3f0a45a8c8dc2a65411545fab898a576f7`，保留MPL-2.0头。Web锁文件使用tldts7.4.16含PRIVATE规则。

## 实际结果

| 检查 | 结果与边界 |
| --- | --- |
| Gateway完整隔离回归 | 48通过；实现及独立审查各运行一次，1项Starlette依赖弃用警告 |
| Web Linux完整单元集 | 403/403通过；最后Retry-After补充前的全套 |
| Web Windows完整单元集 | 400/401；唯一失败为既有POSIX token文件权限断言，Linux该项通过 |
| Web Retry-After补充 | 定向9/9、最终TypeScript检查通过；独立审查重跑9/9 |
| Web生产构建 | 最新源码已重新构建成功，包含Retry-After补充 |
| Ingress配置单元 | 11通过 |
| 实际nginx隔离验证 | 10组通过；下述安全边界真实经过nginx |
| Compose静态配置 | local及含v2的四overlay生产组合通过，使用合成环境；Web独立Compose也通过 |
| 真实Portal/Gateway HTTPS smoke | 通过：真实NextAuth登录、内部/公开Host分离、发码/重放、pending分页、领取/本机批准、删账户撤销/旧Cookie失效；仅loopback合成状态，监听进程清理确认 |\n| 文档与结构 | 168 Markdown，0错误 |\n| SQLite在线备份 | 4通过：在线WAL保留原grant/tombstone、后续原库写入不改快照、不覆盖、错误无残留/非有限timeout拒绝 |

Gateway覆盖账户绑定接入码、过期/重放/错账户、quota拒绝不消耗码、分页账户/视图签名、审计幂等与保留、pending/历史回收、永久删除tombstone、旧paired身份迁移、慢上传/响应发送超时、断开/取消释放、内网service Host、HTTPS Cookie、固定Frame白名单、真实浏览器WS测试通道回压与mixed-Unicode对象收费。

独立复核发现并修复：内网BFF Host和公开Connector Host分离；Connector accept/替换期间取消的租约泄漏；浏览器也受同一Uvicorn wire ceiling/queue约束，传输和Python宽Unicode字符串/队列按保守上界计入预算。Uvicorn limit_concurrency只提供HTTP传输并发门禁；WS依赖nginx及应用限额。

nginx验证覆盖基础配置+optional include解析、原门户HTTPS健康入口、公开accounts/health/非exact控制路由拒绝、Host保留/伪造代理头清理/精确代理IP、Connector和节点WS各101、节点超2MiB拒绝、launch no-store/no-referrer及日志无票据、未知SNI/Host和明文入口拒绝、配对限流与Retry-After。上游是mock，不表示Ambient Tunnel已联调。

## 可重跑命令

```sh
# Gateway目录，已安装其dev依赖
python -m pytest -c pytest.ini --confcutdir=. tests -q
# 部署仓库根目录
python -m unittest discover -s tools/workspace/tests -v
python tools/workspace/check_ingress.py --python-image python:3.13-slim\n# 先构建Web，使用已装Gateway依赖的Python；不读取dotenv\npython tests/integration/test_workspace_portal_gateway.py
python -m unittest discover -s tools/maintenance/tests -p test_backup_workspace_gateway.py -v
python tools/maintenance/check_structure.py
# Web目录
node --test tests/unit/workspace-nodes.test.cjs tests/unit/workspace-enrollment-client.test.cjs
node node_modules/typescript/bin/tsc --noEmit --incremental false
```

## 未覆盖的发布门禁

真实Ambient尚未发送新enrollment字段，完整原生/浏览器工作区、iframe/CSP、真实业务HTTP/WS及Run不重放未验收。真实DNS、CA信任及wildcard续期、公网、生产数据库/备份恢复、生产RSS/负载、nginx15秒慢正文与240整体并发压力未测试。

默认128MiB应用预约、384MiB容器是保守配置，不证明生产容量；已知上界预约会在并发计数之前拒绝。Ambient联调需实测默认额度下完整前端/Frame加载及多WS，监控真实RSS再决定是否调整。没有读取或重建真实用户身份，没有把源码或测试成功报告为线上发布。
