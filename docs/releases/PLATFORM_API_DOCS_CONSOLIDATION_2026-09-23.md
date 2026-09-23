# 2026-09-23 Platform API 文档归并

云端 Platform HTTP API 的现行契约移入 Platform 仓库的 [`docs/guides/API.md`](../../agent-comm-platform/docs/guides/API.md)，另提供 [English reference](../../agent-comm-platform/docs/guides/API_EN.md)。官网用统一阅读器展示两份原文；旧 `/docs/api` 和 `/docs/api/` 返回 308，转向 `/docs/?path=platform/guides/API.md`。Platform 单独部署的旧 `/docs` 入口也转向官网参考。重复的内嵌 HTML 页面已删除。

## 上线源码与镜像

| 仓库 | 运行代码提交 |
| --- | --- |
| Deploy | `75ee0836e5c7c107e9ded384ab5761d1ad3ee5f7` |
| Web | `dfb3e7b8776971134f594d9206e6201e58c3f3bd` |
| Platform | `b80c2f38a5c61ee2f76bbadf460a15f411208887` |
| SDK | `d8adfade59cbf1b0bcc979c762eec2ad9d466c4c` |

| 运行容器 | 镜像标识 |
| --- | --- |
| nginx | `sha256:311761cac6bbc23041f3f4302699b0b5d0614e0a4d28b70def415e7bf16050c1` |
| Web | `sha256:270473f9f1c0ebcc02c44f63f3b15fb65c14c9c8d74e1032567827afdeaba9db` |
| Platform | `sha256:ac39c494245b7672c9e385c067da28a1691b39df0b2753b08f8466c823a1ba80` |

本记录及发布索引会在运行代码提交之后作为根仓库的纯文档提交发布；表中 Deploy SHA 是实际切换服务时的代码指针。本次未修改数据结构，也未重新发布官网安装包。

## 备份、切换与检查

- 切换前备份在服务器 `/root/agent-comm-backups/2026-09-23-api-docs-consolidation`。四个 SQLite 数据库以在线备份方式保存并通过 `quick_check`；配置和 Platform 身份密钥也已备份、校验。切换前 Platform 镜像保留了独立标签。
- 源码检出核对了四仓精确提交；nginx 配置预检通过。生产环境使用 Go 1.26.8 对 `internal/api` 的 `TestBootstrapAndStatusEndpoints` 定向运行通过，并完成 Platform 镜像构建。
- 仅重建了 Platform 和 nginx 容器。Web 镜像与持久卷未变。
- 生产环境 smoke 通过：统一阅读页与中英文 Markdown、旧 URL 的 308、未知与历史文档的 404、`/healthz`、公开 Registry 读接口、未授权 MQ ACK 的 401、登录与下载入口、容器和镜像版本。三个容器运行且重启计数为 0；身份密钥未变化，Web 与 MQ 数据库 `quick_check=ok`。
- 从公网再次核对 `/docs/`、两份 API Markdown 均返回 200，旧 `/docs/api/` 返回 308 到新阅读页。

上述检查不等同于重新执行真实双 Agent 协作或首次安装验收。需要回退时，恢复切换前源码提交和保留的 Platform 镜像，再重建 Platform 与 nginx；保留当前生产卷、身份密钥和后续写入数据，不用备份数据库覆盖新写入。
