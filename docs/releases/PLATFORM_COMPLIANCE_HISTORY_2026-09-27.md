# Platform 合规明文历史与保存期（2026-09-27）

**状态：第二次生产切换于 2026-09-27 02:55:31 UTC（北京时间 10:55:31）完成，只读验收通过。两个 PR 已合并到 `main`，四仓本地与 GitHub 均仅保留 `main`。生产未发送合成消息或修改保存期，正文准入及页面写入仍以本地测试为证。**

## 版本与范围

| 仓库 | 本次固定提交 |
| --- | --- |
| 部署 | `dacd76e448ade7d46792f81bc6f457ec9ea5b502` |
| Platform | `5f0abc3bc07fcbe1551473c8b196fab2fc33868e` |
| Web（固定引用保留） | `78c019bf132e7b55e31b5987ba11617a6ba15662` |
| SDK（固定引用保留） | `fb7fb916945a5c11c219c517f7ff20a1b2856105` |

GitHub 审查入口：[Platform PR #1](https://github.com/BillShiyaoZhang/agent-comm-platform/pull/1)、[部署 PR #1](https://github.com/BillShiyaoZhang/agent-collaboration-deploy/pull/1)。以上是本次构建与生产部署的应用提交，后续补充本记录的纯文档提交不改变镜像来源。

- 合法 v2 `compliance` 准入成功后，原始信封、准入回执与启用留存时的完整明文归档在同一 SQLite 事务提交。`private`、受管 v1 例外和握手不生成明文历史，升级前的消息不回填。
- `/admin/` 增加合规历史页，支持发送/接收 URN 精确筛选、分页和单条正文；读取仍要求平台管理员令牌。
- 独立 `platform.compliance_retention_days` 默认 30 天，页面允许 0–36500 天，保存到数据卷中的 `admin-policies.yaml` 后在线生效，无需重启。期限按平台接收时间算起，与 MQ ACK、TTL、历史清理或队列删除独立；模式或密钥轮换不隐藏仍有效的旧归档。
- `0` 清理已有归档并停止新留存；缩短保存期同步清理超期归档，延长不能恢复已清理正文。正常到期记录即时隐藏，约每五分钟清理。逻辑删除不保证物理擦除或备份删除。

接口与运维说明见[管理后台指南](../operations/PLATFORM_ADMIN.md)和[Platform API](../../agent-comm-platform/docs/guides/API.md)。

## 本地验证与部署镜像

本轮已运行 Platform `go test ./...` 全套和 39 项管理台 Node 测试。检查涵盖合法准入、明文与信封原子性、独立保留期、停止/缩短后的重试、管理鉴权与配置持久化。管理台尚未进行真实浏览器验收；代码和 Node 测试通过不能代替页面交互验证。

项目 Dockerfile 构建未能从已配置镜像源取得 `alpine:3.24.1` manifest（EOF），本轮改用固定 Git 源码快照、缓存的 Go 1.26.8 和已核对的现有生产运行层构建 Linux/amd64 静态二进制（`CGO_ENABLED=0`）；项目 Dockerfile 未修改。该构建方式是本次受限网络环境的 fallback，不能声称完成了原 Dockerfile 的完整联网重建。

| 部署产物 | 值 |
| --- | --- |
| 镜像 tag | `agent-comm-platform:20260927-compliance-history-5f0abc3` |
| 镜像 ID | `sha256:8bbbaed09d4f109f0d88b25f1b8cbe86e29f0bf50974eaef50590850a9d43dd6` |
| 复用运行层镜像 ID | `sha256:a300a1849dc6a763c19f4743038bde1433d22e485476ba06f75aee7581077d56` |
| `image.tar.gz` SHA-256 | `7d8e2be9f6d377bc3ee4edb294f6bf9a36771fc49ad2854cdbf7540532d6b6ff` |
| `image.tar.gz` 大小 | 45,391,954 bytes |
| Platform 二进制 SHA-256 | `23679f2472b650e6d2cc6e0d5a8bd8e85defaba75ee88a212df154b26db63198` |
| 构建时间（UTC） | 2026-09-27 02:40:14 |

本机构建证据保存在 `build/compliance-history-release/artifact.json` 与 `build/compliance-history-release/build-image.json`（未提交的构建产物）。该镜像部署前已用临时合成身份及 tmpfs SQLite 验证健康、admin HTML、历史列表、默认保存期、保存策略和匿名拒绝；该冒烟环境未启用 v2，不能作为真实合规消息链路验收证据。

## 生产部署与只读验收

目标为 ECS `i-0jleb7de83gsnoa0yuc2`，源码目录 `/root/agent-collaboration-deploy`。第二次切换从 02:55:08 UTC 开始，完成时 Platform 实际运行上表新镜像，Linux/amd64 与 revision 均匹配固定提交；容器运行中、重启计数 0、未 OOM。Web 与 nginx 容器未替换，nginx 执行 reload 更新上游。

- 本次备份目录：`/root/agent-comm-releases/2026-09-27-compliance-history-attempt2/pre-cutover/`；初轮目录 `/root/agent-comm-releases/2026-09-27-compliance-history/` 保留供排查与回滚。32 个备份文件 SHA-256 核对通过。
- 四库（Registry、MQ、审计、Web）在线备份与实时库的 `quick_check` 均为 `ok`。它们是逐库一致的在线快照，纳入已提交 WAL 状态，不是跨库统一事务。切换保留实时数据库；19 个受保护文件、容器环境与挂载均保持基线。
- 47 条 User、42 条 Agent 基线记录全部保持原值，凭据比对通过。Platform Peer ID 保持 `12D3KooWNApwdxwbXY27N44cGxTXY15Hn8yRx9m9Yw5St5A7kTpK`；签名策略仍为 `compliance` epoch 3、`allow_v1=false`，摘要仍为 `6f9f7bdf26c5e7761cbe8c451a22fd11f9a448d912fa5bc3ae61c1e53f3ff5c4`。

| 只读检查 | 结果 |
| --- | --- |
| 健康、admin HTML、管理员 overview / 合规历史列表 | HTTP 200；保存期 30 天；历史 `total=0` |
| 不存在的归档详情 | HTTP 404 |
| overview / 历史列表 / 详情缺少令牌，历史列表错误令牌 | HTTP 401 |
| 公开管理指南与 Platform API 文档 | HTTP 200 |
| 私有 agents / workspace API；未公开的历史文档原文 | HTTP 401 / 401 / 404 |
| 02:55:13.080–02:56:41.807 UTC 稳定期复核（约 89 秒） | 三容器 fatal/panic、数据库争锁、pool timeout、nginx 上游错误均为 0；47 User / 42 Agent 身份及凭据不变，历史仍为空、保存期仍为 30 天 |

第二次切换启动窗口记录 nginx 上游错误 2 次，reload 后稳定期为 0；其他 fatal/panic、数据库争锁与 pool timeout 均为 0。日志检查最多读取每容器最新 10,000 行，不能推断未覆盖时间内没有异常。

脱敏证据保存在本地 `build/compliance-history-release/cloud-deployment-summary.json`、`cloud-verification.json`、`cloud-verification-observation.json`、`cloud-preflight-summary.json` 与 `rollback-verification.json`；原始凭据、数据库和私人日志未提交。MQ 备份可能包含合规明文，须按正文数据限制访问，并另行管理备份保存期。

## 初轮回退、回滚与验收限制

初轮切换在 02:50:11 UTC 回退至旧镜像 `sha256:a300a1849dc6a763c19f4743038bde1433d22e485476ba06f75aee7581077d56`，以及部署 `69a00686e97c659a958fb93976f5340c18307914` / Platform `8382a74a881ded7d46241c9333ac06bb55fe078d`；保留实时数据库和身份，回退后的健康、四库、策略、环境与受保护文件复核通过。初轮 verification 未保留具体 reason，无法确定是哪一个检查项触发回退；安全日志记录切换窗口 nginx 上游错误 9 次，不能将其直接认定为唯一失败原因。重试前修正验收门禁，分开记录切换窗口和稳定期错误。

回滚镜像 tag 为 `agent-platform:rollback-20260927-compliance-history`，配置及源码备份在上述目录。应用回退不得用旧备份覆盖切换后写入；旧版不认识新增 `compliance_retention_days` 管理覆盖字段时，先备份并处理该单项兼容性，不清空其他运行策略。

本次生产检查仅为只读：历史为空，没有合成消息准入、真实正文详情、ACK/队列处置后的归档验证，也没有在线修改保存期或验证生产配置写入。本地真实 v2 Go 测试覆盖这些存储与保留行为；管理台 Node 测试不能代替真实浏览器交互。未使用真人消息作测试，也未代用户作披露授权。本次没有重新发布 SDK/helper 接入包；公开安装包不因 Platform 上线自动升级。

本记录与索引已通过结构检查：141 份 Markdown，0 errors；发布证据的功能分支已合并到 `main` 并删除。本次发布证据的云端同步仅更新根仓库文档，不重建服务。

## 后续合并与分支清理

按用户要求，Platform PR #1 与部署 PR #1 已合并，分别形成 `d93b076499557fdf2e036f9101b5c21267de6846` 和 `03fb4531b2ff02365d205953ba6388be44549801`。四仓旧 `codex/compliance-history` / `codex/web-chat-collaboration` 分支的提交均已被各自 `main` 包含；本地和 GitHub 删除这些分支后仅保留 `main`。其他 detached worktree 保留。

根仓库将 Platform 固定引用更新到合并提交 `d93b076499557fdf2e036f9101b5c21267de6846`；其源码树与镜像构建提交 `5f0abc3bc07fcbe1551473c8b196fab2fc33868e` 相同。本次合并与引用更新不改变已部署镜像和数据。
