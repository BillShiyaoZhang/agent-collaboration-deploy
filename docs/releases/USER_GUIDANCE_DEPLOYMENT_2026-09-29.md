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

首次 Web 切换时没有重建 Platform 容器；随后经用户明确允许，Platform 也按下节补充更换。本次没有发布新的 SDK 接入包。公网下载清单仍为 `v0.9.6`，指向本次以前的四仓提交；SDK 新源码和 skill 不能当作现有安装的运行版本。SDK 的序号修补仅在少量积压的隔离场景验证：Platform 每个 URN 默认 500 条队列、单次读取 4 MiB 上限下，控制包可能无法准入或被检索窗口遮住。发布新版公开包还须验证运行中 Hermes 认证的 `peer_content_safety` 三字段，并完成满队列与 4 MiB 边界的端到端方案；不能以源码提交、轮子安装或 MQ ACK 代替这些结果。

## 同日 Platform 容器补充更换

Platform `407ed72` 相对原运行镜像标注的 `ba779d1`，自身源码只变更 SDK 子模块固定提交；服务端调用路径没有相应代码变更。本机官方 Go 1.26.8 容器中的 `go test ./...` 全部通过，管理台测试 39/39 通过。从固定 Platform 与 SDK 提交在本机 Docker Desktop 构建的 Linux/amd64 镜像 ID 为 `sha256:7cafa719c1ddc0ef3e1a5f7ab44cc03277af1811e0aba9d4887fdc4841a2673b`，OCI revision 为上述完整 Platform 提交，SDK revision 为上述完整 SDK 提交。镜像内 Platform 二进制 SHA-256 为 `cf04d90e929161414ec18bf14cc3d0af5e4db79184cbc508ccca691c5dc85364`，与旧运行二进制的 `dd5f264d24e10e3bb8f4a69264c93b2c9434203f7e17dcf26e5492b3a961a696` **不同**，因此不以源码差异推断字节相同。压缩镜像归档大小 24,756,017 字节、SHA-256 `bc7f4038c45df1ed6c94fabfa8beb24cc20f8cf8e7b786b172ef04dac3b146f8`，云端重算一致。

切换前在私有 `/root/agent-comm-releases/guidance-20260929/backup/platform-pre-switch/` 中新建当前 Web SQLite 在线快照，以及 `.env` 和外部 v2 配置、策略与密钥归档。随后短暂停止原 Platform，三库 `PRAGMA quick_check=ok` 后完整归档 `platform_data`，包含数据库、身份密钥、管理策略及当时存在的 WAL/SHM；归档为 776,918,131 字节，SHA-256 `357afdf239c7593ece919e4a3fd0a081fbd9a748dd1b837a750cd1ce929475e3`，`gzip -t` 和 tar 全量列表均通过。原容器在备份后先恢复运行。旧镜像 `sha256:87799b78e0d51b067759c498bd1bb9deda900e8c0b243bb62be45d49cd7abea1` 保留 `rollback-20260929-before-guidance` 标签；归档及配置备份仅 root 可读。未把备份覆盖实时卷。

北京时间约 20:51，在保留签名 v2 Compose 覆盖文件及原数据卷的情况下，仅重建 Platform 容器，然后检查并重载 Nginx；Web 和 Nginx 容器未重建。切换后 Platform 为目标镜像、`running`、重启数 0，原配置、v2 策略/公钥/网关与回执私钥只读挂载及 `/data` 命名卷均存在。公网 bootstrap 的 Peer ID 仍为 `12D3KooWNApwdxwbXY27N44cGxTXY15Hn8yRx9m9Yw5St5A7kTpK`；签名策略原字节 SHA-256 仍为 `6f9f7bdf26c5e7761cbe8c451a22fd11f9a448d912fa5bc3ae61c1e53f3ff5c4`，epoch 3、`compliance`、`allow_v1=false`。Web、Registry、MQ、审计四库再次 `quick_check=ok`；首页、登录、文档、`/healthz`、bootstrap、v2 policy 均返回 HTTP 200，三个服务容器持续运行且重启数 0。新 Platform 近十分钟日志中未匹配到 `panic` 或 `fatal`；这些只读检查不代替新的双方 Agent 业务验收。

## 同日补充：聊天中 `@事项` 的授权引导

用户在手机聊天页指出，原提示虽说明缺少事项读取能力，却没有给出授权入口。Web `3074339ce647d94b7be232c10d2909e69c7ea841` 将 `@` 提示按政策暂停、待核验、离线、需要恢复配对和方法缺失区分，并链接到**当前 Agent** 的连接设置；该页自动展开说明、控制台 URN、预览和执行命令。默认选中的基础范围包含 `task.list` 与 `task.detail`，只有用户主动选“含网页操作”时，命令才带 `--allow-web-actions`。页面明确重配会替换原方法和期限，原有自选方法需逐项保留；网页本身不改变本机授权。用户和接入包说明同步修正默认方法列表及原设备、原 profile 的恢复步骤。

