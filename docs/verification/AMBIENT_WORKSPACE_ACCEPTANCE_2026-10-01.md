# Ambient Workspace 客户端与容量验收（2026-10-01）

本次独立复核认为 Ambient 已符合[云端交接契约](../developers/AMBIENT_WORKSPACE_HANDOFF_2026-10-01.md)，未发现阻止合并的客户端问题。联调确认原 Compose 的 128 MiB 应用预算不足以加载完整工作区，云侧已提高到 256 MiB，并在 384 MiB Linux 容器内完成短时单节点容量验证。

本记录不证明公网 Workspace 启用，实际服务器部署、域名与 TLS 状态见[发布记录](../releases/AMBIENT_WORKSPACE_DEPLOYMENT_2026-10-01.md)。此前的[云端分支验证](WORKSPACE_GATEWAY_CLOUD_2026-10-01.md)保留当时的结果与未覆盖范围。

## 固定源码与环境

| 组件 | 本次核对的提交 |
| --- | --- |
| Ambient | `793da83ac263aebe26dc989d5e025d8b7c7c01de`；客户端实现为 `9de811594725b79c8ad531978d7892474145225b` |
| Web | `fa55096cc66f88f17f1b6191a5bc41d046cd08e8` |
| 部署仓库 | `f472f5b8b8f57805f8addd73b62a6ad026da4d93`；承接云端实现 `d6dd823f1b379440616a2dc2e866ce9d9bac7729` 并修正预算 |

Ambient 独立复跑使用 Windows、Python 3.13.5，禁用字节码及 pytest 缓存；测试仅使用临时 SQLite、合成账户、节点目录与 loopback 监听，不读取真实用户身份。网络脚本使用真实 Gateway HTTP/Tunnel/浏览器 WS、合成 HTTP 上游和真实 echo WS，上游数据不属于真实业务。

Linux 容量探针使用本次构建的 Linux/amd64 Gateway 镜像 `sha256:afec80d7c4756321f2b5a6155782b993534d117ff6f197ae3a53acbe69af6910`，revision 为上述部署仓库提交。镜像的 `app.py`、`launcher.py`、`safeguards.py` 与挂载源码哈希一致；依赖为 Python 3.12.14、FastAPI 0.139.0、Uvicorn 0.51.0、websockets 16.0。容器使用 384 MiB 内存上限、0.5 CPU、只读文件系统和隔离网络。

## 客户端契约复核

已阅读 Ambient 的 Connector、配对 API、远程设置 UI、服务请求层及对应协议测试：

- 接入码仅在本次配对请求中发送。API 使用 `SecretStr` 与安全验证错误；`node.json` 持久化采用字段白名单，公开状态和错误不包含设备凭据、接入码或不可信响应正文。前端在关闭窗口或一次尝试结束后清空码，不写 URL 或 localStorage。
- 账户绑定的 pending 不等于 claimed。只有用户在本机明确提交匹配的 `account_id`、`grant_id`，且 Gateway 返回相同身份、权限及到期时间，才保存本机批准状态并建立 Tunnel。
- paired 重启保留节点身份、grant、原期限和 origin。每次转发重新核对本地授权与 scopes；失效、到期、撤销和删账户停止转发。本机撤销先清凭据，再关闭 Tunnel、WS 并取消在途 HTTP。
- 429 遵守有界 `Retry-After`，连续失败指数退避并加抖动。容量门禁产生的 Tunnel 握手 403 会通过设备 state 复核，保留仍有效的身份并在容量释放后恢复。失去配对响应、超时或断线不会自动重放创建节点、HTTP 写操作或 Run。
- 固定 Frame 资源白名单、传输大小限制、header 过滤、双向 WS 与子协议、本机管理 API 的可信来源检查保留；普通远程操作权限不能修改模型、Coding Agent 和技能管理配置。

## 实际检查结果

| 检查 | 结果与边界 |
| --- | --- |
| Ambient Connector 独立回归 | `tests/backend/test_remote_workspace.py`：68 passed，4.22 秒；一项既有 Starlette/httpx 弃用警告 |
| Ambient/Gateway 独立真实网络联调 | `scripts/verify_remote_workspace_handoff.py`：6 组全部 PASS，使用临时状态和真实 loopback 网络 |
| Gateway 隔离回归 | 48 passed |
| Ingress 配置单元 | 11 passed |
| Compose 配置 | 包含 v2 的四 overlay 组合解析通过；使用合成环境，不证明真实证书或 DNS |
| Linux 单节点容量探针 | 一条 Tunnel、四条浏览器 WS、四个并发 2 MiB HTTP 请求及响应通过；WS 使用上限 256 KiB 文本/二进制双向传输 |
| 撤销与回收 | 所有 WS 关闭，Tunnel/WS/HTTP 连接及队列归零；指标请求自身仍预留 32,768 bytes |

