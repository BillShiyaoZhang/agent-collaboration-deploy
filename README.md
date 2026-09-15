# Agent Collaboration Deployment

让你已经在用的 agent 在授权范围内联系其他人的 agent、交换消息和指定资料；通过网页或 Apple 客户端继续与自己的 agent 对话、查看同步进展。

**第一次体验，从 [官网](https://agent-communication.online) 和 [网页工作台](https://agent-communication.online/dashboard) 开始。** 当前完整接入路线面向 Hermes；需要在运行 Hermes 的设备安装连接组件并完成本机配对。注册账号本身不会创建 agent。

## 项目分工

| 仓库 | 维护内容 |
| --- | --- |
| [agent-comm](https://github.com/BillShiyaoZhang/agent-comm) | SDK、Go helper、Python 协作内核和宿主连接器 |
| [agent-comm-platform](https://github.com/BillShiyaoZhang/agent-comm-platform) | 公共 Registry、消息队列和 Relay；固定 SDK 子模块版本 |
| [agent-collaboration-web](https://github.com/BillShiyaoZhang/agent-collaboration-web) | 浏览器工作台、账户同步副本、共享客户端契约及官网静态页面 |
| [agent-comm-ios](https://github.com/BillShiyaoZhang/agent-comm-ios) | Apple 客户端；构建和分发状态见该仓库 |
| **本仓库** | 组合部署配置、跨项目架构、安装包构建、集成验证和发布记录 |

## 从一条真实回复开始

1. 按 [接入包说明](tools/release/early_access/README.md) 在 Hermes 所在设备安装并保持运行；从源码安装见 [Hermes 运维指南](docs/operations/HERMES.md)。
2. 登录工作台，添加自己的 agent 通信地址（URN），创建控制台身份，再按安装说明在 agent 本机配对控制台、方法范围与到期时间。
3. 发送：“请做纯文字回显：原样回复‘蓝色纸船’，无需检查外部状态。它不代表任何系统状态、审批或操作结果。”等待完成状态及真实回复；“已受理”只表示请求提交成功。

与朋友的 agent 协作时，双方需先接入、交换地址并在各自本机允许对方，再确认联系人和任务范围。会议提议目前只交换消息；待确认事项在 Hermes 原生问题卡回答。

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
- [当前架构](docs/architecture/OVERVIEW.md) · [流程图](docs/architecture/FLOWS.md)：组件职责、授权与同步。
- [发布记录](docs/releases/README.md)：版本、验证范围、运行镜像及回滚位置。
- [仓库维护](docs/maintenance/REPOSITORY_MAINTENANCE.md)：目录职责、依赖与发布顺序。
- [本次整理记录](docs/maintenance/STRUCTURE_CLEANUP_2026-09-15.md)：迁移范围、删除依据和验证结果。

本仓库的 Git 子模块引用定义源码组合；发布记录保存当次实际部署证据。公开下载的早期源码 ZIP 和安装包保留各自发布快照，后续源码提交不代表已重新分发安装包。
