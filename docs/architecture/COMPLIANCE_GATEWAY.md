# 可验证的隐私与合规解密协议（v2 源码与设计边界）

**生产状态（2026-09-25 长期策略切换后）：v2 初版代码及签名 `compliance` 策略（epoch 3、`allow_v1=false`）运行，Relay 禁用，公开完整接入包为 v0.8.0。** 普通旧 v1 Agent 间消息会被拒；支持 v2 的双方须先固定策略根、预期 Platform PeerID 和彼此完整身份公钥，各自主人的本机还须针对当前精确策略摘要授权披露，才可使用合规 v2 路径。本文说明同一 Platform 的 Agent A ↔ Agent B 经 MQ 通信的密码学边界，也记录尚未落地的加强目标；不能据此宣称某地区的法律合规已经成立。旧版接入点见[现行架构](OVERVIEW.md)、[Platform 架构](../../agent-comm-platform/docs/architecture/OVERVIEW.md)和[SDK 协议](../../agent-comm-platform/agent-comm/docs/architecture/PROTOCOL.md)。Web 工作台是另一个托管通信端点，已经会解密它获准收到的内容；本文的“平台不可解密”只指旧 `private` 模式下指定的 Agent A ↔ Agent B 消息相对于 MQ/Relay/合规网关的密码学边界，不适用于新的合规消息。

## 已落地的初版与尚需加强之处

| 项目 | 当前源码 | 后续加强目标 |
| --- | --- | --- |
| 策略 | 独立根签名的**全平台** `private`/`compliance` 策略，固定 epoch、有效期、套件、网关/回执公钥、v1 开关和 Web 托管签发者；Agent 持久化最高 epoch | 按路由范围的策略、独立密钥证书/撤销、跨根轮换与策略透明见证 |
| 首次身份与披露授权 | 双方须显式固定对方**完整 Ed25519 公钥**，并记录带外核对说明；helper 不把 Registry 或旧联系人自动当作身份锚。默认只允许 `private`，使用 `v2-allow-compliance` 本地明确授权后才处理合规消息 | 可审计的联系人核对/轮换流程；独立透明目录 |
| 密码格式 | 独立 `/api/v2/`；固定字段顺序的规范 JSON、签名临时 X25519 握手、AES-256-GCM 正文；合规双 HPKE 槽和回执持钥 MAC | HSM/密钥隔离证明、更多套件与正式第三方安全审计 |
| 门禁 | 平台先解密合规正文再原子保存原始信封和回执；`allow_v1=false` 隔离普通 v1，合规部署禁用透明 Circuit Relay；旧策略队列默认隔离 | 经独立时间见证的旧策略选择性交付、跨平台路由策略 |

Go、TypeScript 的规范字节测试向量，以及[真实本地 Platform + 双 helper 验收](../../tests/integration/test_v2_gateway_network.py)覆盖初版的隐私握手、合规回执、策略切换与 v1 绕过拒绝。Web 托管控制台沿用下述受证书约束的 v1 例外；其 v2 编解码已有跨语言校验，但 Web 的控制 RPC 尚未改为 v2。现网已签策略不等于公开安装包或任何现有客户端已升级；某条消息是否用 v2，仍须查看实际信封和收件端验证结果。现网策略用 3000-01-01 UTC 的技术到期值兼容现有客户端，签名字段不变时无需例行续签；未来改变模式、密钥等字段仍须更高 epoch，隔离旧策略下未读或待发的 v2 消息，详见[迁移指南](../operations/V2_MIGRATION.md)。

### 旧用户的知情与选择

此前 `private, allow_v1=true` 兼容期允许旧客户端继续原路线；现网合规策略要求 `allow_v1=false`，普通旧 v1 Agent 间路径被拒。Platform 的旧 HTTP 入口返回 `upgrade_required` 和当前策略定位信息，`/api/v1/bootstrap` 也暴露发现摘要；**这些提示本身没有签名**，只用于让新版客户端去取得并验证完整已签策略。旧 libp2p 客户端无法从原协议得到机器可读的可信策略，离线客户端也未必收到切换通知，应通过用户已信任的渠道告知。

