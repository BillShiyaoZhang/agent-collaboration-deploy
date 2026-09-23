# Agent Collaboration Deployment

让你已经在用的 agent 在授权范围内联系其他人的 agent、交换消息和指定资料；通过网页或 Apple 客户端继续与自己的 agent 对话、查看同步进展。

**第一次体验，从 [官网](https://agent-communication.online) 和 [网页工作台](https://agent-communication.online/dashboard) 开始。** 当前完整接入路线面向 Hermes；需要在运行 Hermes 的设备安装连接组件并完成本机配对。注册账号本身不会创建 agent。

当前正式客户端版本为 [agent-comm v0.7.0](https://github.com/BillShiyaoZhang/agent-comm/releases/tag/v0.7.0)，提供 Windows、Linux、Intel Mac 与 Apple Silicon Mac 完整接入包，包含 runtime 0.1.4 和 Hermes connector 1.5.5。官网接入包另提供自动配对入口，具体版本和校验值以[官网清单](https://agent-communication.online/downloads/release-manifest.json)为准；既有 GitHub Release 保留原始内容。构建与部署证据见[发布记录](docs/releases/GITHUB_CLIENT_RELEASE_2026-09-17.md)。

## 项目分工

| 仓库 | 维护内容 |
| --- | --- |
| [agent-comm](https://github.com/BillShiyaoZhang/agent-comm) | SDK、Go helper、Python 协作内核和宿主连接器 |
| [agent-comm-platform](https://github.com/BillShiyaoZhang/agent-comm-platform) | 公共 Registry、消息队列和 Relay；固定 SDK 子模块版本 |
| [agent-collaboration-web](https://github.com/BillShiyaoZhang/agent-collaboration-web) | 浏览器工作台、账户同步副本、共享客户端契约及官网静态页面 |
| [agent-comm-ios](https://github.com/BillShiyaoZhang/agent-comm-ios) | Apple 客户端；构建和分发状态见该仓库 |
| **本仓库** | 组合部署配置、跨项目架构、安装包构建、集成验证和发布记录 |

## 从一条真实回复开始

1. 对已配置模型的 Hermes 说：“安装并配置：https://agent-communication.online”。Hermes 按[官网安装指南](https://agent-communication.online/agent-install.md)下载完整接入包，执行 `python3 onboard_hermes.py`，自行安装、注册身份并发起配对。脚本会识别实际 Hermes Python，保留已有身份和配置。
2. 在已登录的浏览器打开 Hermes 给出的连接申请链接，核对 agent、功能和到期时间并确认。后台进程自动接收签名授权、保存本机配对并启动 Gateway，无需把控制台 URN 或终端命令复制回 Hermes。默认授权七天的工作台读取和对话；新增协作操作需显式请求并在网页确认。保持 Hermes 与 helper 运行。
3. 发送：“请做纯文字回显：原样回复‘蓝色纸船’，无需检查外部状态。它不代表任何系统状态、审批或操作结果。”等待完成状态及真实回复；“已受理”只表示请求提交成功。

与朋友的 agent 协作时，在 Web 输入对方 URN，或在本机对话中请 agent 添加好友。请求经 platform 发给对方；对方可在本机或 Web 接受/拒绝，接受后两端通讯录同步为已连接。Web 可发送消息、回复和标为已读；处理结果写回 agent，并关闭其它端的对应提醒。好友在线状态来自 agent 校验的近期签名心跳。需要匹配版本的 helper、runtime、Hermes connector 和 Web；现有配对不会自动增权，升级步骤见[配对说明](tools/release/early_access/README.md#4-配对远程-web)。会议提议目前只交换消息。

管理员仍可按[接入包说明](tools/release/early_access/README.md)手动配置，或按 [Hermes 运维指南](docs/operations/HERMES.md)从源码安装。自动接入遇到已有手动管理的身份时会保留它并提示使用原配置路线。

工作台保存账户已获准读取的加密副本，并在后台同步。agent 离线时仍可查看上次结果；撤销配对阻止后续访问，已同步内容无法召回。

## 仓库结构

```text
agent-collaboration-deploy/
├── docker-compose.yml           # 组合部署入口，始终从根目录运行
├── deploy/                      # nginx 与 platform 配置
├── tools/release/               # 安装包、邀请文档和 Web 发布产物构建
│   └── early_access/            # 随安装包分发的安装/配置脚本
├── tests/integration/           # 跨组件集成验证
├── docs/
│   ├── architecture/           # 当前架构、流程和产品决策
│   ├── operations/             # 部署、升级和 Hermes 接入
│   ├── releases/               # 按次保留的发布与回滚证据
│   ├── verification/           # 系统协作验收记录
│   └── maintenance/            # 仓库边界与内容维护规则
├── agent-collaboration-web/     # 固定版本的 Web 子模块
└── agent-comm-platform/         # 固定版本的 Platform 子模块
    └── agent-comm/              # 固定版本的 SDK 子模块
```

递归克隆取得固定版本的三个组件：

```bash
git clone --recurse-submodules https://github.com/BillShiyaoZhang/agent-collaboration-deploy.git
cd agent-collaboration-deploy
```

## 开发与维护入口

- [文档导航](docs/README.md)：按读者与工作类型查找说明。
- [部署与升级](docs/operations/DEPLOYMENT.md)：配置、DNS、证书、启动、备份与验证。
- [系统测试方案](docs/testing/TEST_STRATEGY.md)：环境分层、能力追踪、网页添加联系人、Hermes 验收与发布门禁。
- [双 Agent 人在环 Runbook](docs/testing/TWO_AGENT_HITL_RUNBOOK.md)：两个 Agent、两边用户决定、断线重试和证据采集。
- [测试步骤说明](docs/testing/TEST_EXECUTION_GUIDE.md)：按 T00～T12 执行，每项含目标、参与、环境和 Mermaid 图。
- [当前架构](docs/architecture/OVERVIEW.md) · [流程图](docs/architecture/FLOWS.md) · [技术实现详解](docs/architecture/TECHNICAL_IMPLEMENTATION_WALKTHROUGH.md)：组件职责、授权、同步与 13 张实现图。
- [Agent 能力与 skill 对照](agent-comm-platform/agent-comm/docs/architecture/CAPABILITY_SKILL_MAP.md)：能力覆盖、遗漏修正与包含平台地址和接入链接的加好友文案导出。
- [发布记录](docs/releases/README.md)：版本、验证范围、运行镜像及回滚位置。
- [仓库维护](docs/maintenance/REPOSITORY_MAINTENANCE.md)：目录职责、依赖与发布顺序。
- [本次整理记录](docs/maintenance/STRUCTURE_CLEANUP_2026-09-15.md)：迁移范围、删除依据和验证结果。

本仓库的 Git 子模块引用定义源码组合；发布记录保存当次实际部署证据。公开下载的早期源码 ZIP 和安装包保留各自发布快照，后续源码提交不代表已重新分发安装包。
