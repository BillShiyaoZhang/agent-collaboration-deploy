# 发布工具

发布工具需要 Python 3.11+ 和 Git，从仓库根目录运行。递归初始化子模块后，先在各组件仓库完成验证并提交，再由内到外提交子模块引用。构建器要求发布源仓库干净，包括未跟踪文件和子模块状态；不会将本地编辑或临时资产默默发布。

公共源码从已提交的 Git 对象读取，保留仓库记录的换行，排除密钥、实际环境文件、数据库、日志、依赖和构建产物。已跟踪的 `.env.example` 占位模板会保留，其余 `.env*` 文件均排除。每份发布清单记录源提交和文件 SHA-256；校验值用于核对完整性，下载来源仍需可信。

## Web 发布快照

```sh
python tools/release/package_web_release.py --release RELEASE_ID
```

默认输出 `build/releases/web-release.tar.gz`，可用 `--output` 指定其他位置。包内包括：

- `web/`：完整的 Web 可发布源码快照，含 Web 自身 `docs/`。
- `docs/`、`agent-comm-platform/docs/`、`agent-comm-platform/agent-comm/docs/`：其余三仓在固定提交的原始文档，供官网 `/docs/source/` 只读挂载；没有另行改写或手工复制 Markdown。
- `docker-compose.yml`、`deploy/nginx/nginx.conf`、`deploy/nginx/docs-source.conf`、`deploy/platform/config.yaml`：待审阅的部署配置。
- `manifest.json`：`mode: full_snapshot`、四仓源提交、逐文件校验值与部署语义。

该快照应解压到新的源码目录，将 `web/` 作为 Web 源码目录并构建，审阅配置后再部署。Platform 服务仍需从清单固定提交取得完整源码；包内 Platform 与 SDK 仅包含供官网挂载的 `docs/`，不能用来构建 Platform 服务。它没有删除补丁清单，不能作为覆盖包直接叠加到旧源码上；旧源码、在线数据库和挂载数据的切换由部署流程管理。本工具只生成文件，不连接或修改服务器。

## 接入包与开发源码

准备 runtime 与 Hermes connector wheel，版本由各自 `pyproject.toml` 或静态 `setup.py` 提取：

```sh
python -m pip wheel --no-deps --no-build-isolation agent-comm-platform/agent-comm/python --wheel-dir agent-comm-platform/agent-comm/python/dist
python -m pip wheel --no-deps --no-build-isolation agent-comm-platform/agent-comm/connectors/hermes-platform --wheel-dir agent-comm-platform/agent-comm/connectors/hermes-platform/dist
```

在构建环境安装所需的 setuptools/wheel。helper 从 SDK 的 `./cmd/helper` 构建；按目标设置 Go 的 `GOOS`/`GOARCH`，将四份产物放入 `build/early-access/`（或通过 `--helper-dir` 指定）：

| 目标 | 构建输入文件名 | ZIP 内执行文件名 |
| --- | --- | --- |
| windows / amd64 | `agent-comm-helper.exe` | `agent-comm-helper.exe` |
| linux / amd64 | `agent-comm-helper-linux-amd64` | `agent-comm-helper` |
| darwin / amd64 | `agent-comm-helper-darwin-amd64` | `agent-comm-helper` |
| darwin / arm64 | `agent-comm-helper-darwin-arm64` | `agent-comm-helper` |

为 v2 接入包先由发布者从**平台之外**核对策略根公钥和预期 Platform Peer ID，创建仅含公开资料的本地 JSON（未经审阅不要提交；绝不能放策略根私钥）。例如将以下模板保存为受限的 `build/policy-trust-RELEASE_ID.json`，把占位值替换为实际核对结果：

```json
{
  "schema_version": 1,
  "release": "RELEASE_ID",
  "platform_origin": "https://agent-communication.online",
  "platform_peer_id": "EXPECTED_PLATFORM_PEER_ID",
  "policy_root_public_key_hex": "64_LOWERCASE_HEX_CHARACTERS",
  "verification_note": "Release owner independently verified the offline root and Platform identity"
}
```

```sh
python tools/release/build_early_access.py --release RELEASE_ID --policy-trust build/policy-trust-RELEASE_ID.json
```