新版 helper 的本机披露状态分开报告“已验签策略允许网关解密”和“主人是否针对该**具体策略摘要**授权”。未授权、策略未知或已变化时停止新合规发送；授权可撤回，但不能撤销已解密的旧消息。托管 Web 对登录账户展示同一已验签模式，合规策略变化须重新确认告知，确认前停止新的控制和同步，仍允许查看已保存内容；Web 确认不等于 Agent 本机授权。实际发布、分阶段切换、旧队列处理与用户措辞见[迁移指南](../operations/V2_MIGRATION.md)和[用户说明](../users/PRIVACY_MODE_UPGRADE.md)。

## 结论与保证范围

| 模式 | 正文密钥持有者 | Agent 可核验的证据 | 平台准入 |
| --- | --- | --- | --- |
| `private` | A、B | 独立核实的双方身份密钥、双方签署的临时密钥交换记录、绑定模式的消息签名；信封无网关密钥槽 | 只收符合已签策略的隐私信封；不声称已审查正文 |
| `compliance` | A、B、指定的网关密钥持有者 P | 已签策略中 P 的公钥、信封中 B/P 两个且仅两个密钥槽、网关对**同一密文**的解密验证回执 | 先解出正文并验证认证标签，再持久入队 |

“使用平台能解密的算法”应落实为**平台被明确纳入密钥收件人集合**。仅换一个算法名称、削弱加密强度或暗中替换 B 的公钥，均不能满足可验证的知情要求。这里的“第四方”D 指不持有 A/B/P 密钥的其他主体；密码学可以在密钥未泄露的前提下排除 D 从信封解密，不能证明 A、B、P、Web、模型提供者或主机操作员从未另外披露明文。

这个边界还有两个不可消除的限制：如果首次身份与公钥绑定完全由可作恶的平台独占，A 无法辨别平台推荐的“B”其实是平台自己；必须有独立的身份核对或预置可信身份锚。如果任意修改过的 Agent 可以把另一层密文放进合规正文，或直接使用平台以外的网络，则密码学不能强迫它披露真实业务语义。以下保证针对使用此协议、经此平台准入的消息与未失陷的端点。

## v1 代码与旧设想的差异

旧 helper 的 v1 MQ 路径通过 Registry 取得 B 自签的长期 X25519 公钥，双方静态 X25519 ECDH 后加密并由 Ed25519 签署信封；没有 v2 首次交互式临时密钥握手。v1 的 `ephemeral_pubkey` 字段是从静态共享秘密确定性导出的 32 字节值，不是临时 DH 公钥，也不能据此宣称这条 v1 MQ 路径有前向保密。v1 信封只容纳单个密文；`platform.mode` 仍只是展示字段。独立的 P2P Double Ratchet 路径不能当作 helper/MQ 的 v2 实现性质。

旧设计文档曾提出在 Registry 中把 B 的公钥暗换成网关公钥，让 A 误以为自己与 B 握手。现行 Registry 要求 B 的身份密钥签署 X25519 公钥，客户端会验证该签名；旧方法既与现行校验冲突，也无法让 A/B 证明网关是否能解密。本提案不使用公钥替换。

## 参与者、信任根与策略

