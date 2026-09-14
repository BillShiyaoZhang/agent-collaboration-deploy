# 早期试用发布记录 · 2026-09-14

本页记录当天**首次试用发布**，保留当时的实现与验证范围。之后已增加账户内容保存与后台同步，当前行为和后续发布状态见 [工作台同步发布记录](WORKSPACE_SYNC_RELEASE_2026-09-14.md)；首次使用请从 [项目介绍与入口](../README.md) 开始。

状态：已部署至现有域名。用户明确授权公网部署；未向其他人发送邀请，未用现有用户身份进行测试或发送消息。

## 入口及产品范围

- 工作台：https://agent-communication.online/dashboard
- 注册：https://agent-communication.online/register
- 可转发邀请：https://agent-communication.online/downloads/agent-comm-early-access-invitation.pdf
- 下载校验清单：https://agent-communication.online/downloads/release-manifest.json
- 开发源码：https://agent-communication.online/downloads/agent-comm-early-access-source.zip

公开安装包覆盖 Windows amd64、Linux amd64、macOS arm64，包含平台对应 helper、`agent-comm-runtime 0.1.0`、`hermes-platform-agent-comm 1.3.0`、校验清单、安装和配置脚本。首个完整宿主适配为 Hermes；其他宿主、知识图谱和交互渠道有版本化扩展接口及参考实现，尚不能宣称已全部接入。

Web 仅维护账户、控制台身份、连接记录与有期限的 RPC 密文缓存。联系人、协作状态和远程会话结果由 agent 返回。原生审批仍在 Hermes；不开放远程审批或后台对端自动调用私人模型。

## 验证

- runtime 39、Hermes 109、Web 54、接入脚本 12，共 214 项测试通过。
- TypeScript、Windows 本地及 Linux Docker 生产构建通过。
- 真实 Go helper/platform 验证身份认证、收发、离线队列和重启恢复。
- 完整本地 Web + Go + Python 验证真实注册/登录、控制台身份、双签名 Registry、加密 RPC、agent 联系人读取和撤销。
- 最终 wheel 的 20 个包内源码/技能/清单文件与工作区逐字节比对通过；三套安装包的 `install.py --check-only` 通过。
- 公网登录、注册、健康检查、邀请 PDF 和校验清单均返回 200；本机 curl 和实际 Edge 浏览器在严格 TLS 验证下访问成功。
- 浏览器以 1440×900、390×844 检查登录/注册页，布局无横向溢出或表单截断。截图对应初次上线版本；最终 r2 只增加登录回跳安全校验，不改变布局。
- SQLite 完整性检查通过，迁移前后所有旧表行数保持。旧业务表只保留历史数据，新应用不再维护这些表。

证据保存在本地 `build/early-access/`、Web 的 `build/full-stack-smoke/`、`build/public-browser-check/` 及 SDK 的 `build/helper-platform-test/`。这些临时日志不打入公开源码包。

## 部署与回滚

最终 Web 镜像：`agent-collaboration-web:early-access-20260914-r2`。

镜像 ID：`sha256:37cc9d7a4356f4da72153061a9cb4c7bde588a642bcd44c051edb8ee6b5c8c6a`。

服务器发布记录：`/root/agent-comm-releases/early-access-20260914-r2/deploy-result.json`。

本轮重构前备份：`/root/agent-comm-backups/early-access-20260914T072049Z`。

最终补丁切换前备份：`/root/agent-comm-backups/early-access-20260914T084203Z`。

备份包含 SQLite 在线一致性备份、原 Web 源码、Compose/nginx 配置和 rollback.json。旧镜像分别保留 `agent-collaboration-web:rollback-20260914` 与 `agent-collaboration-web:rollback-20260914-r2`。回滚先确认目标，恢复对应源码/配置并将目标镜像标为 `agent-collaboration-deploy-web:latest`，再重建 web/nginx；当前数据库迁移是增量的，不应直接覆盖实时数据库。

r2 首次切换遇到 nginx 尚未监听即触发健康检查，自动回滚成功。补充连接就绪重试后再次切换，最终检查通过。平台容器未重新部署。

初次公网部署使用多层仓库的已校验工作区快照，公开源码 ZIP 保存该发布快照。本次 Git 发布同步提交 SDK、platform、Web、deploy，并更新两级子模块引用；递归检出发布后的 deploy 提交即可取得相应实现。实际运行镜像仍以上述镜像 ID 和服务器发布记录为准。今后仍须由内到外提交并推送，避免根仓库引用尚未公开的子模块提交。

## HTTPS 续期修复

发布期间发现原证书在当天到期，现已续期至 **2026-12-13 07:40:15 UTC**。Certbot 改为 webroot 验证，Compose 将 `./acme-challenge` 只读挂载到 nginx；无需停机完成后续验证。

已启用服务器现有 `certbot-renew.timer`。成功续期后，`/etc/letsencrypt/renewal-hooks/deploy/agent-comm-nginx.sh` 检查并 reload nginx。原续期配置位于本轮重构前备份目录。不要另建一份重复的停机续期 cron。

## 试用边界与后续

Linux/macOS helper 为交叉编译产物，尚未在对应真实 Hermes 宿主上完成完整交互测试。不要将本地模拟 handler 测试描述为真实模型或真实日历执行测试。远程会话可运行真实 Hermes Gateway，但用户自己的宿主版本、模型、交互渠道需在试用中验证。

已披露内容和已运行工具无法撤回；撤销控制后续访问。10 分钟 Web 缓存期限为可读取有效期，过期记录在后续控制调用/轮询中清理。Web 后端作为托管控制台身份端点会解密显示内容。

非阻塞界面整理项：favicon 缺失、旧 metadata 描述以及页脚备案图标位置。首批试用反馈应优先记录宿主版本、配对/期限、真实会话完成情况、原生确认体验及错误 request_id；不要收集密钥或无关私人记忆。

当前架构、Mermaid 流程和适配开发说明见 [架构图](PROJECT_ARCHITECTURE_DIAGRAMS.md)、[扩展接口](ARCHITECTURE_AND_EXTENSION_PORTS.md)、[实现交接](PERSONAL_AGENT_COLLABORATION_IMPLEMENTATION.md)。
