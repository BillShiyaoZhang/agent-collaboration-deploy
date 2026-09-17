# Agent / Web 能力一致性上线 · 2026-09-17

2026-09-17 21:56（北京时间）完成阿里云生产切换，更新 [Web 工作台](https://agent-communication.online/dashboard/agents)、Platform、三个系统接入包及公开源码 ZIP。实现与隔离网络测试见[能力一致性验证](../verification/AGENT_WEB_PARITY_2026-09-17.md)。用户电脑上的既有组件不会随服务器发布自动升级。

## 版本

发布标识：`agent-web-parity-20260917-17490d9`。

| 仓库 | 发布源提交 |
| --- | --- |
| Deploy | `c6317c63c87aa14d1e84592a0a641f706ea9174d` |
| Web | `0bd2fb3ded747a8c7121ff675b8111f3966ab132` |
| Platform | `b398f4d28e328c2721632d974cf93841ceee6a32` |
| SDK | `5aed3992ea71cab87804b53d9c0d5bbf0bf70365` |

应用整合基线为 Deploy `17490d9`；`c6317c6` 只将接入包说明改为可分发文档。本记录之后的文档提交不改变镜像和安装包所含源码。

两份镜像均从干净 Git 源码、正式 Dockerfile 和锁文件在本地构建为 `linux/amd64`，经 Workbench CLI 上传并在服务器核对 SHA-256 后加载。

| 服务 | 镜像标签 | 服务器镜像 ID |
| --- | --- | --- |
| Web | `agent-web:agent-web-parity-20260917-17490d9` | `sha256:e2859901275f78c9acd6d05d1444c993da88e0603321c3426a099d5641bc67c3` |
| Platform | `agent-platform:agent-web-parity-20260917-17490d9` | `sha256:b3359b418035dd9896c50630eb00c0f5d6be0e262d406d552593a627ca061893` |

Next Build ID：`jDA79pfiwZIAlG5R9sjFl`。实际版本：Node 24.21.0、Next 15.5.25、React 19.3.0、Go 1.26.8。nginx 沿用此前已核验的 1.31.6 镜像。本次不新增 SQL schema、环境变量或公网端口。

## 接入包

[下载清单](https://agent-communication.online/downloads/release-manifest.json)包含三个系统 ZIP 和源码 ZIP 的长度、SHA-256 与四仓提交。runtime 为 0.1.3，Hermes connector 为 1.5.4；安装器会强制重装包内对应版本，不能仅按包版本号判断此次更新是否已经安装。

- Windows amd64、Linux amd64、macOS arm64 helper 均使用 Go 1.26.8 构建，目标文件格式核对通过；Linux 版本为静态链接。
- 两个 wheel 共 37 个源码/资产文件与当前源码逐字节一致。
- 三个安装包的 `install.py --check-only`、四个 ZIP 的 CRC 与清单哈希核对通过。
- 源码 ZIP 从已提交的 Git 对象导出，排除实际环境文件、数据库、私钥和本地测试身份；历史邀请 PDF 未更新。

已有用户按[升级步骤](../../tools/release/early_access/README.md#已有客户端升级)保留原身份与数据目录，更新 helper、runtime、connector，并使用同一控制台 URN 加 `--allow-web-actions` 重新配对。服务器不会替已有配对自动增权。

## 验证与数据保留

- 本地 Web 171 项测试及生产构建通过；正式镜像的 `npm ci` 审计为 0 项漏洞。Runtime、Hermes、双向好友、真实 Go 网络、完整 Web 链路及浏览器操作的验证结果见上面的能力验证记录。
- Linux Web 候选使用独立数据库、随机密钥和仅监听本机的测试端口，不连接生产 Platform。注册、重复邮箱拒绝、长密码错误后缀拒绝、正确登录、HttpOnly 会话、匿名与伪造会话拒绝、工作台/通知页及引用资源通过。
- 重启同一候选后，既有签名会话和再次登录验证通过。Linux Platform 候选禁用外部网络，健康检查、UID 10001 与身份重启保留通过。
- 切换前保存旧镜像、源码配置、下载包、平台身份及在线一致性 SQLite 备份；短暂停止 Web/Platform 写入后再做最终 SQLite 备份，按固定提交快进更新并切换镜像。
- 生产 Web 与 Platform 分别以 UID 1001、10001 运行；三个服务无异常重启或 OOM。四个数据库完整性检查通过，原账户、连接、加密配置、平台身份和命名卷保留，后台同步已恢复成功响应。
- 公网 5 个入口及 HTML 实际引用的 14 个 JS/CSS 资源返回成功，Service Worker 与发布源码的 SHA-256 一致；标准 TLS/主机名验证及 HSTS、SAMEORIGIN、nosniff 检查通过。6 个匿名私有 API 均返回 401 与 `no-store`；清单发布标识、四仓提交及 4 个 ZIP 的长度和流式 SHA-256 全部一致。
- 验收结果与下载校验记录保存在本次发布目录，见下节。未创建生产测试账户、使用真实用户凭据或发送业务测试消息；本次没有新增真实模型调用验收结论。

Hermes 的系统通知历史条目仍受宿主撤回接口限制；业务待办、共享已读和后续提醒按 agent 状态同步。实际用户的新增好友、发消息及协作能力需要安装对应本地组件后使用。

## 记录与回滚

服务器发布目录：`/root/agent-comm-releases/agent-web-parity-20260917-17490d9`。

备份目录：`/root/agent-comm-backups/agent-web-parity-20260917-17490d9`，访问权限限 root；`final/` 保存切换前停止写入后的最终 SQLite 备份。发布目录保存源码增量、候选报告、部署脚本/检查点和内部验收结果。本地证据在忽略目录 `build/releases/agent-web-parity-20260917-17490d9/`。

旧镜像已保留为：

- `agent-web:rollback-agent-web-parity-20260917-17490d9`，镜像 ID `sha256:d33361259f606a6849d43d39b6984525269bfbcc302214637e6db873bffc2cc7`。
- `agent-platform:rollback-agent-web-parity-20260917-17490d9`，镜像 ID `sha256:20323a12f31faeac021a79b8458dfb43ef9e4fc223b96075a6ac6fb43e8e5a3c`。

如需回滚，将上述旧镜像重新标记为 `agent-collaboration-deploy-web:latest` 与 `agent-collaboration-deploy-platform:latest`，在原部署目录执行 `docker compose up -d --no-deps --no-build --pull never platform web`，验证服务后检查并 reload nginx。按备份记录恢复对应源码与下载文件。保留实时数据库、原身份和 `.env`，不要直接用历史数据库备份覆盖升级后的用户写入。旧 Web 已包含 scrypt 登录支持。
