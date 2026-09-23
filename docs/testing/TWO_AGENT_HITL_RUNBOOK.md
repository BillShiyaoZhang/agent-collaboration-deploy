# 两个 Agent 与两边用户的实操验收 Runbook

本文专门回答一个问题：Alice 的 Agent 和 Bob 的 Agent 如何真实互动，以及 Alice、Bob 各自的用户决定如何被证明。它建立在 [系统测试方案](TEST_STRATEGY.md) 的 E1/E2 环境上。

## 1. 先固定角色和边界

| 角色 | 真实对象 | 负责什么 |
| --- | --- | --- |
| Alice | Hermes profile A + helper A + Web 账户 A | 发起联系人、消息或协作事项；在自己的原生对话或 Web 审批卡做决定 |
| Bob | Hermes profile B + helper B + Web 账户 B，或临时 helper/runtime B | 接收请求、接受/拒绝联系人、阅读消息、回复或处理协作事项 |
| Platform | staging 服务器上的 Registry/MQ/Relay | 查找身份、暂存和转交密文；不替任一用户做决定 |
| Web A/B | 两个独立登录会话和 Console URN | 只能调用各自 agent 本机明确配对的方法 |
| 测试员 | 操作 Alice/Bob 的浏览器和原生 Hermes | 记录每次人的决定，不直接改数据库来制造结果 |

必须为 A、B 分配不同的 helper keys、URN、Peer ID、mailbox、Hermes profile、协作 SQLite 和 Web 账户。不能把一方的 key、profile、remote pairing 或 owner principal 复制给另一方。

如果本机只有一个 Hermes，先用临时 helper/runtime B 做确定性协议测试；真实的两边用户介入测试再使用第二个 Hermes profile、第二台机器，或能同时运行两个独立 profile 的 Hermes 实例。只启动第二个 helper 不能证明第二个真实宿主会话已经工作。

## 2. 两种测试层次

### 层次 A：两个临时 Agent，先证明协议

这层不调用模型，结果稳定、适合每次版本回归。仓库已有脚本：

~~~sh
python tests/integration/test_agent_web_parity_network.py \
  --helper PATH_TO_HELPER --platform PATH_TO_PLATFORM
~~~

它会自动创建 Platform、Alice/Bob 两个 helper、Web Console 身份，验证：

- Alice 的 Web 联系人请求到达 Bob；
- Bob 的本地 owner 接受后两端变为 connected；
- Web → Bob 的消息和 Bob → Alice 的回复；
- 两边共享已读和提醒终态；
- 签名、加密、请求关联、方法权限和在线 presence。

先跑这一层，失败时优先检查协议、helper、Platform 和 Store；不要先把问题归因给浏览器或模型。

### 层次 B：两个真实 Hermes + 两个用户

这层只在 staging 做，验证真实宿主会话、原生确认卡、Gateway 生命周期和人做出的选择。模型任务只使用没有外部副作用的文字，例如“原样回复蓝色纸船”。

两层都要做，因为：

- 层次 A 能证明 Agent/Platform/Web 的事实链路；
- 层次 B 才能证明真实 Hermes 是否把来信展示给正确用户、是否能让用户决定、是否把决定写回同一个协作 Store。

## 3. 建立一次可重复的测试运行

为每次运行生成一个 RUN_ID，例如 20260922-120000-ab12。所有对象都加这个后缀：

- Web：owner-a-RUN_ID、owner-b-RUN_ID；
- agent 连接名：Alice-RUN_ID、Bob-RUN_ID；
- 消息文本：A-to-B-RUN_ID、B-to-A-RUN_ID；
- 联系人 ID：alice-to-bob-RUN_ID；
- 任务、审批、请求和消息 ID：使用稳定的前缀加随机值。

服务器使用单独 staging 域名和 Compose project。当前根 Compose 固定了 agent-nginx、agent-web、agent-platform 三个 container_name；如果生产和 staging 在同一台服务器，不能只加 Compose project 名，必须使用单独服务器或为 staging 移除/改名这些容器。

先确认服务器。已有阿里云服务器可以直接作为 staging；如果生产也在这台 ECS，必须先套用经过检查的 staging override，不能只使用 Compose project 名：

~~~sh
docker compose -f docker-compose.yml -f PATH_TO_STAGING_OVERRIDE.yml -p agent-staging ps
curl --fail https://staging.example/healthz
~~~

本机启动两个隔离 helper。命令中的 keys-A、keys-B、端口和 Platform URL 必须不同：

~~~sh
agent-comm-helper daemon /path/to/keys-A https://staging.example 45042
agent-comm-helper daemon /path/to/keys-B https://staging.example 45043
~~~

分别查询：

~~~sh
curl http://127.0.0.1:45042/info
curl http://127.0.0.1:45043/info
~~~

保存两个返回的 URN。确认 A、B 的 URN、Peer ID 和 keys 目录完全不同；确认同一个 helper inbox 没有同时被 Hermes connector 和 standalone remote serve 消费。

