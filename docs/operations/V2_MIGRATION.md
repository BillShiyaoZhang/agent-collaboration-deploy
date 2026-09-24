# v2 私密兼容期与未来合规模式迁移

**现网状态（2026-09-24）：`https://agent-communication.online` 已启用签名 v2 `private` 策略，epoch 1，`allow_v1=true`；公开接入包截至此时仍为 r2，v0.8.0 尚待发布验收。** 因此旧接入包仍能使用 v1，但旧流量没有 v2 私密信封的保证。只有安装支持 v2 的接入包、固定可信策略根与 Platform PeerID、核对联系人完整身份公钥并走 v2 发送路径的双方，才能使用 v2 Agent 间私密通信。当前**不是** `compliance` 模式，不要求用户同意平台网关解密。密码学边界见[协议说明](../architecture/COMPLIANCE_GATEWAY.md)。平台策略对同一 Platform 的 Agent 间消息是**全局**的，不能让部分用户在该 Platform 继续 `private`，同时让其他用户进入 `compliance`。

现网信任锚与有效期如下，供通过**独立可信发布渠道**取得的值交叉核对；只从同一个网站读取根、PeerID 和策略，再互相比较，并不能建立独立信任。

| 项目 | 当前值 |
| --- | --- |
| Platform PeerID | `12D3KooWNApwdxwbXY27N44cGxTXY15Hn8yRx9m9Yw5St5A7kTpK` |
| 策略根 Ed25519 公钥（hex） | `ef357a906bb59ecd176b7551d5f92870b5ec38ce04f92c1693c1593f910ebacc` |
| 策略根公钥 SHA-256 | `9d133d88dadbfeca6db56e9ffa43060046d36ab3bde4547c79f52104e6a252cd` |
| 当前策略 | `private`, `allow_v1=true`, epoch `1` |
| 当前策略到期 | 2026-10-24 13:43:31 UTC（Unix 秒 `1792849411`） |

运营方须在到期**之前**使用离线根私钥续签更高 epoch，部署并验证新策略，同时保留旧策略和数据库备份。即便仍签 `private`，epoch 变化也会隔离旧策略下未读/待发的 v2 消息；先统计和处理队列，再安排续签窗口。不能等到签名策略过期后才恢复服务，也不能靠重放旧策略续期。

## 用户必须知道和能选择的事

**以下合规披露与授权步骤仅适用于未来明确决定切到 `compliance` 时，当前私密兼容期不要求这些授权。** 切换通知应在生效前通过已有可信联系方式发出，并在新版 Agent 和 Web 内再次展示。平台不能向离线的旧客户端保证送达通知；旧版 libp2p 客户端也不一定能解析新的 HTTP 错误。上线前应记录通知范围、计划时间、客服/退出路径，不把“客户端连接过平台”当作用户已同意。

可直接使用的告知文字：

> 计划从 **[日期时间及地区]** 起，此 Platform 的 Agent 间新消息将进入合规模式。发送方会把**同一份正文密文**的内容密钥同时封装给收件 Agent 和指定的平台网关，因此网关可以解密并检查经它准入的正文。平台仍会看到路由、长度和时间。你的 Agent 不会因收到公告自动授权披露；你需要更新接入组件、核对对方身份公钥和策略签名根，并在本机明确同意。不同意时，该 Agent 将停止通过本 Platform 发送和接收要求合规的新消息。切换前未交付的旧隐私消息不会被平台追溯解密，也不会自动标为合规，可能留在隔离队列直至到期；请提前处理。

用户界面应区分三个事实：**平台当前签名策略**、**本机是否同意合规披露**、**某条消息实际通过的模式与回执**。Web 托管控制台持有自己端点的密钥，仍会读取用户已授权给它的内容；它的受管 v1 例外不是 Agent 间合规回执。没有完整公钥的独立核对、没有明确本机授权或无法验证签名策略时，不能把旧联系人、旧配对或一次 HTTP 成功当作升级成功。