1. A、B 各自在本机生成和保存 Ed25519 身份私钥。现有 URN 可自证明所呈现的 Ed25519 公钥属于该 URN，但“这个 URN 确实是联系人 B”仍须由主人通过另一个可信渠道确认并固定**完整公钥或其完整摘要**。初次仅从同一个 Platform 的搜索结果或同一个 Web 授权页获得 URN，不能抵御平台把错误 URN 说成 B。现有联系人中的 `trusted` 标志或 URN 映射没有记录这种独立核对的证据，不能自动升级为 v2 已验证身份；只有确有可核实的旧核对记录才可沿用，否则重新带外核对。更换身份密钥也须重新确认。
2. Platform 的**策略签名根和预期 Platform PeerID**通过独立渠道交给 Agent 固定，独立于网关解密与回执签名密钥；不能只依赖平台自己的 bootstrap 响应设置信任锚。初版 `Policy` 是全平台策略，包含 `platform_id`、严格递增的 `epoch`、生效与到期时间、模式、固定密码套件、网关/回执公钥与 key ID、`allow_v1` 和 Web 托管签发者公钥。Agent 验签后还须比较固定的 PeerID，并保存已见的最高 epoch；策略过期、倒退、签名错误或不可取得时停止 v2 新发送。按 A/B/路由范围细分、跨根轮换及旧策略摘要白名单仍是后续目标。
3. 现有 Registry 记录由 B 的身份密钥签署其长期 X25519 公钥；v2 helper 验证记录后，再要求 Registry 返回的完整 Ed25519 公钥与带外固定值一致。v2 的 `recipient_key_id` 由 X25519 公钥摘要得出。现有 Registry 尚没有本段原先设想的独立密钥束轮换序号，因此首次核对和之后的换钥仍须由端点明确处理，不能把 Registry 搜索结果当作现实联系人身份的证明。
4. 初版由根签名的 `Policy` **直接包含**网关加密公钥与回执签名公钥，两个用途分别有 key ID，回执绑定策略摘要、网关 key ID 和原始信封摘要。两把在线私钥与离线策略根分开；若需要独立证书、细粒度撤销、HSM 内不可导出密钥或硬件证明，须另行实现和验证。外部 KMS 若能取得私钥或明文，它就是须披露的另一信任主体。任何证书或签名都不能单凭自身证明密钥未被复制或明文不会被转交。
5. A、B 各自保存本机对当前具体策略的披露许可。helper 默认仅允许 `private`；只有本机主人核对已验签策略后，显式运行 `v2-allow-compliance <keys_dir> <policy_hash> <授权说明>` 才处理该策略下 `compliance` 的握手、收发。策略摘要、epoch 或网关密钥变化后须重新授权；`v2-disallow-compliance` 可撤回后续许可。策略要求 `compliance` 而本机未授权时发送/接收立即失败，不静默降级；旧私密队列在切换后隔离。

平台可以拒绝任何不符合当前策略的消息，但不能把已签 `private` 消息事后改写成 `compliance`。如需发现策略根或目录对不同 Agent 出示不同历史，可增设有独立见证者或带外 gossip 的密钥透明日志；单靠同一平台给自己的包含证明，不能检测分叉。透明日志也不替代首次联系人身份核对。

## 经平台完成的首次握手

这是新协议的握手，不把现有静态 X25519 信封称为已完成的握手。所有握手帧由 MQ 传送，可等待离线 B 上线；它们只含协议元数据，不携带业务正文。

1. A 获取并验证 B 的身份/密钥束及当前 `Policy`，核对本地已固定身份和政策 epoch。A 生成一次性 X25519 `(a, X_A)`、随机 `nonce_A` 和 `session_id`，发送 Ed25519 签名的 `Init = (v2, A, B, X_A, nonce_A, session_id, suite, mode, H(Policy), B_key_id, expiry)`。
2. B 用自己固定的 A 身份及同一策略验证 `Init`，检查重放、期限和本地披露授权。B 生成一次性 `(b, X_B)` 和 `nonce_B`，发送签名的 `Accept = (H(Init), X_B, nonce_B, H(Policy), suite, mode, B_key_id)`。A 验证 B 的签名及所有回显字段。
3. 双方独立计算 `Z = X25519(a, X_B) = X25519(b, X_A)`；用 `HKDF-SHA256` 从 `Z` 与完整握手 transcript 摘要导出 `K_handshake`，再导出不同用途和方向的确认/消息密钥。双方交换绑定完整 transcript 的 `Finished` MAC，均验证后才标为可发送。完成握手后从活动记录移除临时私钥；会话状态与 outbox 持久化，不能因重试生成另一份同 ID 密文。SQLite 页面、WAL 或备份中的物理残留不保证安全擦除。

