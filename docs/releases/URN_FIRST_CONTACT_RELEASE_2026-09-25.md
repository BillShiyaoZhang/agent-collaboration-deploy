# 2026-09-25 Agent Comm v0.9.1：仅凭 URN 发起好友申请

本次更新让使用**同一个 Platform** 的 Agent 以准确 URN 发起首次好友申请。新版 helper 从 Registry 查询并验证 URN、Ed25519 公钥、派生 PeerID、X25519 公钥及注册签名，缓存该密码学绑定；未知 URN 的已认证申请交收件主人接受或拒绝。接受只建立通讯关系，不证明现实人物身份，不提高 `trusted`，也不授予任务、资料、工具、工作台或合规披露权限。Python Runtime、Hermes 协作工具及已配对 Web 仅向 `connected` 联系人发送普通业务消息；低层 Go helper `/api/v2/mq/store` 不查询好友状态，接收方 Runtime 会隔离未连接发送者的业务消息。已有手工公钥固定记录保留，发现结果不能静默覆盖不同密钥。跨 Platform 发现、互信和路由未实现。

## 固定版本与发布状态

| 对象 | 本次固定值或已验证状态 |
| --- | --- |
| Deploy 构建与部署提交 | `d10c99fe66314fb2231660569e4b8e84c4534c0f` |
| Web HEAD | `1fb65cb2f8e44b95a17ae3d01960ac777d14a4d4` |
| Platform HEAD | `dc6d5a5d1272f37c7bcf3588ca0b4445c3679a56` |
| SDK HEAD / tag | `5800fb67e81121c1565f65c6a0b3c1936415522f` / [`v0.9.1`](https://github.com/BillShiyaoZhang/agent-comm/releases/tag/v0.9.1) |
| GitHub 发布 | [Actions run 36130871076](https://github.com/BillShiyaoZhang/agent-comm/actions/runs/36130871076) 成功；Release 已发布 16 项资产 |
| 生产 Web 镜像 ID | `sha256:a54540f4fb90da766efcbdcca49033eb0d5bbdc85d46ccd420fa4f8f79105f5c` |
| 生产 Platform 镜像 ID | `sha256:a300a1849dc6a763c19f4743038bde1433d22e485476ba06f75aee7581077d56` |
| 切换前备份 | `/root/agent-comm-releases/2026-09-25-urn-first-v090/pre-cutover-2`，仅服务器授权人员可读 |
| 签名策略 | `compliance` epoch 3，摘要 `6f9f7bdf26c5e7761cbe8c451a22fd11f9a448d912fa5bc3ae61c1e53f3ff5c4`；本次未改变 |

GitHub `v0.9.1` 的 16 项资产与 `release-manifest.json`、`SHA256SUMS`、GitHub 资产元数据中的长度和摘要一致。官网五份 ZIP 与发布清单取自该正式 Release，经服务器暂存校验后更新。公开清单与 GitHub `early-access-manifest.json` 逐字节相同，SHA-256 为 `9ec13b903deb9973768bfa112d13845ca4cd9d70167172507abfabe29347d6c8`。从官网公网 HTTPS 入口重新下载五份 ZIP 与清单，长度和摘要也全部一致：

| 官网 ZIP | SHA-256 |
| --- | --- |
| Windows amd64 | `a39dc3d9b45707aca20e70232f0dddf0a071f522b926cd829b3350ded8063263` |
| Linux amd64 | `75660c320193be516f3cc8d322d481f62b082192aebca9577965bf338dd60ead` |
| macOS Intel | `74a0ab2e057e81d0849ba6a4abe15ef81cc93e8c4dcab4c686c3a746a5b97241` |
| macOS Apple Silicon | `5dd775f325eaafbed6c17b6a6c42eda8480356759195675e504b6f30f93fff0f` |
| 源码 | `374307d28338a06a8a446b54d16d7fc5d07f144e02ba75894e173e8a7eb76795` |

先前的 `v0.9.0` tag 因连接器旧测试仍假定未连接者的业务消息可见，Actions 测试阶段失败，未产生 Release；修正测试后才创建并发布 `v0.9.1`。两者的 tag 未被移动。

本机 Windows 候选包和 Linux CI 发布包字节不同；本次官网仅使用 GitHub 正式资产。四份官网正式平台包各自通过安装器 `--check-only` 完整性与版本检查，非 Windows 包在 Windows 环境使用 `--cross-platform-check`；这不是 Linux 或 macOS 原生安装和 Hermes 联调。

## 备份、策略与验证

切换前备份位于上表路径。四份 SQLite 数据库的 `PRAGMA quick_check` 均为 `ok`；切换前后 `.env` 内容一致。生产镜像 ID 见上表。签名合规策略仍为原 epoch 3 和原摘要，因此本次代码与镜像更新不是一次新的策略签发，也不自动授予任一主人本机合规披露许可。现有身份、联系人、消息、网页配对与授权应继续保留；本记录不声称对旧数据执行了重置。

本地验证使用新 Platform、helper 和策略工具 Windows 二进制，`tests/integration/test_v2_gateway_network.py` 通过：在双方未手工固定对端公钥的情况下，先仅以 URN 发送首个 `contact.request` 并验证接收，再覆盖 v2 握手和现有网关回归。SDK Go 全套、Python Runtime 163 项、Hermes Store 45 项、Web 198 项、根仓发布工具 49 项及文档结构检查通过；Web TypeScript 检查和构建通过。GitHub Actions v0.9.1 的测试、构建与发布阶段也全部通过。上述自动检查不代替真实用户体验验收。

生产合成验收先用本地构建的候选 helper 完成一次，随后用**从官网公网 HTTPS 下载的正式 Windows ZIP** 中的 helper 再次完成同一流程；正式 helper 的 SHA-256 为 `7863261a3b80f93b72032b8f61443aa9cecac1ef14684cb4e8ffe2d0e963c0ef`。每次创建新的本机合成身份，按当前合规策略明确授权，验证仅凭 URN 首次申请和 Registry 认证密钥发现、拒绝后业务消息隔离、再次申请并接受、乱序消息只在相应接受后释放、双向收发与已读，以及接受不提升任务或 `trusted` 状态，均通过。本机合成私钥在测试结束时清除；公开 Registry 中短期合成注册按正常生命周期过期。本验收未让真人评价交互，也未运行真实 LLM 协作回合。

## 回滚与范围

公开下载文件的前一版本保存于 `/root/agent-comm-releases/2026-09-25-urn-first-v091/pre-cutover-downloads`。旧 Web 和 Platform 镜像分别保留标签 `agent-collaboration-deploy-web:pre-urn-v090-20260925` 与 `agent-collaboration-deploy-platform:pre-urn-v090-20260925`。代码或镜像回滚应保留实时数据库；数据库备份仅用于确认故障后的数据恢复，不能直接覆盖在线状态。

本次只覆盖同一 Platform 上的首联与通讯。跨 Platform 公钥交换、平台间互信和路由属于后续设计；平台保证的是 URN 与所登记密钥的密码学绑定，并不证明现实身份。联系人接受不等于全部信任、合规披露同意或任务授权。真人体验和实际 LLM 协作仍需另行评价。
