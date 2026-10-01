# Ambient 验收、main 合并与 Web 部署（2026-10-01）

Ambient 客户端符合云端交接要求，独立协议、网络与 Linux 容量检查通过；Web 与部署仓库已快进合并并推送 GitHub `main`，本次两个 proposal/review 分支已删除。Ambient、Platform、SDK 原本只保留 `main`，本轮没有修改它们的源码或用户状态。唯一修正是云端默认应用预算从 128 MiB 提高到 256 MiB，使完整页面的四条 WebSocket 能同时建立。

北京时间 18:28 左右，现有云服务器已更新 Web 和 nginx 配置，18:29:44 完成切换后验证。**Workspace 公网入口尚未启用**：服务器仅有 `agent-communication.online` 的证书，没有独立工作区域名、DNS 与通配符 TLS。Gateway 镜像已经加载，未启动公网服务；新增页面及源码部署不能当作远程工作区已可用。

## 固定版本与验收

| 组件 | 固定提交或镜像 |
| --- | --- |
| 部署代码 | `f472f5b8b8f57805f8addd73b62a6ad026da4d93`；本发布记录与后续纯文档提交另行同步 |
| Web | `fa55096cc66f88f17f1b6191a5bc41d046cd08e8` |
| Ambient | `793da83ac263aebe26dc989d5e025d8b7c7c01de`；客户端实现 `9de811594725b79c8ad531978d7892474145225b` |
| Platform / SDK | `407ed72b4fdf1c42f25e3afe56e0de9308813c25` / `e2f6fce544f8dcf8523fcacb70184d51c3749a14`，未更换 |
| 运行 Web 镜像 | `sha256:e0e40142b8da1f2c295e5785ee8a2df7179ead3288db777a1ebc4cb08bb750ce`，OCI revision 为 Web 固定提交 |
| 待启用 Gateway 镜像 | `sha256:afec80d7c4756321f2b5a6155782b993534d117ff6f197ae3a53acbe69af6910`，OCI revision 为部署代码固定提交 |
| 保留的 nginx 镜像 | `sha256:311761cac6bbc23041f3f4302699b0b5d0614e0a4d28b70def415e7bf16050c1`，与切换前一致 |

[独立验收记录](../verification/AMBIENT_WORKSPACE_ACCEPTANCE_2026-10-01.md)详列 68 项 Ambient 测试、6 组真实 loopback 网络联调、48 项 Gateway 测试、11 项 ingress 单元测试、四文件 Compose 合成配置和 Linux 容量结果。客户端接入码不持久化、不重放写入，本机明确批准、旧 paired 身份重启、撤销、到期与删账户停止转发均通过。

Linux/amd64 实际 Gateway 镜像在 384 MiB、0.5 CPU、只读与隔离网络容器中完成一 Tunnel、四 WS 和四并发 2 MiB HTTP；最大预约 235,207,640 bytes，Gateway RSS 样本最大 84,066,304 bytes、生命周期 VmHWM 91,013,120 bytes，测试容器峰值 141,492,224 bytes。撤销后连接和队列归零。这是短时单节点合成验证，不覆盖公网 TLS、满队列和多节点最坏峰值；默认 256 MiB 不能同时承载两张完整活动页面。

## 构建、备份与切换

Web 和 Gateway 从固定提交的 `git archive` 在本机 Docker Desktop 离线构建 Linux/amd64 镜像，不在 1.8 GiB ECS 执行 Next 构建。Web 生产构建及非 root 运行文件检查通过；合并镜像归档 243,753,093 bytes，SHA-256 为 `07996ec5920a6a56f4d00809533e4578ab7888c5ef70bfc13e27d3bcdb1b813f`。本机 gzip CRC、Docker manifest、Config IDs 与云端 SHA-256、镜像架构和 revision 均一致。

服务器为 ECS `i-0jleb7de83gsnoa0yuc2`（`8.130.40.38`），源码路径 `/root/agent-collaboration-deploy`。通过现有 Workbench CLI 上传到私有 `/root/agent-comm-releases/workspace-20261001/`；准备、加载、切换和验证分别保存脚本、日志及检查点。开始前四仓服务器工作树均干净，源码按上表固定版本更新。备份在该目录的 `backup/`，目录仅 root 可访问，文件为 0600。

