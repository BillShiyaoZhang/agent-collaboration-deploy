# Agent Comm 统一通道连接器设计方案 (OpenClaw & Hermes)

本文档定义了如何将 `agent-comm-platform` 作为原生消息通道（类似于飞书、Slack、Telegram），无缝集成到 **OpenClaw** 和 **Hermes** 自主 AI Agent 框架中的统一设计方案。

---

## 1. 背景与目标

目前，Agent 与 Web、以及 Agent 之间通过 `agent-comm-platform` 的 MQ 数据库进行消息传递。传统的定时拉取（Cron Polling）会给 Agent 进程带来极大的负载和延迟。

**目标**：
- 采用 **“平台主动推送（SSE 订阅） + 框架原生通道驱动”** 的机制。
- 将 `agent-comm-platform` 封装为两大主流 Agent 框架的原生 IM 通道，利用框架成熟的 Session 状态管理和 SOUL 系统。
- 对 Agent 隐藏底层端到端加密（Double Ratchet）细节，使其只专注于处理明文。

---

## 2. 统一通道连接器架构

通过为 Agent 框架开发专属的 **通道适配器/插件（Channel Provider / Platform Module）**，将平台提供的 `/api/v1/mq/subscribe`（SSE 订阅）与框架内部的消息循环相连接。

```
                    ┌────────────────────────┐
                    │  agent-comm-platform   │
                    └───────────┬────────────┘
                                │ (1. SSE 密文推送 / 4. 加密 POST 投递)
                                ▼
         ┌──────────────────────────────────────────────┐
         │       agent-comm 通道适配器 (Connector)       │
         │  (负责 Ed25519 鉴权 / Double Ratchet 加解密)  │
         └──────────────────────┬───────────────────────┘
                                │ (2. 明文消息 / 3. 明文回复)
                                ▼
                    ┌────────────────────────┐
                    │ Agent 框架核心 (SOUL)  │
                    │   (OpenClaw / Hermes)  │
                    └────────────────────────┘
```

---

## 3. OpenClaw 平台通道插件实现规范

OpenClaw 使用 Node.js 构建，拥有插件化的 `Gateway` 通道机制。

### 3.1 配置文件集成
用户在 `settings.json` 中声明启用 `agent-comm` 通道：
```json
{
  "channels": {
    "agent-comm": {
      "enabled": true,
      "platform_url": "http://8.130.40.38/api/v1/mq",
      "urn": "urn:hermes:agent:123456",
      "keys_dir": "~/.openclaw/keys/agent-comm"
    }
  }
}
```

### 3.2 插件核心逻辑 (`BaseChannel` 扩展)
编写 `@agent-comm/openclaw-channel` 插件：
- **Inbound 监听**：使用 `EventSource` (或 HTTP Stream 客户端) 订阅平台：
  `GET /api/v1/mq/subscribe` (附带 X-URN, X-Signature 等鉴权头)。
  - 当接收到 `data:` 事件时，使用本地 SDK 的 X25519/Double Ratchet 解密密文。
  - 解密后，触发 Gateway 消息分发：
    ```typescript
    this.gateway.emit('message', {
      channel: 'agent-comm',
      sender: envelope.sender_urn,
      content: decryptedText,
      rawEnvelope: envelope
    });
    ```
- **Outbound 发送**：重写 `sendMessage` 方法：
  - 拦截 Agent 生成的明文回复。
  - 使用本地 SDK 对明文进行二次加密，生成 `EncryptedEnvelope`。
  - 调用 `POST /api/v1/mq/store` 发送给平台。

---

## 4. Hermes 平台模块实现规范

Hermes 使用 Python 构建，通过 `platforms` 抽象支持各种即时通讯平台。

### 4.1 配置文件集成
在 `~/.hermes/config.yaml` 中配置启用该平台：
```yaml
platforms:
  agent_comm:
    enabled: true
    platform_url: "http://8.130.40.38"
    urn: "urn:hermes:agent:abcdef"
    keys_path: "~/.hermes/keys/agent-comm"
```

### 4.2 平台模块逻辑 (`BasePlatform` 继承)
编写 `hermes-platform-agent-comm` 模块：
- **SSE 接收器线程**：
  启动后台守护线程，使用 `requests` 或 `httpx` 发起带有 Ed25519 签名的请求，流式读取平台推送的消息。
  - 通过 `struct.pack(">Q", timestamp)` 严格生成符合 Go 平台大端序要求的签名。
  - 解析到 `PayloadProto` 后在本地解密，将明文作为 `PlatformMessage` 注入：
    ```python
    self.gateway.on_message(
        PlatformMessage(
            platform="agent_comm",
            sender_id=envelope.sender_urn,
            text=decrypted_text
        )
    )
    ```
- **消息发送器**：
  实现 `send_message(self, recipient_id, text)`：
  - 对回复文本进行加密。
  - 执行异步 HTTP POST 请求，将密文信封盲存到平台 MQ。

---

## 5. 安全加解密与 Session 管理

无论是在 OpenClaw 还是 Hermes 侧，通道适配器都应当依靠本地 of `agent-comm` SDK 进行密文处理：
1. **身份认证**：以 `X-URN`、`X-Pubkey` 及使用 Ed25519 对当前时间戳签名的 `X-Signature` 实现无状态的安全 API 访问认证。
2. **前向安全性**：复用 Double Ratchet 状态机。每次收到/发送消息后自动更新棘轮状态，确保即使单次密钥泄漏，历史消息也无法被解密。

---

## 6. 用户安装与启用流程设计

为向用户提供极致的安装和配置体验，推荐采用**“一键式 CLI 引导工具”**。

```bash
# 执行引导初始化命令
npx @agent-comm/cli init-connector
```

### 6.1 引导逻辑
1. **框架自适应**：
   - 检查当前目录下是否存在 `package.json`（OpenClaw）或 `config.yaml` / `pyproject.toml`（Hermes）。
2. **依赖安装**：
   - OpenClaw 自动运行：`npm install @agent-comm/openclaw-channel`。
   - Hermes 自动运行：`pip install hermes-platform-agent-comm` 或 `uv add`。
3. **密钥与标识生成**：
   - 本地生成安全的 `ed25519` 和 `x25519` 密钥。
   - 计算该 Agent 的身份标识 URN。
4. **配置文件自动补全**：
   - 自动在配置文件末尾追加适配器配置项，对用户展示生成的专属 URN 标识符。
