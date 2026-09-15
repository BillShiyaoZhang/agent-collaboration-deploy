# 并行 worktree 的整合与发布

## 推荐流程

1. 每个任务从明确的基准提交创建独立分支，完成后提交全部成果，并记录测试结果。worktree 是工作目录，实际合并对象是分支或提交；未提交内容不会随分支合并。
2. 指定一个整合任务，创建 `codex/integrate-<date>` 分支。先合结构或公共接口调整，再逐个合功能和文档，每次解决冲突后检查关联路径、导入和构建工具。
3. 合并完整任务优先使用 `git merge --no-ff <task-branch>`，保留分支来源；仅选择个别独立提交时使用 `git cherry-pick <sha>`。不要通过互相覆盖工作目录来整合，也不要靠 `ours` / `theirs` 一次性丢弃一方改动。
4. 重跑组合后的相关测试和生产构建。每个分支分别通过测试，不能证明它们组合后仍然通过。
5. 先发布 SDK，再在 Platform 中固定最终 SDK SHA，随后发布 Platform / Web，最后更新并发布 Deploy。发布前检查 `git submodule status --recursive`。
6. 将验证完成的整合分支通过 PR 合入主分支。个人项目在已审阅并明确授权的情况下，也可以快进主分支并推送。遇到远程新增提交，重新整合并验证，不能强制覆盖。
7. 部署固定的 Deploy 提交及其子模块组合；保留数据库、身份、环境配置、旧镜像与回滚记录。先做隔离候选验收，再切换生产。

```sh
# 同一 Git 仓库中的任务分支示例；在专用整合 worktree 中运行。
git fetch origin
git switch -c codex/integrate-YYYYMMDD origin/main
git merge --no-ff codex/structure-task
git merge --no-ff codex/feature-task
git merge --no-ff codex/documentation-task
# 运行项目测试，提交冲突修复和最终子模块 SHA，再提交 PR。
git push -u origin codex/integrate-YYYYMMDD
```

SDK 默认分支是 `master`，其余三个仓库是 `main`，实际命令应按仓库调整。每个子模块本身都是独立仓库；只提交 Deploy 无法保存 SDK 中的源码修改。

## 任务交接约定

每个并行任务结束时提供：仓库路径、分支名、完整提交 SHA、是否仍有未提交文件、测试结果、依赖其他任务的变化，以及是否已经推送/部署。若任务处于 detached HEAD，应先给提交命名分支，避免后续清理时失去入口。

涉及目录重组时，尽量先完成并合入结构变动，再让功能任务从新基准开展工作。必须并行时，明确由整合任务处理重命名、文档相对路径和发布清单。

## 子模块与 squash

父仓记录子仓的精确 SHA。如果子仓 PR 使用 squash 或 rebase，最终主分支 SHA 可能改变；父仓必须更新到实际合入的 SHA，再提交和验证。不要在生产运行 `git submodule update --remote`，它会绕过 Deploy 固定的版本组合。

参考：[Git 分支合并](https://git-scm.com/book/en/v2/Git-Branching-Basic-Branching-and-Merging)、[Git 子模块](https://git-scm.com/book/en/v2/Git-Tools-Submodules)。