## 4. 接通两个 Web 控制台

为 Alice 和 Bob 分别注册 Web 账户，保存各自 agent URN，然后在各自工作台创建 Console identity。每个控制台只绑定对应的 agent：

1. Alice 账户只保存 Alice URN，Bob 账户只保存 Bob URN。
2. 在 Alice 本机 pair Alice Console；在 Bob 本机 pair Bob Console。
3. 读权限至少包括 capabilities、contacts.list、contacts.requests、collaboration.state、inbox.list、attention.list。
4. 要在 Web 添加联系人、发消息、标记已读或回答审批，再显式加入 contacts.add、contacts.respond、messages.send、inbox.mark_read、approval.respond；要在 Web 聊天使用完整协作工具，再加入 collaboration.execute。
5. A 的 Console URN 不能出现在 B 的 pairing store；B 的 Console 不能读取 A 的 agent。

使用配置脚本时，先执行检查计划，再执行写入：

~~~sh
python configure_hermes.py --remote \
  --pair-console ALICE_CONSOLE_URN \
  --expires FUTURE_UTC_EXPIRY \
  --allow-web-actions --check-only

python configure_hermes.py --remote \
  --pair-console ALICE_CONSOLE_URN \
  --expires FUTURE_UTC_EXPIRY \
  --allow-web-actions
~~~

Bob 使用自己的 profile、Console URN 和 helper URL 重复一次。检查计划输出的 profile、agent URN、Console URN、方法集合和期限；不要用 Alice 的命令改 Bob。

如果手动配对，使用相同的方法集合逐项 remote pair。重启两个 Gateway 后，在 A/B Web 各点一次“重新检查连接”，确认 capabilities 来自对应本机 agent，而不是 Web fixture。

## 5. 第一组：好友请求的双边闭环

### A 发起，B 接受

1. Alice 在原生 Hermes 中提出“把 Bob 的 URN 加为联系人”，或在 Alice Web 的联系人表单填写 Bob URN。
2. 如果由原生 Agent 发起，Alice 必须在自己的原生确认卡确认联系人绑定；如果由 Web 发起，Alice 必须完成表单确认且 Console 具有 contacts.add。
3. 保存 request_id、contact_id、Alice/Bob URN 和时间。
4. 检查 Alice 的状态：请求应为 requested/pending，不能立即显示 connected。
5. 等待 Bob 的 helper 收到好友请求；检查 Bob 的 attention 中出现 friend_request_received。
6. Bob 用户在 Bob 的原生 Hermes 中选择接受。若测试 Web 接受，则 Bob Console 必须单独拥有 contacts.respond，且点击的是具体请求的接受按钮。
7. 等待双方同步；A、B 的联系人快照必须有相同 URN 和请求关联，connection_status 最终为 connected。
8. Bob 的待办关闭；Alice 不应因为“平台 ACK”提前显示已连接。

记录四个独立事件：

~~~text
A 本地保存请求
Platform 暂存/转交
B agent 持久收到请求
B 用户接受并回执
~~~

### A 发起，B 拒绝

重复上面的步骤，但 Bob 选择拒绝。期望：

- Alice 看到 rejected/denied 或产品规定的等价终态；
- 两边都不能显示 connected；
- 相同 request_id 的重放不改变结果；
- Web 不能通过刷新或重新标记已读把拒绝变成接受。

### 断线和重复

在 Alice 提交后、Bob 决定前停止 Bob helper：

1. Alice 只能看到已提交或待投递，不能看到对方接受；
2. 恢复 Bob helper 后请求补拉；
3. Alice 刷新 Web，重试必须沿用原业务参数和原请求意图；
4. Bob 接受后只产生一个连接和一条接受回执。

## 6. 第二组：消息和两边用户介入

### Web → Bob native → Alice Web

1. Alice Web 发纯文本 A-to-B-RUN_ID。
2. 记录 Web 的 request_id 和 agent 返回的 message_id。
3. Bob agent 收到后，Bob 用户在 Hermes 中读到来信；此时只能是 unread/open，不要把 Platform ACK 当作已读。
4. Bob native 回复 B-to-A-RUN_ID。
5. Alice Web 等待同步，确认 message_id、in_reply_to、文本和对端 URN 正确。
6. Alice Web 标记已读，确认 Alice agent inbox、Web 副本和 attention 都关闭对应提醒。
7. 在两个 Web 页面和两个 native 端同时刷新，确认没有重复消息、重复提醒或重复 ACK。

### Bob Web → Alice native

反向再做一次，专门验证 Bob 的 Console 权限、Alice 的本地收件和 Alice 用户的原生处理不会被前一条链路污染。

### 发送结果不确定

在 Web 已提交、但浏览器收不到响应时断开网络：

- 页面应显示等待核实/结果不确定；
- 重试使用原 request_id、原 message_id 或同一持久密文；
- 不得因为用户重新打开页面就自动发送一条新的消息；
- 只有 agent 返回已认证结果后才把消息显示为完成。

