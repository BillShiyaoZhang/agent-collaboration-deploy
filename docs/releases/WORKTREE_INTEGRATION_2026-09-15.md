# 并行 worktree 整合与服务器清理（2026-09-15）

三个并行任务的目录整理、能力映射与联系人导出、技术实现文档已合并；四个仓库已推送默认分支，正式服务于 2026-09-15 12:23（北京时间）完成切换。访问入口：[官网与工作台](https://agent-communication.online)。

## 固定版本

| 仓库 | 默认分支 | 部署源码提交 |
| --- | --- | --- |
| Deploy | main | `23e80a0fe1f79f0e4fdd63a4d1a1c1ecbf5b78be` |
| Web | main | `ea736ec4c21f902f2529a3a9ba225957cc9ba4f9` |
| Platform | main | `a91d99f756f38af2a5323e4f7084b74fd447699c` |
| SDK / agent-comm | master | `d47f0a559bb4fe41a9f0a9b2ee359928ddf09ae5` |

本记录是部署后新增的文档；上表标识实际构建、验收和部署的版本组合。各仓库也保留 `codex/integrate-worktrees-20260915` 分支。原任务 worktree 保留，未提交成果先保存为独立提交，再用合并提交整合。

保留整理后的目录层次，合入能力与 skill 映射、Python `export_contact` / Hermes `agent_comm export_contact` 邀请卡导出以及技术实现文档。SDK 的文档发布清单补入拆分后的 `references/*.md`，避免目录重组后安装包缺少引用文件。

## 组合验证

- SDK Python 65 项、Hermes connector 116 项测试通过。
- SDK 5 个、Platform 6 个 Go 测试包通过；Linux amd64 平台二进制构建通过。
- Web 114 项测试、lint、Prisma generate、完整生产构建通过。
- 发布与早期试用脚本 18 项测试通过；目录与 Markdown 路径检查通过。
- `test_remote_control_network.py` 与 `full_stack_smoke.py` 通过：临时身份、真实 Go 进程、Web 登录与 Python 配对、加密请求与返回、撤销配对和隔离验证；没有向生产发送测试消息。
- 服务器 Web 候选使用空白数据库与隔离网络，验证迁移、登录/注册、账户隔离、安全及分块 cookie、worker 启动、静态资源和 Linux 运行依赖。
- 平台候选使用新身份和独立数据，验证健康/API/文档/管理页、被移除的旧首页、数据库完整性与生产身份隔离。
- 切换脚本通过 27 项测试，覆盖在线数据库备份、密钥备份、目录切换及恢复中断、清单摘要和跨系统换行校验。

## 运行产物

| 产物 | 标识 |
| --- | --- |
| Web 镜像 | `sha256:61af06306b4b22e0cadb829f053362c275f45fdbd340d40e4896b72b824f0146` |
| Platform 镜像 | `sha256:5a29bfe2aae1f46a676f728b2bc35789314b0919c7333ea8305182e0a61b131a` |
| nginx 镜像 | `sha256:cc44224bfe208a46fbc45471e8f9416f66b75d6307573e29634e7f42e27a9268` |
| Next.js Build ID | `D-2PT3yWN9WrjUq5fh8ix` |
| Linux 平台二进制 SHA256 | `2324bd626b592ce8397992d37fc05f3919c3e6dcecb07999298ae714c6cce981` |
| 发布包 SHA256 | `4e58e6c826d7637481389eda53a2a0517b0b9d5698e42643ea9043d12f7251a8` |
| manifest SHA256 | `01ea709f3e7d55b0413714249bdfe99e9e19fdeb9297808286c2049f466efe7b` |

服务器资源有限，运行镜像以已在该机运行的 Linux 镜像为基础，只替换经过校验的应用产物。Web 的运行依赖、迁移入口和原有静态资源兼容性已验证；它不是重新从网络下载依赖的全量 Docker 构建。平台替换为本次 Go 源码构建的二进制。

## 数据保留与回滚

生产目录为 `/root/agent-collaboration-deploy`。目录切换后四仓 Git 状态均干净，提交与上表一致。数据库卷、身份密钥、`.env`、证书、下载目录和 ACME 挑战目录保留；配置路径迁移到 `deploy/`，配置内容保持一致。

备份目录：`/root/agent-comm-backups/worktree-integration-20260915-20260915T042250Z`。

- `source/`：切换前源码及旧配置。
- `databases/`：四个 SQLite 库的在线备份，均通过完整性检查。
- `platform-identity/keys/`：权限受限且指纹核对一致的身份密钥备份。
- `.env` 与 `rollback.json`：环境备份及切换检查点。
- 旧镜像保留为 `agent-web:rollback-worktree-integration-20260915`、`agent-platform:rollback-worktree-integration-20260915` 和 `agent-nginx:rollback-worktree-integration-20260915`。

发布与验收记录位于 `/root/agent-comm-releases/worktree-integration-20260915/`。如需回退，在核对该目录的 manifest 与回滚记录后执行：

```sh
python3 /root/agent-comm-releases/worktree-integration-20260915/server_deploy_v2.py --rollback
```

回滚恢复源码及镜像，保留实时数据库；不会用备份覆盖切换后的新数据。

生产验收：`/`、`/login`、`/healthz` 返回 200，未登录的 `/api/workspace` 与 `/api/agents` 返回 401；四库完整性正常，原 User / Agent ID 与平台身份保留；worker 在新容器启动后产生了新的同步尝试。

切换前曾发现原三个容器处于正常退出状态（非 OOM），已用原镜像、原容器和原配置恢复，原因未确认。第一次正式切换的预检又因四个历史 Git 文件自带 CRLF 换行而拒绝继续；核对原始摘要及规范化内容后修正校验，重跑测试和只读预检通过。这两次处理均未覆盖生产数据。

## 磁盘清理

40 GiB 系统盘清理前使用率约 99%。清理未使用 Docker 构建缓存与 DNF 软件包缓存，两阶段文件系统可用空间合计增加 **30,910,033,920 字节（约 28.8 GiB）**。部署完成时可用 **29.4 GiB**，使用率约 **22%**。

无标签镜像清理实际回收 0 字节；主要空间来自构建缓存。保留了所有已有标签镜像、生产容器所需层、数据卷、下载包、证书、历史发布记录和备份。没有手工删除 Docker 内部存储目录。

## 范围与后续工作方式

本次更新服务器源码和服务；公开早期试用安装包没有重新发布，本机 Hermes 安装也未在本次部署中替换。源码提交和服务器部署不代表所有已安装客户端已经升级。

后续并行任务的提交、整合、子模块发布顺序和固定版本部署流程见 [并行 worktree 的整合与发布](../maintenance/PARALLEL_WORKTREES.md)。
