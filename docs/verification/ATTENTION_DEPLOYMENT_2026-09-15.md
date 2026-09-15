# 通知与协作部署验证

日期：2026-09-15。部署到现有服务器，并升级已连接 Web 的本机 Hermes。

## 已部署版本

| 组件 | 版本 / 提交 |
| --- | --- |
| Deploy | `0c162e0e35437ec9dfd3139c8cba53fc27c36006` |
| Web | `dc3b4465ba97da5dbafa4f07b4059633098eeeae` |
| Platform 的 SDK 引用 | `97366a352b3a312aa022fee8944136ddf7298b90` |
| SDK | `14a8057e32303791d90fbe5029d9d81b7807bc6d` |
| 本机 runtime / Hermes connector | `0.1.1` / `1.4.0` |
| Web Build ID | `4l9U8Z3DCECtt__VzoJEx` |

Web 镜像：`sha256:0ceeb30ac2153538d02d36f8b2106f9bae52d25caf5f3dd3abd1b1c0db34c2a9`。
入口：[通知中心](https://agent-communication.online/dashboard/notifications)。

代码已保存为本机提交，并通过现有 Workbench 传到项目服务器。用户另行明确授权 GitHub 推送；截至本次记录，直连和现有本机代理均在 TLS 握手时失败，**尚未推送 GitHub**。打包快照内的 remote-tracking refs 不作为已推送证据。可选的快照 Git 跟踪信息清理被自动审批拒绝，未执行。

## 部署验证

- 服务器隔离候选使用 `--network none`、合成账号和合成数据库，未复制真实业务行。
- 新 SQL 连续执行两次，旧表行保持不变；四张通知表、外键和 SQLite 完整性通过。
- 沿用已核对版本的 Linux 运行依赖；补充的 Prisma 生成器与锁定官方 npm 包的 SHA512、文件字节一致。仅针对当前 Linux 架构生成客户端，原始 schema 保留。
- 生成器复制的 Linux 引擎与基镜像字节一致；当前构建及保留的旧静态资源共 201 个文件通过校验。
- 隔离候选通过登录、分片会话、账号隔离、通知筛选、非法输入拒绝、数据库 API、前端资源和后台同步验证。
- 北京时间 14:51 完成 Web 切换；线上健康检查、匿名接口 401、后台新同步、四张通知表和数据库完整性通过。
- 真实 User/Agent ID、原密钥、环境变量和数据卷保留；原登录会话可继续使用。Platform 与 nginx 容器未重建，nginx 仅重新加载。

## 本机与真实 Web 验收

升级前备份旧插件、配置和数据库，并在 Gateway 空闲后正常停止。升级后已验证唯一 connector 安装来源、Gateway 运行和提醒后端可读。

经用户明确确认，只为现有本人 Web 配对增加 `attention.list`，原身份、其他权限和到期时间保持不变。Web 的持久提醒基线已完成，真实连接状态为 `ready`。

使用五分钟自行到期的 self 待决任务 `attention-deploy-20260915T065314Z`，未新增联系人，未确认、未分发，操作数为 0。

| 实机检查 | 结果 |
| --- | --- |
| 新待办自动出现 | 通过；无需刷新，Bell 与通知中心显示 1 未读 / 1 待处理 |
| 已读不等于已处理 | 通过；标为已读后显示 0 未读 / 1 待处理 |
| 跨标签、刷新后保持 | 通过；仍为 0 / 1 |
| 定位具体问题 | 通过；打开对应任务并展开原生问题，没有 Web 批准按钮 |
| 自然到期及源端收敛 | 通过；北京时间 14:58:14 到期后，待处理降为 0，历史保留“已到期”；Hermes 源端及 Web 持久记录均为 `expired` / revision 2，执行操作仍为 0 |

已读按事项版本记录：原 open 版本已读后，源端 expired 新版本到达仍会产生一条未读更新（1 未读 / 0 待处理）。业务截止时待处理先归零，与随后到达的新版本未读是两个独立状态。阅读该终态后，两个标签均为 0 未读 / 0 待处理；保留通知中心，已关闭临时第二标签。

本次线上验证覆盖提醒闭环及协作任务的定位。双边协作 v2 的提议、双方接受、约定回执、取消和恢复，已在[此前隔离集成验证](COLLABORATION_ATTENTION_2026-09-15.md)通过；本次没有代替真实双方进行授权或作出业务承诺。

### 尚未通过的实机检查

- 当前 Codex 内置浏览器显示“浏览器已阻止系统提醒”，开启按钮不可用；没有验证真实浏览器系统弹窗。
- Hermes Desktop 的 `Agent Comm 待办` companion 已安装、后端已启用，但宿主输入保护阻止自动操作前端开关；没有绕过保护或声称桌面弹窗成功。
- 本版浏览器提醒要求页面运行，未实现关闭页面后的 Web Push。

## 备份与回滚

服务器 release：`/root/agent-comm-releases/attention-collaboration-20260915`。

服务器备份：`/root/agent-comm-backups/attention-collaboration-20260915-20260915T065118Z`，含旧镜像引用、原源码、环境文件及通过完整性检查的在线数据库备份。

**必须保留备份中的 `source`**：既有 nginx / Platform 的挂载仍引用其中原文件 inode。在将来明确重建这些容器前不可清理。回滚脚本只恢复源码和镜像，保留实时数据库；不要用旧数据库快照覆盖升级后新增事实。

Hermes 私有备份位于 `%LOCALAPPDATA%/hermes/backups/attention-deployment-20260915T062121Z`。应成对回退 connector/runtime，正常停止 Gateway，保留升级后产生的有效协作事实。

最后核验：三个生产容器均运行且重启计数为 0，SQLite 完整性为 `ok`、外键违规为 0。

本机详细证据位于忽略目录 `build/attention-deployment/`：`manifest.json`、`candidate-progress-v5-final.json`、`deploy-result.json`、`attention-baseline.json`、`final-attention-audit.json`、`local-install.json`、`local-deployment-record.md`、`local-pending-probe-latest.json`。真实浏览器记录为 `build/collaboration-design/production-attention-result.md`。其中不公开私人密钥或业务正文。