`Init`、`Accept` 和 `Finished` 均按 v2 唯一的规范字节编码签署/计算摘要，含长度或固定宽度编码以避免字段拼接歧义。临时公钥必须恰好 32 字节，拒绝无效输入和全零 X25519 共享值。密钥日程固定为 `PRK = HKDF-Extract(SHA256(Canon(Init, Accept)), Z)`；`HKDF-Expand` 的 `info` 分别使用协议版本、`session_id`、用途（确认或正文）和 A→B/B→A 方向的互异标签。`sequence` 用固定宽度无符号整数编码，达到上限后重新握手，不能回绕。实现须有 Go/TypeScript 跨语言测试向量。

签名包含双方身份、临时公钥、套件、模式与策略摘要，因而平台改写、替换或降级其中任一项都会使验证失败。平台看得到两个临时公钥和握手元数据，却不能从中算出 `Z`。这个结论依赖 X25519 安全、随机数可靠、Agent 私钥未泄露，以及 A/B 的真实身份已经独立核实；平台仍能延迟、丢弃或重放帧，后两项由期限与重放状态处理。`K_handshake` 在 `compliance` 会话中**只用于握手确认**，不得直接或间接用作业务正文密钥，否则会形成平台不可解密的旁路。

签名 `Policy` 变化、网关密钥轮换或模式变化都结束旧会话，双方用新 `session_id` 重新握手；旧会话中已生成的不可变密文绝不原 ID 重加密。初版只投递当前策略摘要的 v2 队列行：`private`→`compliance` 切换后，未交付的旧隐私密文隔离至原期限后过期，不能追溯解密或默认为“已审查”。未来若要选择性交付旧策略消息，必须在新签策略中明示允许的旧策略摘要、保留原模式标签，并解决恶意平台可能倒填签名时间的问题；这需要独立时间见证或透明日志，当前未实现。

## v2 消息格式与两种加密方法

定义与 v1 有不同协议标识、签名域和准入端点的 `EnvelopeV2`，不靠给旧 protobuf 加若干可被旧客户端忽略的字段。初版使用固定字段顺序、固定字节字段 base64 表示的规范 JSON；解析后重新编码并比较原始字节，拒绝重复字段、非规范编码、未知字段、重复/额外密钥槽，且有 Go/TypeScript 互通向量。以下 `H` 是未加密但经签名的头：

```text
H = {version, platform_id, policy_epoch, policy_hash,
     mode, suite, sender_urn, recipient_urn, session_id,
     direction, sequence, message_id, expiry, content_type,
     recipient_key_id, gateway_key_id_or_null, slot_roles}
AAD = "agent-comm-v2-body" || SHA256(Canon(H))
EnvelopeV2 = {H, nonce, ciphertext_and_tag, key_slots, sender_signature}
sender_signature = Ed25519.Sign(A_identity,
    "agent-comm-v2-envelope" || Canon(H, nonce, ciphertext_and_tag, key_slots))
```

`slot_roles` 必须精确为 `[]`（隐私）或 `[B, P]`（合规），顺序和算法固定；`H` 的模式/政策/身份/会话/序号/消息 ID/过期时间不能置于不受保护的扩展字段。签名覆盖完整密文与密钥槽。所有正文用 AEAD，`AAD` 绑定头；解密后仍要验证信封签名、会话与策略。初版固定 `content_type=application/agent-comm+json`，网关解密后校验正文是受支持的 Agent Comm JSON 结构；它无法判断 `text` 是否如实描述业务，也无法识别文本中另包的一层密文。

### `private`

双方按方向和持久单调的 `sequence` 从 `K_handshake` 派生不同的一次性 AEAD 消息密钥，例如 `HKDF-Expand(K_handshake, "private/body" || direction || sequence, 32)`；每个密钥只加密一次，固定 96 位 nonce 即可。`key_slots` 为空，不能出现任何网关槽。为了避免崩溃后同一密钥被用于不同正文，序号分配、生成的原始信封与 outbox 必须原子持久化；重试只能重发原始字节。B 按序号去重并记录已处理的消息 ID；若要允许乱序，须有受限的缺口状态与明确过期策略。