经发布者审阅的**公开**版本可将这份仅含公钥的资料固定在仓库的 `tools/release/trust/RELEASE_ID.json`，供 GitHub Actions 从确切的部署仓库提交重现构建；`v0.8.0` 的输入是 [`trust/v0.8.0.json`](trust/v0.8.0.json)。此处只存公钥和核对来源说明，不存根私钥、网关私钥或用户许可。CI 必须核对该文件的 `release` 与 SDK tag 相同，并验证四个包内文件和校验清单均匹配该固定输入；后续版本各自新增文件，不覆盖旧版本信任资料。

输出到 `downloads/`，可用 `--output-dir` 指定独立发布目录。每份 ZIP 保持 `onboard_hermes.py`、`install.py`、`configure_hermes.py`、发布生成的 `policy-trust.json` 和 README 并列，包含对应 helper、两个 wheel 及 `SHA256SUMS.json`；策略根公钥、Peer ID、HTTPS origin 和核对记录均由这份文件提供，校验清单覆盖其确切字节。构建器缺少或发现畸形的信任资料时拒绝出包。自动入口先将它幂等固定到原 helper 身份，再启动并确认 helper 真正加载相同根和已验签的平台 ID，随后才处理注册、Web 确认后的签名配对与 Gateway 启动；已运行旧 helper 不能未经安全停止/重启而被静默复用。单独的安装和配置入口继续支持已有客户端。脚本逐字节核对 wheel 与当前源码，解压后执行安装脚本的 `--check-only`。源码 ZIP 包括 deploy、Web、platform 和 SDK 四个仓库及其提交清单。

包内 SHA 清单只证明**已取得的包内部**没有相互不一致；发布时仍须从可信发布渠道核对顶层 ZIP 的哈希。只有线上已部署并验证签名 `private` 策略且两端真实接入通过后，才将 v2 ZIP 同步到公开下载目录；构建候选包本身不改变现有 r2 下载或生产策略。

`--release` 默认为当天 UTC 日期，可传版本号或明确的发布标识。包内 Python 版本来自项目 metadata，安装脚本按发布清单核对，不需要手动同步版本常量。归档文件时间戳来自 deploy 提交时间。

邀请 PDF 由维护者另行审阅并提供，构建不再依赖旧邀请生成器。需要随本次发布分发时显式传入：

```sh
python tools/release/build_early_access.py --release RELEASE_ID --invitation /path/to/reviewed-invitation.pdf
```

省略该参数时，本次清单不包含 PDF。重复使用输出目录时，以本次 `release-manifest.json` 列出的文件为发布范围；历史残留文件不代表本次发布产物。建议每次使用独立输出目录，再按清单同步到下载服务。

## GitHub 正式发布

SDK 的 Release 工作流发布 helper、两个 wheel、四个平台接入包、源码与文档 ZIP。先提交 SDK，再由内向外更新 Platform 和本仓库的子模块引用，全部推送成功后才推新的 SDK 语义版本标签。标签触发时会解析本仓库 `main` 的确切提交，并拒绝其 SDK 引用与版本标签不一致的组合。

从 Actions 手动重跑时必须选择确切的版本标签和本仓库提交；不能将 `main` 当版本号，也不要移动已发布标签。版本说明放在 SDK 的 `docs/releases/TAG.md`。工作流通过测试、版本一致性、wheel/source 与完整包校验后才发布。

GitHub 的 `release-manifest.json` 是 SDK 下载器使用的资产清单；`early-access-manifest.json` 是安装包/源码 ZIP 清单。同步官网时使用 GitHub 已验证的相同 ZIP，并把 `early-access-manifest.json` 作为官网 `downloads/release-manifest.json`，不要用 SDK 清单覆盖官网清单。

## 测试

```sh
python -m unittest discover -s tools/release/tests -v
python -m unittest discover -s tools/release/early_access/tests -v
```

发布测试在临时 Git 仓库中验证私有资产排除、脏仓库拒绝、完整快照与 wheel/source 一致性。接入测试验证文件校验、当前 Python 安装目标、配置备份、授权与远程配对。交叉编译成功与文件校验通过不替代各系统上的真实宿主测试。