六组真实网络联调分别覆盖：

1. 一次性接入码、同账户领取、错账户不消耗码、本机确认、真实 Tunnel、HTTP 写入只执行一次、超时不重放、四条 WS 的子协议和文本/二进制转发、撤销。
2. quota 拒绝保留接入码、429/Retry-After、本机冷却阻止提前请求、过期码拒绝。
3. grant 到期、删账户与永久 tombstone、无效设备停止。
4. 原 128 MiB 预算实际拒绝第三条浏览器 WS。
5. Tunnel 容量拒绝时 state 复核、身份保留、不替换原连接、容量释放后自动恢复。
6. 旧 schema 的 paired 身份与 origin 保留、Gateway/Ambient 重启、旧未批准节点作废。

Ambient 自身的[浏览器验收记录](https://github.com/BillShiyaoZhang/ambient-agent/blob/793da83ac263aebe26dc989d5e025d8b7c7c01de/docs/verification/remote-workspace-handoff-2026-10-01.md)另记录隔离 Playwright、真实 Ambient UI、Widget 数量从 0 到 1、空聊天的三条 WS 加 Widget WS、一次性打开链接消费及干净 URL、host-only Cookie、本机撤销后旧 Cookie HTTP/reload 401。该浏览器环境为合成工作区、loopback HTTP，本次没有将其表述为公网 TLS 验收；`favicon.svg` 的 403 是已记录的图标请求拒绝。

## 预算修正与 Linux 实测

应用预算是保守的对象、传输和队列预约，不能当作进程 RSS，也不能用配置中的连接计数上限推导可达容量。

| 场景或测量 | 结果 |
| --- | --- |
| 128 MiB：一 Tunnel 加两 WS | 预约 109,331,432 bytes；第三条 WS 被容量门禁拒绝 |
| 256 MiB：一 Tunnel、四 WS、两 HTTP | 预约 209,746,904 bytes，可接纳 |
| 一 Tunnel、四 WS、四 HTTP，含指标请求 | 预约 235,207,640 bytes，低于 268,435,456 bytes |
| Linux Gateway RSS 样本最大值 | 84,066,304 bytes |
| Linux Gateway 生命周期 `VmHWM` | 91,013,120 bytes |
| Linux 测试容器 `memory.peak` | 141,492,224 bytes；包含测试进程，不能直接视为 Gateway RSS |

完整 Ambient 页面需要至少聊天三 WS 和 Widget 一 WS，因此 128 MiB 不满足该单节点场景。`f472f5b` 已把 Compose 与环境示例的 `WORKSPACE_GATEWAY_BUFFER_BYTES` 从 `134217728` 改为 `268435456`，保持容器上限为 384 MiB。

两张同时保持四条 WS 的完整活动页面，即使共用一条 Tunnel，其预约量也已超过 256 MiB，会受容量门禁限制。32 Tunnel、64 WS 等配置仍是独立计数上限，不表示该内存预算能够同时承载这些数量。

Linux 探针复现源码与构建证据保存在忽略的 `build/workspace-capacity-review-20261001/linux_capacity_probe.py` 和 `build/releases/workspace-20261001/`。测试容器、子进程和临时数据库已清理；未重置真实身份或工作区状态。

## 复跑入口与未覆盖范围

```sh
# Ambient 仓库，使用已有测试依赖；不写 pytest 缓存或字节码
python -B -m pytest -p no:cacheprovider tests/backend/test_remote_workspace.py -q
python -B scripts/verify_remote_workspace_handoff.py --gateway-root /path/to/agent-collaboration-deploy/workspace-gateway
# 部署仓库的其他入口见 tests/README.md
python -m unittest discover -s tools/workspace/tests -v
python tools/maintenance/check_structure.py
```

本次 Linux 结果证明短时单节点上限帧/HTTP传输与撤销回收，不覆盖 nginx/TLS、真实公网域名及 CA 信任、续期、协议队列全部填满、多节点最坏峰值或长时间压力。没有发送真实 LLM 消息或重复执行真实 Run。生产备份恢复、真实账户与权限边界、完整 Workspace 公网联调须按实际发布环境另行记录。