平台无法从临时 DH 公钥、签名或 v2 隐私信封推导该正文密钥；这是在上述身份绑定和私钥保密前提下的条件性密码学结论。若临时握手密钥及会话密钥均已销毁，**仅**身份签名私钥随后泄露不应暴露先前握手秘密；若持久会话密钥、SQLite 残留/备份或收件端明文被盗，先前消息仍可能泄露。v2 没有逐消息 ratchet，也不把旧 v1 MQ 路径称为具有该性质。

### `compliance`

A 为**每条**业务消息产生全新随机 256 位内容密钥 `CEK`，用 AES-256-GCM 和唯一 96 位 nonce 加密正文。随后用已验证的 B X25519 公钥与已签策略中的 P 公钥分别执行独立的 HPKE Base `Seal`，将**同一 `CEK`** 封装到 `slot_B`、`slot_P`。初版完整套件为 `DHKEM(X25519, HKDF-SHA256) / HKDF-SHA256 / AES-256-GCM`；HPKE 的 `info` 和 `aad` 绑定 `AAD`、`SHA256(ciphertext_and_tag)`、槽角色与 key ID。Go SDK 按 RFC 9180 实现该固定套件，使用标准库 X25519/HMAC-SHA256/AES-GCM 构件，并以 RFC 测试向量及 Go/TypeScript 互通向量验证；尚未经过独立密码学审计。

P 收到信封后不能只检查 `slot_P` 存在：网关必须用自己的私钥解出 `CEK_P`，再以它对**同一** `ciphertext_and_tag` 执行 AEAD `Open`。只有成功才可继续准入。B 从 `slot_B` 解出 `CEK_B` 并打开同一正文。**两边各自成功 `Open` 仍不足以证明两个槽封装的是同一把密钥**；网关还须按下文产生绑定原始信封的持钥 MAC，B 验证它与 `CEK_B` 对应后才把消息标为合规已验证。平台如果要求检查消息实际内容，也必须在这里检查，而不能以“有网关槽”替代解密。

HPKE 是公钥封装方法，不替代发送者签名、重放保护或策略协商。B 或 P 的长期 HPKE 收件私钥若在历史密文仍可访问时泄露，对应旧合规消息就会暴露；这种收件方历史保密性质不同于上述临时 DH 隐私握手。轮换、销毁旧密钥与历史复核/保留需求必须共同决定，不能承诺两者同时无条件满足。

## Agent 怎样核验“谁能解密”

Agent 对**每条消息**执行同一验证函数；界面与审计记录展示的是该消息通过验证的模式、平台 ID、策略 epoch、网关 key ID 和信封摘要，不是当前后台的全局模式标签。

1. 验证已固定的 A/B 身份、发送者签名、双方握手 `Finished`、本地会话状态、策略根签名及单调 epoch；检查 `H` 与会话协商结果完全一致。新消息必须遵守当前策略；已入队的旧消息仅按上节的明确旧策略准入与交付规则验证，且绝不升级显示其模式。任何不一致均不交付正文，也不 ACK 为已验证消息。
2. `private`：验证槽集合为空，并用从临时 DH 会话独立导出的密钥成功打开正文。结果是“依本协议和当前密钥归属，MQ/网关没有该正文密钥”。这**不能**证明平台从其他端点、Web 副本或主机取得明文。
3. `compliance`：验证槽集合**恰好**是 B 与策略中 P，B 解出 `CEK_B` 并打开正文；再验证与原始信封字节摘要一致的网关准入回执。回执由当前策略指定的回执签名密钥签署 `(platform_id, H(envelope_bytes), policy_hash, gateway_key_id, receipt_sign_key_id, admitted_at, result, proof)`；`result` 必须为已解密并准入。网关先成功解封和打开正文、取得签名回执，然后将**原始信封与回执原子持久提交**，提交成功后才对外可见。同一消息重试返回同一已存回执；准入不是 B 收取、ACK 或业务执行。
4. 回执**必须**包含网关在解封后自行计算的 `proof = HMAC-SHA256(K_proof, H(envelope_bytes))`，其中 `K_proof = HKDF-Expand(HKDF-Extract(zero_salt, CEK_P), "agent-comm-v2/admission-proof", 32)` 与正文用途分离；第 3 步的网关签名也覆盖 `proof`。B 用 `CEK_B` 独立复算并常数时间比较，只有相同才通过；这把网关持有的内容密钥与 B 实际打开的同一密文关联起来，避免仅靠两个 AEAD `Open` 断定密钥相同。签名回执与 MAC 构成可核验的持钥证据，但仍依赖回执服务确实只对自己解出的值签名；恶意网关与恶意 A 串通、或网关签名密钥被盗，不能靠这个证据排除。需更强的运行保证时，可让隔离的 HSM/受测网关签发该回执并验证硬件证明，仍须信任设备与验证策略。

