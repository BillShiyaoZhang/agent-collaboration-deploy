# 长期授权建议验证（2026-10-02）

独立分支 `codex/ambient-until-revoked-20261002` 基于 `bfc7d0bec494612880d9c150ee44fb9fcee48942`；原 Gateway 源码与发布版本 `152dea974f09e5dbca4d0da16867df1be9d3395e` 相同。[协议文档](../developers/AMBIENT_UNTIL_REVOKED_PROPOSAL_2026-10-02.md)先保存，再执行 Red/Green。未修改原项目 main、Web/Platform/SDK 固定提交、线上配置或授权数据库；尚未提交、推送或部署。

## 单元与协议验证

Windows 宿主、现有 Python 3.12 / uv 环境 `--no-sync`，临时合成 SQLite，不继承真实身份或运行模型。focused Red 实际 19 failed、16 passed；完整 Gateway 与 ingress renderer 回归最终 **93 passed、16 subtests passed**。现有 Starlette/httpx deprecation warning 保留；没有安装依赖以消除它。修改的 Python 文件 Ruff 通过。

覆盖严格 until_revoked 布尔值、无凭证/无状态写入能力 DTO、Host/method/query/body 边界、安全 422 不回显 input、原 bounded 最大期限与省略模式兼容、固定 year 9999 epoch/ISO 的 Windows 格式化、账户绑定与本机批准、五分钟未批准期限、长期节点的六十秒 launch/一小时 session、撤销和删账户关闭 Tunnel、原有限期与长期 paired 重启期限保持。无旧授权期限迁移。

## 真实 Linux ingress

隔离 Docker Linux nginx 以 `nginx:alpine@sha256:1ed1b0e1d7652937d6cbdaf4018c7b6fc009a7dd6c3047351e2eddda745de43f` 运行。缓存 `agent-collaboration-deploy-workspace-gateway:samesite-hotfix-152dea9` 仅提供 Python 解释器运行合成 echo upstream；不把该旧 Gateway 当作已实现新协议的证明。合成两日 TLS、随机专用容器/网络、动态 loopback 端口，没有读取真实证书或连接公网生产账户。

`check_ingress.py --origin-mode both` 在 `separate-site` 与 `same-site-subdomains` 两种模式共 **28 项通过**：新 exact capability GET 转发且无 Cookie/Authorization/redirect，POST 405、后缀 404；原公网 health/账户拒绝、代理头覆盖、精确私网 peer、TLS/明文 Host 拒绝、HTTP/WS、正文门禁、配对限流与 Retry-After、门户同站防护均保留。测试结束后 finally 清理全部随机测试容器/网络，独立 Docker inventory 未发现 `workspace-check-*` 残留。

这是实际 Linux nginx 路由验证和 Windows Gateway 协议测试，**不证明真实新 Gateway Linux 镜像、浏览器或公网长期授权端到端已经完成**。接受建议后仍须按部署门禁构建固定镜像、备份实时数据库、更新 renderer 配置、检查/reload nginx，验证公网能力与私有路由，再由本机明确创建和批准新长期 grant。Portal 当前 schema 可解析 sentinel，无需改变 Web 子模块才能使用本机期限选择。

## 文档与证据边界

完整 `tools/maintenance/check_structure.py` 已执行；独立干净 clone 缺少历史报告所引用的 ignored build/旧审计产物，出现 92 个原有缺失链接。未复制真实历史状态来掩盖缺失，也未弱化 checker。本次修改文档没有缺失链接；固定子模块仍为 Web `4abb3f34331f2d26be411cf0af60bd3827b26314`、Platform `407ed72b4fdf1c42f25e3afe56e0de9308813c25`、SDK `e2f6fce544f8dcf8523fcacb70184d51c3749a14`。

Red、完整 Green、Linux ingress 和结构校验日志留在 Ambient ignored `.cache/ambient-until-revoked-20261002-evidence/`；日志不提交云建议分支。原云工作树检查仍干净。没有模型调用或真实 enrollment/claim/approve/revoke。
