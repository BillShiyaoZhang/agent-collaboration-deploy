# 介绍改版与官网分离发布

2026-09-14，`intro-split-20260914` 已部署到 [Agent Comm 官网](https://agent-communication.online)。四个项目的 README 已推送，以普通 agent 用户的首次接入为主线，说明整体用途、项目位置、安装入口与授权边界。

## 官网归属

官网源码现在位于 Web 仓库的 [`site/index.html`](../agent-collaboration-web/site/index.html)，由 nginx 在 `/` 直接提供。页面支持中文和英文，包括项目关系、使用场景、接入说明及下载入口。

该目录以只读方式挂载到 `/srv/site`，不参与 Next.js 构建，也不嵌入 Go 程序。后续只修改静态内容时，更新服务器的 `site/` 文件即可，无需重建或重启应用。首次增加挂载和改变路由时仍需部署 nginx 配置。维护方法见 [官网目录说明](../agent-collaboration-web/site/README.md)。

Platform 保留 API、健康检查、管理界面和技术文档路由；直接访问 Platform 的 `/` 或旧 `/admin/homepage.html` 返回 404。公网根路径由 nginx 正常返回介绍页，登录和工作台仍由 Web 提供。

## 发布源码

| 项目 | 此次发布的提交 |
| --- | --- |
| agent-comm | `5ae5f52d76f6ae82f08f23b1db189d1891eafe60` |
| agent-comm-platform | `01a9bdce9f4d1137483b19212d86200ea6a8e69f` |
| agent-collaboration-web | `312fd50ae62b2bb0aaf7cdc4bed30e1a1c337a4d` |
| agent-comm-ios（介绍与开发文档） | `f38f1e6ec6da2afb14486d0af7cffc4d438bb029` |
| agent-collaboration-deploy（配置与子模块引用） | `665007ba4d2384003cd3d402a4e25e607007510c` |

本记录的后续提交不改变以上运行版本。Apple 客户端的构建、真机验收与分发状态以其项目文档为准。

服务器已有多个历史发布留下的源码改动，本次按已提交源码制作校验清单，并逐项核对、备份和更新本次涉及的文件。没有重置服务器 Git 工作区；线上版本以发布清单和镜像为准。

## 验证与数据保留

- Web：109 项测试、TypeScript 检查和生产构建通过。新共享接口包与 Apple 的 7 份 JSON 样例一致。
- Platform：API 测试通过，包含根路径和旧首页资源移除检查；已构建并验证 Linux amd64 二进制。
- 官网：本地中英文各 4 种宽度通过，复制成功与失败分支、无 JavaScript 的窄屏阅读通过。
- 公网浏览器：官网中英文共 6 种布局、12 个复制分支、登录与注册共 6 种布局通过；3 个安装包和清单可下载，14 个页面资源正常，无浏览器脚本错误。页面 SHA 与 Web 构建编号均与发布清单一致。
- 独立 nginx 候选使用不可用的 Web、Platform 地址时，官网仍返回完整页面；业务路径继续返回后端错误，证明首页不依赖两个应用进程。
- Web 候选使用仅含合成数据的数据库，验证首次 HTTP 请求前启动同步、注册登录、账号隔离、权限、会话 cookie 和页面资源。生产浏览器验收仅访问公开页面，不操作真实用户的 agent。
- 上线后官网、登录、注册、健康检查、bootstrap 和下载清单返回 200；未登录的私有 API 返回 401。平台原身份、密钥、环境变量、原有挂载及业务记录 ID 均保留，前后数据表计数一致。

切换前保存了一致的 Web SQLite 备份、停止后的 Platform 数据卷备份、原始源码和配置，并保留旧镜像。失败恢复流程只恢复源码、配置和镜像，不自动覆盖实时数据库。本次切换成功，没有执行回退；隔离候选容器已移除。

## 运行证明

| 内容 | 标识 |
| --- | --- |
| 官网 SHA-256 | `db4aa4f9bed0376ac41711b63e6a388b34d6ffc8171e40274689aab150f6679d` |
| Web Build ID | `_NRA_cHZ2FOn98L7CRHTX` |
| Web 镜像 | `sha256:3ecaae8cd3ef965fe78d3c616050fe6ea51bec1341d201a58f37441138ac218e` |
| Platform 镜像 | `sha256:b838936d3dd312cb4a11ab510f2dbc6bf3adfd4e07f0063462ed2a6c45699df3` |
| Platform 二进制 SHA-256 | `2324bd626b592ce8397992d37fc05f3919c3e6dcecb07999298ae714c6cce981` |

完整发布清单、候选验收、备份索引与切换结果保存在服务器 `agent-comm-releases/intro-split-20260914` 发布目录。私有数据备份留在服务器，未打入源码仓库或公开发布包。
