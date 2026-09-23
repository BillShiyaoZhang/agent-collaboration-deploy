# 2026-09-23 官网文档入口统一上线

本次将官网按角色阅读的文档入口统一到 [`/docs/`](https://agent-communication.online/docs/)，Platform API 文档放在 [`/docs/api/`](https://agent-communication.online/docs/api/)。旧 `/guide/` 返回 308，转向 `/docs/`。官网通过只读挂载直接读取部署仓库、Web、Platform 和 SDK 四个仓库各自 `docs/` 中允许公开的 Markdown；文档原文仍由所属仓库维护。

## 初次上线的源码组合

| 仓库 | 初次上线提交 |
| --- | --- |
| Deploy | `868266c` |
| Web | `5602057` |
| Platform | `b3235ff` |
| SDK | `d8adfad` |

初次上线后追加了 Platform API 文档准确性补丁。上表保留首次切换的版本；补丁后的**运行代码指针**如下。根仓库此后仅为本记录及索引做文档提交，因此该文档所在的根仓库提交会晚于运行代码指针，不代表服务器又执行了一次代码切换。

| 仓库 | 补丁后的运行代码指针 |
| --- | --- |
| Deploy | `c1e29b46b6a713b386f3342bd556c3144ed8fcf0` |
| Web | `5602057db6398171e5bbb1be2cddc6c0ba4d7b3a` |
| Platform | `f1714e81a38cd5d93c795b68542cef24af9d4377` |
| SDK | `d8adfade59cbf1b0bcc979c762eec2ad9d466c4c` |

| 运行容器 | 镜像标识 |
| --- | --- |
| nginx | `sha256:311761cac6bbc23041f3f4302699b0b5d0614e0a4d28b70def415e7bf16050c1` |
| Web | `sha256:270473f9f1c0ebcc02c44f63f3b15fb65c14c9c8d74e1032567827afdeaba9db` |
| Platform | `sha256:db876af799c7e59ddd6e0c2c807670f8abbde844f447df57eb992c22e4bcf3af` |

## 备份、切换与验证

- 切换前备份保存在服务器 `/root/agent-comm-backups/2026-09-23-docs-unify`。四个数据库完成在线备份，并运行 `quick_check`。
- 初次切换时重建了 nginx、Web 和 Platform 三个容器；身份与密钥保持原值。生产环境和公网 smoke 通过。
- API 文档准确性补丁只重建 Platform，并重新加载 nginx。补丁上线后的生产与公网 smoke 通过：核对了最新 API 文案、`/docs/`、源 Markdown、旧 `/guide/` 的 308、健康接口、登录页、下载入口、运行镜像与容器、身份和密钥一致性；Web 与 MQ 数据库的 `quick_check=ok`。
- 上述 smoke 结果不等同于真实 agent 协作、首次安装或业务端到端验收。
- 本次未重新发布官网安装包；公开下载的安装包版本应以[官网发布清单](https://agent-communication.online/downloads/release-manifest.json)为准。

回退需以本次服务器备份和切换前镜像为依据，并保留当前生产身份、密钥与后续写入的数据；不要用历史数据库覆盖新写入。
