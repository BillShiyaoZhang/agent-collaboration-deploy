# Gateway 历史事件回放与浏览器连接隔离

这是独立建议分支的传输修复契约。修改源码不代表公网已更新；保持已有账户绑定、本机批准、许可期限、短浏览器会话及撤销语义，不迁移或清除任何原授权。

## 问题与必要行为

原实现把合法历史回放的 ws.data 和控制消息共同计入每节点每 60 秒 1200 条额度。正常消费者逐条收到第 1199 条数据后，下一条会关闭整条 Tunnel；单个 BrowserPipe 满队列也会关闭节点。冷启动可能回放数千事件，因此只验证当前游标后的握手不足以证明完整页面恢复。

TUNNEL_RATE 仍限制控制消息，默认每窗口 1200 条。只有关联到活动 BrowserPipe 且通过类型、编码和 256 KiB 帧校验的 ws.data 使用独立数据预算：TUNNEL_DATA_RATE=60000 帧、TUNNEL_DATA_BYTES=67108864 编码 wire 字节，每节点每 RATE_WINDOW=60 秒；额度在同一 Gateway 进程内跨 Tunnel 重连保留。未知 correlation 不能绕过控制限流。畸形协议、超大帧、失效授权仍关闭 Tunnel。

正常 burst 进入有界异步队列；发送中的、排队的及等待空位的消息均保留字节计费。等待最多 WS_SEND_TIMEOUT，不扩大队列或无限累积任务。真正的队列/发送超时或全局排队字节预算拒绝，只关闭对应 BrowserPipe 并发送同 correlation 的 ws.close 通知本机，其他浏览器 lane、HTTP 和 ping 继续。节点共享的数据帧/字节额度耗尽则关闭 Tunnel，避免恶意 connector 无限超额发送、解析和丢弃；这与单浏览器背压隔离有明确区别。

每条 Tunnel 最多保留 256 个已关闭 lane 的 correlation tombstone，TTL 为 RATE_WINDOW（默认 60 秒），仅用于识别在途帧：仍校验帧、计入节点数据帧/字节额度并丢弃，不重新打开 lane。真正未知或过期 correlation 仍计控制限流；节点数据预算耗尽仍终止 Tunnel。

全局 rate_rejections 和控制/数据分项分别准确计数；背压计入 backpressure_closes。撤销、取消和关闭必须取消挂起的 queue put，并将每个字节 charge 释放一次，不能因等待任务插入迟到数据泄漏内存。

## 验证门禁

先确定性 Red，再验证 4053 条快速 burst、持续消费、双 lane 隔离、HTTP/ping 存活、数据帧与字节额度、跨重连、控制/未知 correlation 洪泛、畸形/超大帧，以及撤销/取消后的资源归零。已有背压用例应改为只关闭违规 lane，保留其超额关闭和资源清理断言。不能用增大 1200 控制额度或取消字节保护掩盖问题。

完整 Gateway 检查、Linux 镜像和真实冷浏览器回放属于发布门禁；当前生产授权不得作为单元测试数据。操作入口见 [Gateway 运维](../operations/WORKSPACE_GATEWAY.md)。

## 本机源码验证结果

本轮 Windows 上使用 Ambient 现有 Python 3.13 环境、隔离临时 SQLite 和合成授权验证，未安装依赖、未调用模型、未触碰真实节点：

- 修改前 focused Red：4 failed / 1 passed。正常逐帧消费在数据 index 1199 关闭整节点，4053 burst 未完成，控制/未知 correlation 限流拒绝未计数。
- 修改后完整 Gateway：91 passed；入口 renderer：14 tests passed；Ruff 与 git diff --check 通过。
- 4053 快速发送且持续消费完成；关闭 lane 后 1205 条合法在途数据继续计费并丢弃，另一 lane、HTTP、ping 存活，最终撤销关闭 Tunnel，资源归零。
- 节点帧/字节预算拒绝均计数并停止 Tunnel，重连不重置额度；tombstone 数量/期限和 pending queue put 的取消、关闭、撤销均有确定性覆盖。
- 仓库结构检查为 174 Markdown / 92 个既有问题；本次新增/修改文档没有未解析链接。已有 Starlette/httpx 弃用警告保留。

这些结果支持源码契约；新的 Linux 镜像、生产发布和真实浏览器从零游标回放尚待后续单独验收，不能用本机合成检查代替。原生产授权与数据库保持原样。
