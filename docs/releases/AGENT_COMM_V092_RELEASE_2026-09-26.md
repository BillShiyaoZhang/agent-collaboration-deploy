# 2026-09-26 Agent Comm v0.9.2：完整协作审批卡与官网接入包

本次发布将 v0.9.2 的正式客户端资产同步到官网，并将阿里云服务器的四仓源码检出更新到发布清单固定的提交。SDK Runtime 对 T06 协作接受问题卡补足方案编号、版本、主题、参与方、UTC 时段、条款摘要和不创建日历的边界，并使旧摘要卡失效。**这次服务器操作只更换公开下载文件并重建 nginx；运行中的 Web、Platform 容器没有升级。**官网文件更新也不会自动升级已有 Hermes 的 helper、Runtime 或连接器。

## 固定版本与发布状态

| 对象 | 固定值或实际状态 |
| --- | --- |
| Deploy 源码检出 | `aa85be794dbbdc21db9d9b26fdcf33bf9c24953e` |
| Web 子模块 | `c4a0e8923da0edcfef2891d49787ab133e442ab4` |
| Platform 子模块 | `d28d9a0d83f4d1ae352318934fa92a608c2d92ba` |
| SDK 子模块及标签 | `a30a193de7f4a258fc0889b1ea4fee6b1fca9124` / [`v0.9.2`](https://github.com/BillShiyaoZhang/agent-comm/releases/tag/v0.9.2) |
| Python 包 | `agent-comm-runtime 0.1.7`；`hermes-platform-agent-comm 1.5.9` |
| GitHub 发布 | [Actions run 36172645436](https://github.com/BillShiyaoZhang/agent-comm/actions/runs/36172645436) 成功；Release 已正式发布 16 项资产 |
| 生产容器 | nginx 按新目录重建；Web 容器 ID `635ba89ac56866202685e512a6cea569416ee6436a0e3fe5f5faca7010ea64ee`、Platform 容器 ID `8f80d3741e3df31d38cc27eefba48d2bc99075d3ae01a7a824aee08c8dd6012c` 在切换前后不变 |
| 签名策略 | 保持原已签发 `compliance` epoch 3，策略摘要 `6f9f7bdf26c5e7761cbe8c451a22fd11f9a448d912fa5bc3ae61c1e53f3ff5c4`；本次未改模式或密钥，也未重签策略 |

服务器更新前，根仓库及所有递归子模块工作区均无本地改动。根仓库从 `16b9d896b1c010137dc346141b23a41605094adc` 快进至上表提交，再按固定 gitlink 更新子模块；最终四仓提交符合 GitHub 清单且工作区干净。源码检出更新不等于生产 Platform 镜像更新，本次不以新 Platform gitlink 声称服务端运行了新代码。

## 正式资产与公网校验

GitHub Release 的 16 项资产逐一匹配 GitHub 资产元数据中的字节数和 SHA-256；列入 `release-manifest.json`、`SHA256SUMS` 的资产也分别与其记录一致。四个平台 ZIP 内的全部文件校验、`policy-trust.json` 信任锚及安装器 `--check-only --cross-platform-check` 均通过；源码 ZIP 的 `SOURCE_RELEASE.json` 与四仓固定提交一致。跨平台检查只证明包完整，不代表已在 Linux 或 macOS 原生安装或完成 Hermes 联调。

官网的五份 ZIP 来自这一正式 Release，`downloads/release-manifest.json` 与 GitHub `early-access-manifest.json` **逐字节相同**，SHA-256 为 `d3babead535af1fa95ce24bdd72bb7902d49412522e48d39e06998b8cbab0eb3`。切换后从公网 HTTPS 重新下载并核对长度与摘要：

| 官网文件 | 字节数 | SHA-256 |
| --- | ---: | --- |
| Windows amd64 ZIP | 12,561,700 | `4bd338b8de5f0980c98b38dc27df76af8ac98ab6f85a3d7878aa0c4fc6e7f238` |
| Linux amd64 ZIP | 12,477,248 | `f7824179930ca07be65c1d2a4fcbfe83feafa2b0b0b9733ef0d64d02ee83773e` |
| macOS Intel ZIP | 12,663,905 | `f33b611a6c1799943b2929418e6bab355d383f4b79faa969204bba5b1d730cbd` |
| macOS Apple Silicon ZIP | 11,854,708 | `167125b5992b1c246b833cbcfc71289ead704c4697423f81a527910a881f7c4d` |
| 源码 ZIP | 1,816,515 | `3a7940111c6b2a3c4dd7ea69f8d7fc6ecc9a8165bbcea71df93f3bddd934c118` |

原有邀请 PDF 未改动，公网仍返回 200。`/login`、`/healthz` 和 `/docs/` 也均返回 200；nginx 容器内 `/srv/downloads/release-manifest.json` 与公网清单摘要相同。

## 切换、回滚与验收边界

切换前的官网 v0.9.1 下载目录复制到服务器 `/root/agent-comm-releases/2026-09-26-v092/pre-cutover-downloads`，旧清单 SHA-256 为 `9ec13b903deb9973768bfa112d13845ca4cd9d70167172507abfabe29347d6c8`。旧目录 inode 另外保留在同一发布目录的 `pre-cutover-live-inode`。新文件先传入独立 staging，核对五份 ZIP 和清单的字节数、摘要及邀请 PDF 后，才替换目录并**仅重建 nginx**，让 bind mount 指向新 inode。Web、Platform 容器 ID 保持不变；未覆盖数据库、身份或现有用户文件。

第一次切换时，nginx 重建后立刻执行的本机回环 TLS 检查遇到启动就绪时序错误，触发回滚；错误处理曾重复进入回滚日志。随后只读核对确认旧 v0.9.1 目录和 nginx 挂载已恢复，公网 `/login`、`/healthz`、旧清单均返回 200，Web、Platform 容器未变。修正为单次回滚并加入有界 nginx 就绪重试后，第二次切换通过，公网五份 ZIP、清单与健康入口再次核验成功。若日后需要回退，先核对当前状态，将现行 `downloads` 移到新的版本化目录，再将保留的 `pre-cutover-live-inode` 移回 `downloads`，仅重建 nginx 并复查配置和公网 HTTPS；不得用旧数据库备份覆盖实时数据。

官网同步本身不会自动升级既有 Hermes；随后另从正式 Release 的 Windows ZIP 对两套隔离合成 Hermes 做了原位升级。两端各自五个 SQLite 库与六份静态身份文件先备份，`install.py --check-only` 通过后只重装各自 venv 的正式 wheel，原 URN、配对、T05 消息、既有 T06 协作和旧摘要卡失效状态均保持，Gateway 最终 connected/idle。第一次 Alice 重启由默认沙箱执行时无权读取其合成 profile 的插件文件，改在有权限的环境精确重启后恢复，正式 wheel 未回滚。`sdk-official-20260926/summary.json` 留有前后状态和插曲。

[生产合成 T06 验证记录](../verification/UX_2026-09-25.md)保留旧 Runtime 卡片缺条款的失败、候选 SDK 四卡双分支通过，以及**正式发布包**新 ID 双分支复测：拒绝轮 Bob 未发送 accept、双方未成约；接受轮 Alice 单方批准时未成约，Bob 独立批准同版后双方得到相同约定；新卡完整、跨账户隔离、页面错误 0，均无日历事件。正式 Windows 包的这两套合成环境验收已完成；Linux/macOS 原生安装和真人对审批文案的理解与决定仍未由本次测试覆盖。

本机忽略提交的审计证据位于 `build/releases/v092-official/`：`official-verification.json` 记录 16 项正式资产与包内校验，`public-verification.json` 记录公网六文件复取，`sync-evidence.md` 记录服务器提交、容器、备份及首次回滚顺序。该目录中的下载物和运行日志不提交仓库。
