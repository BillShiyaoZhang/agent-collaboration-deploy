# Workspace Gateway 本地契约验收 — 2026-10-01

范围为独立提案检出新增 Gateway，未修改或发布上游仓库，未连接现网或使用原用户身份。环境为 Windows、Ambient 已有 uv Python 环境、FastAPI TestClient 和隔离临时 SQLite。

先写测试并确认缺少 Gateway 实现导致 `ModuleNotFoundError`，实现后 22 个测试通过。交叉审查发现固定 Frame 模块依赖缺口和慢上传期间会话到期的缺口，均新增失败测试后修复。静态检查 `ruff check` 通过，源码经 `ruff format` 整理。执行命令见 [服务 README](../../workspace-gateway/README.md)。

已验证：服务凭据与云账户隔离；五分钟配对码领取后不可重放、必须由本机按领取账户/grant 确认；不同 Host 不消费他节点 launch ticket、过期/重放票据拒绝；host-only HttpOnly Cookie；完整扁平身份透传与代理敏感头删除；HTTP 真实请求/响应匹配；HTML 同源配置注入且原 CSP 保留；无凭据固定 Frame 壳；WS 子协议及双向文本/二进制；撤销关闭在途 HTTP、既有 WS 和设备连接；授权及浏览器会话到期关闭连接；路径穿越、本机连接管理 API、HTTP 大小、WS 帧大小、HTTP 并发和超时；重启保留身份/grant，数据库不含原始设备密钥或配对码。

补充验证了固定 Frame 模块依赖链、HTTP body 读取及 WS accept 等待期间到期不会派发写请求或接受过期浏览器、WS 并发额度、固定 Frame gzip 大资源的有界原始传输和浏览器解码、发送阻塞也计入整体超时预算、账户批量撤销及永久删除账户 tombstone 阻止重新领取；同账户删除调用幂等，不影响其它账户。

TestClient 报告一条上游 httpx 弃用提示，未影响测试。按仓库 AGENTS 运行 `tools/maintenance/check_structure.py`，有 92 个已有历史链接错误，均为 2026-09-23/24 报告引用本次检出未包含的 `build/` 证据产物；新增 Gateway 文档未报链接错误。此记录不证明真实浏览器/真实 Ambient Connector、Docker 镜像构建、生产 wildcard TLS、运营限流、计费或多副本已通过；完整本地交互由集成验收记录覆盖。

收尾时以独立 `WORKSPACE_DIR`、Gateway `PYTHONPATH`，从 Ambient 检出运行 `uv --cache-dir .tmp-uv-cache run --no-sync pytest -c .cache/agent-collaboration-proposal/workspace-gateway/pytest.ini --confcutdir=.cache/agent-collaboration-proposal/workspace-gateway .cache/agent-collaboration-proposal/workspace-gateway/tests -q`，再次得到 `22 passed, 1 warning in 3.75s`。显式配置和 `confcutdir` 避免加载 Ambient 的 conftest；Windows sandbox 拒绝现有 pytest launcher 后，复验使用获准的本机进程权限。`ruff check` 再次通过；结构检查为 162 个 Markdown、相同 92 个历史证据链接错误。

可选 Gateway Compose overlay 使用独立临时 Docker 配置目录和仅用于解析的合成 `PLATFORM_ADMIN_TOKEN`、`NEXTAUTH_SECRET`、`WORKSPACE_GATEWAY_SECRET`，执行 `docker compose --env-file .env.example -f docker-compose.yml -f docker-compose.workspace.yml config --no-env-resolution --quiet` 成功；未构建镜像或启动容器。

另用全新 Gateway SQLite、随机合成服务密钥和 loopback `8798`，配合 Web 的全新 SQLite 与本地 HTTPS 门户执行未改写断言的 `tests/integration/workspace-portal-smoke.cjs`。保存的输出为 `WORKSPACE_PORTAL_SMOKE_PASS real login, origin/account isolation, local confirmation, deletion revocation and stale-cookie rejection`，退出码 0；确认真实 NextAuth 登录、跨源及伪造账户拒绝、本机确认、错误密码保留授权、正确删除撤销授权、旧会话拒绝及删除后再次 approve 拒绝。完成后按已确认命令行停止本次 Gateway 测试进程；未接触原用户数据库或公开服务。