| 在线 SQLite 快照 | 字节 | SHA-256 |
| --- | --- | --- |
| Web `web-prod.db` | 5,787,648 | `375fd3738258b1416bff54faf7245601ae8df10fcd6612d8984af7f61b062271` |
| Registry `platform-registry.db` | 81,920 | `0b306d7e766781ae724e8616764f7c24595d499c361e625e7e7b8a559dd10b2f` |
| MQ `platform-mq.db` | 862,371,840 | `f1b3cbf6875324444bef171b15c8b24be6bfa345f8e204656fa609f4cee71db8` |
| Audit `platform-audit.db` | 24,576 | `0a22656950f54b9a461f0d6c06322bf27117fddbf6a625acedfb62c410165e41` |

四份快照均 `PRAGMA quick_check=ok`；它们是各库的在线一致性快照，不声称跨库同一事务。原 `.env`、Compose、nginx 配置、Platform 身份、v2 策略与密钥、Web managed issuer 及管理策略也保留在私有备份。没有用备份覆盖实时卷；切换前后原配置及身份文件 SHA-256 完全相同。

保留旧 Web 镜像为 `agent-collaboration-deploy-web:rollback-before-workspace-20261001`，nginx 原镜像为 `nginx:workspace-preserved-20261001`。服务器只加载镜像，使用 base + v2 + 本次固定镜像 override 执行 `--pull never --no-deps --no-build --force-recreate`，依次替换 Web 和 nginx。nginx 需要重新创建以装入新增 optional include 的绑定文件；使用原镜像，不追随漂移的 `nginx:alpine` 标签。Platform 未重建，启动时间仍为 `2026-09-29T12:50:58.975128793Z`。

加载时磁盘一度只剩约 876 MiB。本轮只删除七个经过本机完整副本及云端 SHA-256 核实的镜像传输文件（包含本次已加载归档），共 1,366,508,302 bytes；保留所有数据库/配置备份、回滚镜像、最近的旧 Web 归档、两份活动 swap 和发布日志。本机归档及清单仍在忽略的构建目录。最终约剩 1.8 GiB，仍需留意主机磁盘余量。

## 切换后实际证据

`2026-10-01T10:29:44Z`（北京时间 18:29:44）的只读验收：

- 官网 `/`、`/login`、`/docs/`、`/healthz` 与新的 Workspace 运维原文返回 200。
- 未登录 `/connect-workspace`、`/dashboard/workspaces` 返回预期 307；`/api/workspace-nodes` 返回 401。
- Web、Registry、MQ、Audit 实时数据库均 `quick_check=ok`。
- Web 与 nginx 为上表镜像，Platform 为原镜像；三个容器持续 running，重启数 0。
- 原身份、`.env`、v2 配置及在线密钥字节保持一致。以容器真实 nginx/nextjs 用户检查四仓公开文档读取权限通过。

本轮没有读取真实用户正文、发送 LLM 消息、执行 Run 或新建真实账户；没有升级用户 PC 上的 Ambient 或 Hermes，也没有发布新 SDK 安装包。上述匿名网页、镜像和数据库检查不能替代完整 Workspace 公网配对验收。

## 公网入口剩余配置

需要已持有的独立注册域，与门户 `agent-communication.online` 不同；控制与节点可同属这个新域，例如 `gateway.example.net` 与 `*.nodes.example.net`。还须配置指向服务器的 A 记录和节点通配符 DNS、DNS-01 wildcard TLS、专用 Gateway secret、证书挂载与续期 hook。不能用 `nodes.agent-communication.online` 绕过不同注册域要求。

按[Workspace 运维](../operations/WORKSPACE_GATEWAY.md)验证实际证书并生成 nginx 入口，再保留原 v2 配置使用 base + v2 + workspace + workspace.production 四文件启用服务。启用后用隔离账户和测试 Ambient 完成公网 enrollment、claim、本机 approve、单次 ticket、Frame/四 WS、撤销与旧 cookie 失效、账户接口/健康/指标封闭及代理日志无票据验收；到时补充新的实际结果。本记录保留当前尚未启用的证据。

回滚 Web 时使用上述旧镜像、对应保存的 Compose/nginx 配置及原密钥，保留实时数据库，不用旧快照覆盖新写入。Workspace 未来启用后，其数据库及永久删账户 tombstone 必须按运维文档单独备份和恢复。
