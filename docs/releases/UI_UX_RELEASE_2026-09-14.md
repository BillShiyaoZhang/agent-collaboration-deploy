# Web UI/UX 发布记录 · 2026-09-14

> 历史发布记录：正文中的版本、状态、路径和验证结论对应此次发布，保留原始证据；现行操作见 [部署指南](../operations/DEPLOYMENT.md)，后续版本见 [发布索引](README.md)。本次目录整理仅迁移文档和链接，不表示重新部署。

状态：已部署至 [工作台](https://agent-communication.online/dashboard/agents)，公网浏览器验收通过。用户明确要求“推送 部署”。

## 版本及范围

- Web 提交：`ea442431dcb41cec7bbd0061fbfba6bf97b33701`，已推送至 Web 仓库 `main`。
- 部署仓库版本引用提交：`8501ff54d5855ef5c07b95a0ff068f7e0c0ca809`，已推送至部署仓库 `main`。
- 镜像标签：`agent-collaboration-web:ui-ux-20260914-ea44243`。
- 镜像 ID：`sha256:df6c3beb9030549e707fa42599824369351f7ee784db993147ca394e5672fbbe`。
- Next Build ID：`Nfi-xhd7D1qv-M4pRB2rb`。
- 服务器发布目录：`/root/agent-comm-releases/ui-ux-20260914-ea44243`。

本轮更新应用式导航、响应式布局、中文登录注册、连接卡片、配对步骤、远程会话和状态反馈。依赖、数据库结构、平台服务及安装包保持原版本。下载区的源码 ZIP 仍是早期试用快照，最新 Web 源码以 Git 提交为准。

## 构建及切换

服务器发布前剩余磁盘约 895 MB，内存 2 GB 且无 swap。本轮沿用已验证的小型运行产物发布方式，没有在服务器重新安装依赖或执行完整 Next 构建，也没有清理历史镜像、数据卷或备份。

本地生产构建通过后，从已推送提交导出源码，统一文本换行为 LF，并打包完整 `.next` 运行产物，排除构建缓存、类型文件、standalone 依赖副本及追踪文件。压缩包 942,842 字节，SHA-256 为 `41d17061ff633273eeea633d64a25bfda7b8f4c988218f4bd659e876f626370b`。

上传使用现有阿里云 Workbench 通道。匿名 GitHub API 确认 Web 仓库公开；包中没有生产环境文件、数据库或凭据，`.env.example` 为公开配置模板。解压后逐文件校验 SHA-256。

候选镜像从实际运行的早期试用 r2 镜像派生，替换 Next 运行产物，保留旧静态分块供已打开页面继续加载。Linux 依赖、Prisma 原生模块和原启动入口保持。核对锁文件、Next 配置、数据库 SQL 与基线一致，实际版本为 Next 14.2.35、React/React DOM 18.3.1、Prisma Client 5.22.0。

先在独立空数据库、独立随机密钥、仅监听 `127.0.0.1:3301` 的候选容器内验收；候选无法访问真实 agent 平台。通过后停止并移除候选容器，备份生产 SQLite 与改动源码，只重建 Web 并 reload nginx。

两次切换被验收脚本自动回滚：首次错误要求服务端 HTML 包含客户端渲染的登录标题；第二次直接比较 Docker 返回的无序挂载列表。分别改为等待正确 Build ID、按挂载路径排序后比较。最终切换及全部检查通过，两次回滚均保留了实时数据库，尝试记录保存在备份目录。

## 验证结果

- 本地：63 项 Node 测试、TypeScript、lint、Next 生产构建通过；连接、配对、会话轮询与窄屏交互浏览器检查通过。
- Linux 候选：独立账户注册、错误密码拒绝、正确登录、Secure/HttpOnly 会话、会话查询、分块 cookie、伪造会话拒绝、未授权访问拒绝、空连接列表通过。
- Linux 候选：登录、注册、连接页面及其 19 个 Next 资源返回 200，备案图片正常；没有缺失模块或 Prisma 初始化错误。
- 公网：登录、注册、健康检查、认证 providers、备案图片及现有下载清单返回 200。服务端 Build ID 与候选一致。
- 实际 Chrome：严格 HTTPS 校验下，新版中文页面完成渲染，密码显示切换及登录到注册页的导航正常；1440 px、390 px、320 px 布局检查通过，无横向溢出、脚本异常或页面静态资源错误。
- 数据：SQLite 完整性检查通过，既有记录 ID 保留；切换前后 User 5、Agent 3、Contact 1、Message 7、HITLRequest 0、Transaction 0、ControlRequest 2。
- 配置：Web 环境变量指纹、数据挂载、Compose/nginx/platform 配置及 `.env` 指纹保持；platform 和 nginx 的容器 ID、镜像与配置保持。
- 服务器全部已发布源码文件与 Web 提交对应的清单一致。服务器 Git 元数据仍承接此前快照部署，运行版本以镜像、Build ID 和发布清单为准。

没有使用生产用户身份进行浏览器测试或创建生产测试账户，没有发送真实 agent 消息。远程会话的交互验证使用本地隔离响应；本次发布不新增真实模型端到端验收结论。

本地证据在忽略目录 `build/ui-ux-release/`；服务器保留 `candidate-test.json`、`backup.json`、`manifest.json` 和 `deploy-result.json`。

## 回滚

最终切换前备份：`/root/agent-comm-backups/ui-ux-20260914T113658Z`，包含 SQLite 在线一致性备份、改动前源码、Compose/nginx 配置及回滚元数据。

旧镜像：`agent-collaboration-web:rollback-ui-ux-20260914-ea44243`，ID 为 `sha256:37cc9d7a4356f4da72153061a9cb4c7bde588a642bcd44c051edb8ee6b5c8c6a`。

需要回滚运行版本时，在现有部署根目录将该旧镜像重新标记为 `agent-collaboration-deploy-web:latest`，执行 `docker compose up -d --no-deps --no-build --pull never web`，然后检查并 reload nginx。按备份清单恢复改动源码；保留实时数据库，不直接用备份覆盖。历史回滚标签和此前发布备份保持可用。