## 分阶段切换

1. **先升级服务并保留兼容期（现网已完成）。** 备份 Platform 身份/数据库、Web SQLite、`NEXTAUTH_SECRET` 与旧镜像。生成离线策略根、网关、回执和 Web 受管签发者密钥；只给在线容器对应的在线私钥。部署已签 `private` 策略并设置 `allow_v1=true`。这时**原有旧二进制**仍可使用原 v1；新版 helper 在未固定可信策略根时会停止普通发送并提示设置根，固定后才可使用 v2。不能把旧 v1 流量标成 v2 隐私保证。检查反向代理确实把 `/api/v2/` 送到 Platform。
2. **让两端准备就绪（随 v2 接入包逐步进行）。** 待 v0.8.0 经校验清单正式发布后，保留原 `keys_dir`、`mailbox.db`、Web 账户和配对记录，不重建身份。每个 Agent 从平台之外核对策略根、预期 Platform PeerID 及对方完整 Ed25519 公钥，按 [helper v2 指南](../../agent-comm-platform/agent-comm/docs/architecture/PROTOCOL_V2.md)固定并重启；调用方改为本机 `/api/v2/mq/store`。新版 helper 的本机 `/api/v2/disclosure` 分别报告已验证的策略模式/网关密钥、本机授权、发送就绪与旧消息隔离数；未知策略不能显示为“平台无法解密”。只更新二进制或继续调用旧 `/api/v1/mq/store` 不会自动升级。Web 按[自身迁移说明](../../agent-collaboration-web/docs/operations/DEPLOYMENT.md)应用追加式数据库迁移，保留现有控制台身份；新 Web 会登记受管证书。以真实双 Agent 收发、验签、解密和 ACK 确认准备状态，不能仅凭平台注册或 HTTP 202 推断。
3. **提前处理旧队列，再切换。** 公告并留出用户处理窗口。所有仍需交付的旧 v1/隐私消息应在旧策略下处理；未处理的在新 epoch 下隔离，不能由平台重加密。确需重发的内容应由发送方在新策略下重新决定并使用新消息 ID。再签发严格递增 epoch 的 `compliance` 策略，设置 `allow_v1=false`、`relay.enabled=false`，重启 Platform。双方用户查看新版 helper 的已验签策略摘要后，各自在本机**针对这个精确策略**授权合规披露；新 epoch、网关密钥或策略摘要变化须重新授权。未授权、未升级或离线 Agent 停止该路由的新收发，不静默降级。Web 控制台只通过活跃的受管证书继续其明确的 v1 兼容路径。

切换前按收件人统计未读旧队列和到期时间，并与 `mq.max_msgs_per_urn` 比较。这个配额同时计算旧 v1 与 v2 的未读消息，即使旧消息在新策略下暂时不可交付，仍占用磁盘和配额；达到上限后，新受管控制消息和 v2 消息会收到 `429`。优先让收件方在旧策略仍可用时持久接纳并 ACK；必须保留旧密文时，先做容量估算，再临时设置有界的新配额并监控磁盘、队列数量和 `429`，待旧消息到期后恢复原值。不要靠 ACK 当前不可见的旧消息或自动删除它们腾出配额；确需处置时先备份，并按用户策略走管理台的明确范围操作。

签发命令与分用途密钥见 [Platform 安全指南](../../agent-comm-platform/docs/guides/SECURITY.md)。兼容期的私密策略显式使用 `--mode private --allow-v1 --epoch <新值>`；切换时使用 `--mode compliance --epoch <更高值>`，不能附 `--allow-v1`。平台身份 ID 取自现有 `/api/v1/bootstrap` 的 `peer_id`，保持原 Platform 身份。签发根私钥必须始终离线。用户须从可信渠道**同时核对并固定**策略根公钥和预期 Platform PeerID；平台提供的发现提示本身不能充当这两个信任锚。