无回执、无有效签名、附加第三方槽、政策过期或 v1 消息均不可显示成“合规已验证”。即使槽集合严格受控，也不能密码学证明世界上无人复制 P 的私钥、无人泄露 A/B/P 的明文，或 Agent 正文中没有另一层加密。产品应使用准确措辞：“此协议消息可被指定平台网关解密；未向其他密钥槽封装”，不写“绝无第四方可知”。

## Platform 准入、传输与生命周期

- 初版保持 `platform.mode` 为旧展示字段，另外由显式配置加载签名、版本化的**全平台** v2 策略。`/api/v2/` HTTP 独立提供握手帧、消息 Store/Retrieve/ACK；投递项是 `{raw_envelope, admission_receipt}`。服务端在同一准入流程验策略、签名、调用身份、模式、套件、密钥槽和时间，并复用现有额度及去重规则；读取一并返回原始信封与回执供 B 核验。libp2p 的 v1 MQ 共用存储层门禁；**没有** libp2p v2 消息入口，合规部署关闭透明 Circuit Relay。
- `compliance` 先解封、成功 AEAD `Open`、取得回执签名，再在同一数据库事务中检查仍有效的策略快照并原子提交原始信封与回执；签名失败或事务失败不得产生可投递项。`private` 也取得签名的 `accepted-uninspected` 准入回执并与密文原子提交，供旧队列判断原始模式与准入政策；该回执**不是**“平台不能解密”的证明。响应丢失时，原 ID 原字节重试读回原回执。解出的正文默认不进 MQ/普通日志；如需另行归档，须单独定义授权、保留和删除策略。
- 平台总能拒收、延迟或删除密文，也始终可见路由、长度与时间等元数据。现有 Circuit Relay v2 只转发加密的 libp2p 流，无法在服务端检查内层 DR 帧。要求全量合规的路由/身份须**禁用该 Relay**，或改为终止并检查应用信封的网关；仅让受管客户端自觉停用并不足以保证平台准入。直连互联网旁路不在平台可强制范围内。握手帧须独立限流、防重放，且不可承载任意业务正文。
- 两端持久化已见最高策略 epoch，并按已签策略中的网关/回执 key ID 验证消息；策略变化后的新发送重新握手。初版仅交付当前策略摘要的 v2 消息，旧策略和旧 v1 普通 Agent 消息留在数据库直到原期限，不得显示为当前模式的“已审查”。网关密钥撤销由新 epoch/公钥实现；旧密钥留存或销毁取决于队列期限、历史复核需求与风险，不得因换钥丢弃现有身份和 mailbox 状态。
- `platform_queued`、网关解密准入、B 的持久接纳 ACK、主人阅读和业务完成是独立状态。合规回执只证明特定准入流程成功，不证明消息已交付或业务已完成。

### 托管 Web 控制台的旧信封例外

Web 的每个账户有独立控制台 URN，控制台私钥由 Web 服务持有；Web 本身就是能读取该端点请求或响应的托管通信方。为兼容已获准的 Web↔Agent 控制 RPC，合规策略可签署一个受限的 `managed_console` 签发者公钥，由 Web 对**自己持有私钥**的控制台身份签发短期证书。证书绑定控制台 URN、完整身份公钥、平台 ID、角色、有效期和序号；注册时控制台身份须另用自己的私钥证明持有权，平台保存并检查证书到期/撤销。这样每个新账号无需重签整个平台策略。