## 7. 第三组：双方用户都要决定的协作事项

用一个不写日历、不调用外部工具的会议提议或资料分享作为固定场景。

1. Alice native 创建 task，明确绑定 Bob、能力、资料版本、时间范围、数量和期限。
2. Alice 用户在原生确认卡确认允许向 Bob 发出具体提议。
3. Alice Agent 发送结构化 proposal；Bob Agent 收到后只建立待处理事项，不自动接受。
4. Bob 用户选择接受或拒绝：
   - native 确认：检查真实 Hermes callback；
   - Web 确认：检查 Bob Console 具有 approval.respond，并且参数只有具体 approval_id 和 approve/deny。
5. 若 Bob 接受，双方各自读取 collaboration.state，确认 proposal 版本、参与人、状态和审计记录一致。
6. 若 Bob 拒绝，双方确认没有发送后续业务消息，任务进入拒绝/终止状态。
7. 在 Bob 决定前修改时间、资料版本、参与人或 task revision；迟到的接受必须失败并要求重新确认。
8. 在任一方撤销配对或 task 后重试，必须阻断；已发出的密文不能声称可召回。

这一组必须证明“双方都同意”是两个独立事实。Alice 的同意不能代表 Bob 的同意，Web 聊天中的“可以”也不能代替 approval.respond 或 Hermes 原生确认。

## 8. 第四组：并发、冲突和恢复

按以下顺序各跑一次：

| 场景 | A 的动作 | B 的动作 | 期望 |
| --- | --- | --- | --- |
| 同时加好友 | 发起对 B 的请求 | 同时发起对 A 的请求 | 只形成一条连接关系，不重复好友记录 |
| 接受与撤销竞态 | 发起并等待 | B 接受后 A 立即撤销 | 最终状态按 agent Store 的线性化结果，Web 不显示矛盾成功 |
| 决定与过期竞态 | 发送短期限审批 | B 在过期边界点击接受 | 过期或版本不匹配必须拒绝 |
| ACK 丢失 | A 发送后丢弃 ACK | B 只处理一次 | 重放补 ACK，不重复处理业务 |
| Gateway 重启 | A/B 任一侧重启 | 另一侧继续等待 | 恢复同一 task/conversation/message ID |
| Platform 重启 | 停 Platform 再启动 | 两边不改请求 | 未过期密文补拉，已持久化状态不丢 |
| Web 刷新 | A 或 B 刷新页面 | 另一侧不操作 | 不重复写请求，原请求可核实 |
| 一侧离线 | 停 B helper | A 发送消息 | A 显示 queued/pending；B 恢复后收到，不能提前显示 completed |

## 9. 每一步如何取证

不要只截图最终页面。每个用例至少保存一条双方时间线：

| 时间 | 发起方 | 事件 | ID | 状态/证据 |
| --- | --- | --- | --- | --- |
| t1 | Alice Web/native | 提交请求 | request_id | submitted/pending |
| t2 | Alice helper | 本机出站 | message_id | accepted/queued |
| t3 | Platform | 入队 | message_id | platform queued |
| t4 | Bob helper | 收件并验签 | message_id | received |
| t5 | Bob 用户 | 接受/拒绝 | approval_id/request_id | approved/denied |
| t6 | Bob agent | 业务状态写入 | task/message/contact ID | connected/replied |
| t7 | Alice Web | 同步已认证结果 | same ID | displayed/resolved |

建议同时保存：

- 两个 helper 的 /info 输出；
- A/B 的 remote pairings 和 capabilities；
- Platform、Web、helper、Hermes 日志；
- Web 浏览器截图和请求摘要；
- A/B 的 state、contacts、inbox、attention 快照；
- result.json，记录版本、时间、方法、ID 和最终状态。

日志中不能写入私钥、密码、完整 Console secret 或不必要的消息正文。测试正文使用 RUN_ID 标记，便于检索和清理。

## 10. 最小可执行顺序

第一次运行不要同时做所有功能，按这个顺序：

1. 跑现有 test_agent_web_parity_network.py，确认两个临时 Agent 的好友、消息和已读闭环。
2. 在 staging 接入 Alice helper 和 Bob helper，先只做 UJ-03 的 A 发起/B 接受。
3. 为 Bob Web 额外配对 contacts.respond，重复一次由 Web 处理 Bob 决定的流程。
4. 换成两个真实 Hermes profile，重复联系人接受、拒绝和消息回复。
5. 加入双方 approval.respond 或 native confirmation，执行一次 proposal 接受和一次拒绝。
6. 在决定前做断线、重启、过期和撤销，核对同一 ID 和最终 Store 状态。
7. 最后才测试真实 Web conversation；其模型输入只做纯文本回显。

停止条件是：任一方显示成功但另一方没有相同的 agent 事实；同一 ID 重放产生第二条业务记录；用户拒绝后仍继续执行；或测试日志无法把 Platform ACK 与业务完成区分开。