本机 `npm run build` 无警告通过，`task-mentions.test.cjs` 2/2 通过，文档结构检查 156 个 Markdown、0 错误。Web 与根仓库提交推送至各自 GitHub `main`；云端源码固定在根 `755a24ca41950bb8e86f0eb875ecd081308f5610`、Web `3074339`，Platform 与 SDK 固定提交未变。Linux/amd64 Web 镜像 `sha256:64722b2f16e9bac30db7f3754c7c62f8526c5fef685d32412bc26449697169d7` 的 OCI revision 为完整 Web 提交。上传归档为 191,469,187 字节，SHA-256 `cfbc015c83913a90882ff5fc277155007135788adc7e7c51ce13a3713b987b01`，云端哈希和 `gzip -t` 均通过。

切换前以 SQLite `.backup` 为卷内实际 `prod.db` 建立私有一致性快照 `/root/agent-comm-releases/mention-guide-20260929/backup/prod-verified.db`，`quick_check=ok`，SHA-256 `cb23b6ec2d4116a1d0bda9d3f02cd077cd97d43aaa1bf2007528336900ba4829`；原运行 Web 镜像另标为 `agent-collaboration-deploy-web:rollback-before-3074339`。仅用签名 v2 Compose 组合重建 Web，Nginx 检查后重载。北京时间约 22:20，Web 已运行目标镜像且重启数 0；Platform 与 Nginx 容器启动时间未变。首页、登录、文档及健康检查返回 200；未登录聊天入口返回预期的 307。切换后生产 `prod.db` 首次直接检查遇到短暂锁，稍后使用 10 秒忙等待重试得到 `quick_check=ok`。

内置浏览器在既有账户中实测：聊天输入 `@` 后出现“查看此 Agent 的授权步骤”，链接准确指向该 Agent 的 `/dashboard/connections?agent=…&guide=task-mentions`；到达后步骤已展开，默认预览与执行命令均不含 `--allow-web-actions`，切到“含网页操作”时两条命令才加入该参数。按手机布局尺寸再次查看引导卡；没有运行配对命令、扩大该账户或 Hermes 的权限，也没有发送聊天。此验收证明网页引导和部署生效，不证明该 Agent 已获得事项读取权限。

## 晚间补充：区分方法未列出与已列出但未开放

在该用户连接的实际能力快照中，`task.list`、`task.detail` **未列出**，而“未开放的功能”只列出其它四个方法；这不足以断定单纯重配就能恢复 `@`。Web `21693d1556111a94de7c09abd614d91398f82c03` 的连接引导因此根据最新能力结果明确区分“未列出”（先核对原设备接入组件支持情况）和“已列出但未开放”（核对适配器和配对范围），用户指南与技术参考同步更新。网页仍不自动增权。`npm run build` 无警告通过，文档结构检查仍为 156 个 Markdown、0 错误。

最终 Linux/amd64 Web 镜像为 `sha256:a8670c4616ef636ef1e3268f39fb26d45871f8ef044429f7aa88673b399f77bb`，OCI revision 对应完整 Web 提交。压缩归档 191,473,451 字节，SHA-256 `e46270981e343efca0e9c7bb968cafd1ccfac40f66b9b4a52e6cdff09a04c1bd`，云端重算和 `gzip -t` 通过。二次切换前为当时实时 Web `prod.db` 再做一致性快照 `/root/agent-comm-releases/mention-guide-20260929/backup/prod-before-21693d1.db`，`quick_check=ok`、SHA-256 `aa0c4c4ce0d683fac9122c9a39e8963fe8d43d425e9f0d8a5f81d21e40d72662`，并把第一版 Web 镜像单独标为 `rollback-before-21693d1`。

云端源码当时固定在根 `a4ed3f61a48b0694f7732a3e653f03dbc9e12857` 和 Web `21693d1`；只重建 Web，Nginx 通过配置检查后重载。北京时间 23:12 左右 Web 为最终镜像、`running`、重启数 0；Platform 与 Nginx 容器启动时间未变。首页、登录、文档及 `/healthz` 返回 200，未登录聊天入口返回预期的 307，生产 Web `prod.db` 的 `quick_check=ok`。内置浏览器在该用户连接上实际读到“最近的能力结果未列出 task.list、task.detail”的新版指引和默认基础范围命令。未在用户 Hermes 原设备升级或重配，故当前事项引用权限仍未恢复。切换后服务器根盘约剩余 2.0 GB（使用率 95%）；后续镜像发布应先整理旧产物，同时保留必要的回滚镜像和数据库快照。本段部署记录提交后，服务器根仓库还需同步到该记录的最终 `main` 提交。
