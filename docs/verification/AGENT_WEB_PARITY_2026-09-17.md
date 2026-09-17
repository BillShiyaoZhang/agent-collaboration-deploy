# Agent / Web 能力一致性修复

本记录对应 2026-09-17 的源码修改。本次发布范围为 GitHub 源码；按用户要求不部署服务器，也未更新线上下载包。

## 问题与修复

| 用户要求 | 原有问题 | 当前实现 |
| --- | --- | --- |
| 1–3 本机 agent 注册并绑定 Web | Web 添加连接必须先解析已注册 URN；注册、控制台创建和配对分散 | 允许保存未注册 URN 的待连接记录，自动创建控制台；本机配对脚本通过 helper 用原有身份签名注册后再授权 |
| 4 agent 是唯一业务事实来源 | Web 有同步副本，但新的写操作、已读和请求状态缺少统一投影 | 联系人、请求、收件箱、已读、审批和操作结果全部由 agent Store 决定，Web 保存经验证的结果 |
| 5–7 聊天与界面能力一致 | 已配对 Web 会话能运行 Hermes，但工具入口仅接受本机上下文；Web 仅两个写方法 | 真实宿主绑定配对会话上下文，使用相同 Runtime；Web 提供好友、消息、已读、审批和通用协作能力入口 |
| 8 双向好友请求 | 添加联系人只是单边保存地址 | 持久好友请求与响应协议；对方可接受/拒绝，接受回执更新发起方；旧单边映射显示尚未验证 |
| 9 双端消息与提醒 | 陌生消息不可见；已读不是共享状态；通知 revision 更新可能留下旧弹窗 | 主人可查看陌生消息；消息已读与提醒终态保存在 agent，Web/本机同步；旧消息也可处理，处理后关闭业务待办；配置自动安装本机待办界面 |
| 10 好友在线状态 | 无在线状态来源 | helper 每 30 秒续写签名注册心跳，90 秒过期；本机验签后向 Web 同步在线/离线/未知 |
| 11 Web 展示 | 无好友请求及读状态操作、完整能力表单 | 好友请求、连接/在线状态、收发消息、已读、审批与其它 Runtime 功能均可查看和操作 |

## 已执行验证

- `go test ./...`：SDK 全套通过，包括签名 presence 与 helper 测试。
- Runtime Python 单元测试：154 项通过，包括双向好友、拒绝、伪造身份、跨端已读、旧消息和崩溃重试。
- 官方 Hermes 宿主 `98f758ae` 下 connector Python 测试：142 项通过；Desktop 待办及恢复 JavaScript 测试共 55 项通过。测试使用真实宿主代码与受控回合，不调用付费语言模型。
- 本机配置/安装测试：16 项通过；发行打包测试：5 项通过。
- Web 单元及共享客户端契约测试：171 项通过；生产构建通过。
- 发布兼容补充：上述测试包括新增 [提醒已读回归测试](../../agent-collaboration-web/tests/unit/notification-read.test.cjs) 6 项，覆盖旧客户端、未授权/失效配对、离线与缺少能力快照、agent 回执匹配及失败不写入 Web 已读；TypeScript 检查通过。
- [真实浏览器操作](../../agent-collaboration-web/tests/integration/workspace-social-browser.cjs)：四组检查通过，覆盖好友接受/拒绝、请求到连接状态、在线/离线、发消息、双端已读，以及不确定操作禁止换新请求自动重放。无页面错误；390px 手机布局无横向溢出。
- [新能力真实网络测试](../../tests/integration/test_agent_web_parity_network.py)：本地 platform、双方 helper、控制台 helper 和 Python Store/RPC，通过自动签名注册、陌生好友请求、接受后双方连接、Web/本机双向消息、共享已读和在线状态。
- [既有远程链路回归](../../tests/integration/test_remote_control_network.py)：17 项检查通过，含身份校验、方法范围、撤销、重启恢复、投递失败重试、审批主人隔离与双边协作。
- [生产 Web 完整链路](../../agent-collaboration-web/tests/integration/full_stack_smoke.py)：10 项检查通过，包含真实 Next 登录、Web 控制台签名加密、Go MQ/helper 传输、Python 授权执行及账户加密副本同步。

生成日志与临时测试身份保存在忽略的 `build/`，不应提交或分发其中的私钥。

## 使用与部署边界

需要一起更新 helper、runtime、Hermes connector、配置脚本及 Web。已有配对不会自动增权，使用同一控制台 URN 执行新版 `configure_hermes.py --remote --pair-console ... --expires ... --allow-web-actions`，然后重启 Gateway/dashboard 并重载 Desktop。注册与签名发生在 agent 本机，不创建云端替身 agent，也不上传本机私钥。

旧 agent 或未授权 `inbox.mark_read` 的配对，在提醒中心禁用消息已读按钮并显示升级/重新配对说明；提交前也会重新检查 agent 能力，只有匹配的 agent 已读回执才能继续确认该提醒。审批等其它提醒的查看确认仍与业务决策分开。客户端升级顺序见[接入包说明](../../tools/release/early_access/README.md#已有客户端升级)。

在线表示 agent-comm 通信端近期有效心跳，不承诺模型正在推理。同步采用后台轮询，因此其它端状态在下次成功同步后更新；离线端恢复连接后补齐。

Hermes SDK 的 `host.notify` 与 `ctx.os.notify` 未提供撤回既有 OS 通知的接口。本次可以关闭 agent 业务待办、计数和后续提醒；已经送达系统通知中心的历史条目仍由宿主管理。Web 的 Service Worker 支持处理后的通知关闭。