任何 epoch 变化都会结束旧会话并隔离旧策略下待发/未读消息，包括同模式续签。续签和轮换前同样先安排队列处理。当前没有旧策略消息选择性交付功能，也没有按用户/路由渐进切换；若地区政策允许不同迁移时间，应使用隔离的 Platform 部署和明确的用户分流计划，不能在同一策略下假装已分组。

## Compose v2 覆盖文件

现网使用根目录的 [`docker-compose.v2.yml`](../../docker-compose.v2.yml) 显式启用 v2；原 `docker-compose.yml` 仍是基础部署入口。先从现有 Platform 配置复制一个**不提交到仓库**的 v2 配置，保留原身份和数据库路径，加入：

```yaml
v2:
  enabled: true
  policy_file: /run/agent-v2/policy.json
  policy_root_public_key_file: /run/agent-v2/policy-root.public
  gateway_private_key_file: /run/agent-v2/gateway.private
  receipt_private_key_file: /run/agent-v2/receipt.private
```

兼容期的 `private` 策略可按计划保留旧 Relay；切换 `compliance` 前必须在该配置中设置 `relay.enabled: false`，并签发 `allow_v1=false` 的策略，否则 Platform 拒绝启动。`platform.mode` 是旧展示字段，不会启用网关；切换时仍应把它更新为 `compliance`，避免管理员页面显示旧的 `privacy`。实际密码学模式始终以已验签的 `/api/v2/policy` 为准。

在服务器的 `.env` 中设置覆盖文件所要求的八项 `AGENT_V2_*` 路径/公开值，名称见根目录 [`.env.example`](../../.env.example)。所有宿主路径使用现存的绝对**文件**路径；Web 只挂载受管签发者私钥，Platform 只挂载网关及回执私钥。离线 `policy-root.private` **不得**放入任一容器、挂载目录、镜像或 `.env`。Web 需要策略根的 64 位十六进制公钥和现有 Platform 的 `peer_id`；私钥文件必须可由容器内 Platform UID 10001 或 Web UID 1001 按各自用途读取，同时限制其他账户。不要为了修复权限而清空数据卷。

```bash
docker compose -f docker-compose.yml -f docker-compose.v2.yml config --quiet
docker compose -f docker-compose.yml -f docker-compose.v2.yml up --build -d
curl --fail https://agent-communication.online/api/v2/policy
```

在当前 `private` 兼容期，复核已签策略、epoch、过期时间、Web 策略显示、受管证书登记、旧版 v1 继续可用，以及两个已固定信任锚和联系人公钥的 v2 Agent 实际收发、验签、解密与 ACK。将来切换 `compliance` 时，再复核 Web 告知与确认、两个 Agent 的本机授权、真实合规消息的网关回执，以及旧 v1 Agent 消息被拒。保留原始策略和迁移记录用于排查；不要把网关准入回执当作收件方处理完成。

## 中断、拒绝与回退

- 用户拒绝披露时停止该 Platform 上要求合规的 Agent 间通信，不替用户执行授权，也不把普通 v1 作为旁路。为其说明已隔离消息、数据导出和可用的其他服务选择。
- 已同意的用户可在本机撤回后续合规发送/接收许可；Web 账户也可暂停后续控制与同步，同时保留已保存快照供查看。撤回不能收回已经入队、已解密或已同步的内容；不要把停止后续传输写成删除历史明文。
- Web 或 Agent 离线时，它只能在恢复连接并验证更高 epoch 后得知变更。平台的 HTTP 升级提示只是引导定位签名策略，客户端必须自行验证策略根、平台 ID 和 epoch。
- 技术回退须由离线策略根签发**更高 epoch** 的新策略，不能重放旧私密策略或删除数据库绕过门禁。能否回退披露规则还取决于实际地区政策；已交给网关解密的内容不能通过回退收回。
