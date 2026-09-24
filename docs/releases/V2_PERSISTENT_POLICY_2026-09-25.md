# 2026-09-25 生产 v2 长期策略切换

生产 Platform 于 **2026-09-25 07:17 CST 左右**，从签名 `compliance` epoch 2 切到同模式的 epoch 3。此次不改变披露范围、`allow_v1=false`、Platform PeerID、网关/回执/受管签发者公钥或 Relay 配置；只把策略从短期有效改为长期有效。公开 v0.8.0 客户端的签名格式仍要求 `expires_at`，因此签入 **3000-01-01 00:00:00 UTC**。这在操作上取消每月例行续签，但不是数学意义的永不过期。

| 核对项 | 实际结果 |
| --- | --- |
| 新策略 | `compliance`，epoch `3`，`allow_v1=false`，Relay `false` |
| 新策略摘要（policy_hash） | `6f9f7bdf26c5e7761cbe8c451a22fd11f9a448d912fa5bc3ae61c1e53f3ff5c4` |
| 技术到期时间 | 3000-01-01 00:00:00 UTC (`expires_at=32503680000`) |
| 原 epoch 2 策略 | `15d105118ddd433c8d5599c7fbd287085df8adce9680a120d09ff187b10c062a`，原到期 2026-10-24 16:52:24 UTC |
| Platform PeerID | `12D3KooWNApwdxwbXY27N44cGxTXY15Hn8yRx9m9Yw5St5A7kTpK`，未变 |
| 策略根公钥 SHA-256 | `9d133d88dadbfeca6db56e9ffa43060046d36ab3bde4547c79f52104e6a252cd`，根私钥留在维护工作站 |
| 签发器源码 | Platform `b1526b5555b1587dbf8752677e6146d57600466c` |
| 生产 Platform 镜像 | `sha256:0372f06156656d4709b959a748d69aae0cf5d9058e161c7f82fdcdf8c743ad77`；现有镜像已支持远期时间戳，无需换镜像 |
| Web 源码与最终镜像 | Web `69a8665e223462a1b8cdad3c86fa748e99fd5185`；`sha256:7b3418adc70dfd500e1b8c5488b6a53812f4fc3aa4fd6e1c8e8c12160e678869`，`linux/amd64` |

## 切换与备份

签发器默认生成长期策略；显式 `--valid-for` 才生成有界的短期策略。使用原离线根签出 epoch 3 后，在本机验证 Ed25519 签名和规范字节，逐字段比对新旧策略：除 epoch、`not_before`、`expires_at`、签名外全部相同。新签策略只有公开 JSON 上传到服务器；离线根私钥没有进入服务器、容器、镜像或 Git。现有 Go helper、Platform 和 Web 均维持原有验签与短期策略到期拒绝规则，Go、JavaScript 和 Windows Python 已验证可处理 3000 年时间值。

切换前备份位于服务器 `/root/agent-comm-releases/2026-09-25-persistent-e3/pre-cutover`，包含四份 SQLite 在线备份、原策略和配置、在线密钥、Platform 身份、`.env`、管理员策略及旧镜像 ID。`registry.db`、`mq.db`、`audit.db`、`web-prod.db` 的 `PRAGMA quick_check` 均为 `ok`。切换脚本在重启前再次发现**有效未读 v2 消息 0 条**，若非零会停止切换；它复核了新旧在线密钥/配置完全相同、策略摘要和签名字段差异符合预期，并确认服务器没有离线根私钥。

脚本仅重建 Platform 容器，然后测试并重载 nginx。刚重启时一次健康探测出现 HTTP/2 framing 错误，内置有界重试后切换完成。随后的独立只读复核得到 `/healthz`、Web 首页、`/api/v2/policy` 均 HTTP 200；MQ 持久状态为 epoch 3、上述新摘要、`expires_at=32503680000`、`require_v2=1`。Platform、Web、nginx 容器均在运行。旧 epoch 2 策略不能在严格 epoch latch 下直接重放为回退；必要时须用离线根签更高 epoch 修复，保留数据和备份。

## 线上合成验收

脱敏结果位于本机忽略提交的 `build/live-two-agent-acceptance/live-20260925-compliance-e3-accept/`。两套全新且相互隔离的 Hermes helper/身份分别固定可信根、Platform PeerID 和对方完整公钥：未授权及单侧授权时均阻断新合规收发；两端分别按 epoch 3 精确摘要授权后，Alice→Bob、Bob→Alice 均验证了收件人与网关两个密钥槽、网关解密准入的签名回执和 proof、收件端实际解密、持久 inbox 与 ACK，无重复投递。普通 helper/Platform v1 路径均被拒；双方撤销本机许可后继续拒绝新合规流量。`v080-compliance-e3-result.json` 为 **PASS**，清理记录也为 **PASS**。

同一轮两个全新合成 Web 账户分别完成披露确认前后门禁检查：未确认不能认领，错误策略摘要被拒，逐账户确认互不代替；受管控制与 Alice 的暂停/恢复检查通过。`web-live-e3-preclaim.json`、`web-live-e3-postclaim.json` 均为 **PASS**。测试结束后撤销配对并移除临时凭据、身份私钥和进程。网关准入回执与收件 ACK 仍不等于用户阅读或业务完成；这轮合成决定不能代替真实用户的选择。

Web 镜像从已测试并推送的 `69a8665` 源码在本机 Docker 构建，核对架构、源码标签以及镜像中的新公开安装说明后，以摘要 `bb36f108c8102a733e3c5e2dd088366d2470484a7c281b1c6c9773745721e166` 的 gzip 归档传至服务器。服务器验摘要和镜像 ID，另备份当时的 Web SQLite 至 `/root/agent-comm-releases/2026-09-25-persistent-e3/web-preimage.db`，仅重建 Web 并重载 nginx。账户数 `42→42`、SQLite `quick_check=ok`，HTTPS 公共说明含长期策略文字。刚重启时一次登录探测出现短暂 502，重试后成功；随后独立复核 `/healthz`、首页、策略接口均为 200，Platform/Web/nginx 运行。最终 Web 镜像 ID 与上表一致。

同一新版 Web 镜像参与了独立的[T21 有界并发与断线补测](../verification/T21_STABILITY_2026-09-25.md)；测试中的 Platform 是隔离镜像，Web Push 则通过生产合成账户的真实外部推送链路。各自结果和未覆盖范围以该验证记录为准，不能把不同环境的样本合并成生产全链路压力结论。

## 用户授权与后续轮换

即使模式和密钥不变，这次 epoch/hash 变化仍会隔离旧摘要下的未读/待发 v2 消息，并使旧的本机精确策略授权和 Web 逐账户确认不适用于新摘要。切换后、合成验收前的只读检查中，epoch 3 的 Web 确认为 0；epoch 2 没有真实账户确认记录。验收后 epoch 3 有 2 条合成测试账户的确认，**不等于用户本人作出选择**。本次没有代替任何真实用户确认 Web 披露或在其 Agent 上授权。需要真人参与的体验与决定仍按[测试步骤](../testing/TEST_EXECUTION_GUIDE.md)执行。

模式、网关/回执/受管签发者密钥、`allow_v1`、Platform 身份等签名字段全部不变时，可一直使用当前长期策略，无需例行签发或重复授权。任何字段变化仍须严格递增 epoch、备份并核对旧队列、公告新范围，并由两端主人按精确新摘要重新决定，Web 账户另行确认。长期有效也意味着密钥泄露不会在 30 天后自然失效；发生泄露时必须主动轮换或更换信任根并让用户重验。操作细节见[迁移与轮换指南](../operations/V2_MIGRATION.md)。
