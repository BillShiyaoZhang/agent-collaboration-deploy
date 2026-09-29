# 用户情境引导与 Web 部署（2026-09-29）

## 交付范围

从首次注册、Hermes 首装和一次性链接、已有安装续接、好友与合作邀请、对端内容审核、状态判断、权限不足、离线恢复，到撤销配对和删除账户，核对并补齐了官网、Web、用户指南及 agent skill 的入口和边界。修正了 Web 手工连接保存时的授权说明、一次性领取失败提示，以及过时的文档导航描述。2026-09-28 隔离 Agent 与 Hermes 的现场往返、冲突和序号修补限制记录在[验收文档](../verification/HERMES_PEER_SCENARIOS_2026-09-28.md)。

本次源码组合的部署代码提交为根仓库 `fb931fb20fe26fe83af5d30ac08195898b56014e`、Web `a0ebb169b233d30f753c70701ddcad25fc1cc298`、Platform `407ed72b4fdf1c42f25e3afe56e0de9308813c25`、SDK `e2f6fce544f8dcf8523fcacb70184d51c3749a14`。四仓 GitHub 和本地只保留 `main`，根仓库按 Web、Platform 和嵌套 SDK 的固定提交引用。此记录本身是部署后的文档提交。

## 构建、备份与切换

Web 在本机 Docker Desktop 上按 `linux/amd64` 构建；`npm run build` 和相关测试 28/28 通过。Web 全量测试 387/388 通过，剩余一项是 Windows 沙箱下的 POSIX 文件权限断言，未在 Linux 环境复跑。根仓库早期接入包测试 44/44 通过，文档结构检查 155 个 Markdown、0 错；fake Hermes 的配置测试夹具改用标准库读取原有 JSON 配置，避免沙箱中不可读的 PyYAML 造成假失败。SDK Go 全量和 Python runtime 208 项测试通过；Hermes connector 测试因本机缺 `aiohttp` 未运行。

Web 镜像 ID 为 `sha256:5c561a3a83c2ed8ea1b1e9147810a825f0ff08a1cd975ffbfa5a1edf8e2d97fb`，OCI revision 为完整 Web 提交。上传到 ECS `i-0jleb7de83gsnoa0yuc2` 的压缩镜像归档大小为 191,463,632 字节，SHA-256 为 `61619e1ea260003e1677483e18d3695bc1c64a62f207a8acf76b759e47271852`，云端重新计算一致。原 Web 镜像保留为 `agent-collaboration-deploy-web:rollback-20260929-before-guidance`。

切换前以 SQLite `.backup` 为当前 Web `prod.db` 建立一致性快照，`PRAGMA quick_check=ok`，备份 SHA-256 为 `ad5a4a5948969175d185f226bde53b29961ed5848544a85a02cf680ec8e44f4f`；私有位置为 `/root/agent-comm-releases/guidance-20260929/backup/`。生产库未由备份覆盖；Platform 数据卷和身份未修改。服务器源码按上述提交和子模块更新，只以 `docker compose ... up -d --pull never --no-deps --no-build --force-recreate web` 替换 Web。Nginx 配置检查通过后重载；Platform、Nginx 容器未重建。

## 切换后证据与限制

2026-09-29 北京时间 20:20 左右，Web 容器为目标镜像、`running` 且重启数 0；Nginx 和 Platform 容器持续运行。官网首页、登录页、文档入口均返回 HTTP 200，Web 生产 `prod.db` 的 `PRAGMA quick_check=ok`。内置浏览器实际读取到首页的链接过期/配对未完成恢复说明、现行合规披露说明和新版用户情境导航。上述网页与只读检查不等于一次新的完整 Hermes 首装、内容审核或双方业务任务验收。

本次**没有**重建 Platform 容器，也没有发布新的 SDK 接入包。公网下载清单仍为 `v0.9.6`，指向本次以前的四仓提交；SDK 新源码和 skill 不能当作现有安装的运行版本。SDK 的序号修补仅在少量积压的隔离场景验证：Platform 每个 URN 默认 500 条队列、单次读取 4 MiB 上限下，控制包可能无法准入或被检索窗口遮住。发布新版公开包还须验证运行中 Hermes 认证的 `peer_content_safety` 三字段，并完成满队列与 4 MiB 边界的端到端方案；不能以源码提交、轮子安装或 MQ ACK 代替这些结果。