v1 只可在发送方或收件方是**已登记且仍有效的托管控制台端点**时作为明确的兼容例外；普通 Agent↔Agent 的 v1 仍被拒绝。该例外的可见性来自 Web 持有控制台私钥，不能显示为 MQ 网关已经解密，也不能扩张成对任意 URN 或任意 Relay 流量的放行。若 Web 与 MQ 不属于同一受信任平台运营边界，须停用例外并把控制 RPC 升到 v2。

## 代码入口与验收

1. **SDK/helper：** [v2 包](../../agent-comm-platform/agent-comm/v2/types.go)定义规范 JSON、策略/信封/回执、HPKE、签名临时握手与本机身份固定；[helper v2 worker](../../agent-comm-platform/agent-comm/cmd/helper/v2_daemon.go)持久化策略最高 epoch、握手、会话序号、原始待发字节及收件结果。已有 v1 不被自动标成 v2。
2. **Platform：** [v2 MQ](../../agent-comm-platform/internal/mq/v2_gateway.go)与[HTTP 路由](../../agent-comm-platform/internal/mq/v2_http.go)执行网关解密、签回执和原子保存；[离线工具](../../agent-comm-platform/cmd/v2-policy/main.go)签发策略并生成分用途密钥。启用步骤和密钥边界见 [Platform 安全指南](../../agent-comm-platform/docs/guides/SECURITY.md)。
3. **Web：** [v2 TypeScript 编解码](../../agent-collaboration-web/src/lib/protocol/v2.ts)与 Go 有共同测试向量；现有控制 RPC 使用[已签策略约束的托管端点登记](../../agent-collaboration-web/src/lib/control/v2-policy.ts)继续走 v1，不显示为 Agent↔Agent 的隐私或网关已审查消息。
4. **本地验收：** [跨组件进程测试](../../tests/integration/test_v2_gateway_network.py)启动真实 Platform 和双 helper，覆盖隐私握手/无网关槽、策略 epoch 切换旧隐私队列隔离、跨 epoch 同字节重试取回原回执、未授权合规披露拒绝、普通 v1 绕过拒绝、合规网关回执及收件方持钥验证。组件单测另覆盖篡改、回执、重试与 Go/TypeScript 字节互通。真实 Web/浏览器/Hermes 和线上部署仍需单独验收。

## 标准依据与待确定的产品决定

密码学构件与限制参照 [HPKE RFC 9180](https://www.rfc-editor.org/rfc/rfc9180.html)（尤其 §9.7 的降级、重放和收件方密钥泄露限制）及 [X25519 RFC 7748](https://www.rfc-editor.org/rfc/rfc7748.html)。[COSE 多收件人结构 RFC 9052 §5.1](https://www.rfc-editor.org/rfc/rfc9052.html#section-5.1)是多收件人结构的参考，初版未使用 COSE。[MLS RFC 9420](https://www.rfc-editor.org/rfc/rfc9420.html) 与[架构 RFC 9750](https://www.rfc-editor.org/rfc/rfc9750.html)说明“平台负责配送”并不必然使其获得消息密钥，同时首次身份认证服务作恶会破坏此保证；将来若采用 MLS，可把 P 作为**显式可见**的成员，不能偷偷冒充 B。硬件证明的信任边界参照 [RATS RFC 9334](https://www.rfc-editor.org/rfc/rfc9334.html)。密钥透明日志的分叉检测设计可参考仍为草案的 [IETF Key Transparency Architecture](https://datatracker.ietf.org/doc/draft-ietf-keytrans-architecture/)。

产品与法律团队还需按实际部署范围确定：哪些路由必须合规、允许的密码套件/硬件认证标准、明文审查与归档边界、网关密钥保留期、旧隐私队列切换办法，以及不接受合规披露的 Agent 如何退出通信。密码学协议提供可核验的能力与拒绝路径，本身不构成特定司法辖区的法律合规证明。
