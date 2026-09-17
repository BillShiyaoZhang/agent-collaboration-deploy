# 发布工具

发布工具需要 Python 3.11+ 和 Git，从仓库根目录运行。递归初始化子模块后，先在各组件仓库完成验证并提交，再由内到外提交子模块引用。构建器要求发布源仓库干净，包括未跟踪文件和子模块状态；不会将本地编辑或临时资产默默发布。

公共源码从已提交的 Git 对象读取，保留仓库记录的换行，排除密钥、实际环境文件、数据库、日志、依赖和构建产物。已跟踪的 `.env.example` 占位模板会保留，其余 `.env*` 文件均排除。每份发布清单记录源提交和文件 SHA-256；校验值用于核对完整性，下载来源仍需可信。

## Web 发布快照

```sh
python tools/release/package_web_release.py --release RELEASE_ID
```

默认输出 `build/releases/web-release.tar.gz`，可用 `--output` 指定其他位置。包内包括：

- `web/`：完整的 Web 可发布源码快照。
- `docker-compose.yml`、`deploy/nginx/nginx.conf`、`deploy/platform/config.yaml`：待审阅的部署配置。
- `manifest.json`：`mode: full_snapshot`、源提交、逐文件校验值与部署语义。

该快照应解压到新的源码目录并构建，审阅配置后再部署。它没有删除补丁清单，不能作为覆盖包直接叠加到旧源码上；旧源码、在线数据库和挂载数据的切换由部署流程管理。本工具只生成文件，不连接或修改服务器。

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

```sh
python tools/release/build_early_access.py --release RELEASE_ID
```

输出到 `downloads/`，可用 `--output-dir` 指定独立发布目录。每份 ZIP 保持 `install.py`、`configure_hermes.py` 和 README 并列，包含对应 helper、两个 wheel 及 `SHA256SUMS.json`。脚本逐字节核对 wheel 与当前源码，解压后执行安装脚本的 `--check-only`。源码 ZIP 包括 deploy、Web、platform 和 SDK 四个仓库及其提交清单。

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
