# Ship

把当前已提交分支送进本仓的远端 PR 闭环:local preflight -> PR body / local review -> pre-push Trellis finalization -> push final head -> Draft PR -> CI wait -> remote review -> squash merge gate -> handoff。

`/trellis:ship` 承接 `.trellis/workflow.md` Phase 3.4 commit 之后的远端交付面。它支持两种合法入口:分支已提前完成 `/trellis:finish-work` 并包含 archived task evidence;或分支仍有 active task,由 `/trellis:ship` 在第一次 push / PR CI 前执行 Trellis finalization,把可入库的 `.trellis` 归档/任务证据放进同一个 PR 的最终 head(`.trellis/` 由主仓直接跟踪)。用户已经要求 ship 时,不要再要求先运行 `/trellis:finish-work`;finish-before-ship 只是本地先收尾的一种可选路径,不是避免重复 CI 的必要前置步骤。

---

## 先读

运行或人工读取以下上下文:

```bash
python3 ./.trellis/scripts/task.py current
git status --short --branch
```

若 `task.py current` 失败,先不要手写 `.trellis/.runtime` 或伪造 active task。已完成 finalization 的分支允许由 Step 1 preflight 根据本分支 diff 中的 archived task 证据判定。

必须遵守:

- `.trellis/spec/guides/git-pr-sop.md`
- 当前任务的 `prd.md` / `design.md` / `implement.md`

## 授权语义

调用 `/trellis:ship` 仅表示用户授权:

- push 当前任务分支;
- 创建或更新 PR;
- 读取 CI、review、comments;
- 在 CI 或 remote review 失败时继续修复并追加提交;
- 若当前分支仍有 active task,在 pre-push finalization 阶段运行 `/trellis:finish-work` 或等价脚本,精确提交可入库的 Trellis bookkeeping,并把该 bookkeeping 放进第一次 push 的最终 head。

调用 `/trellis:ship` 同时授权(全程自动执行,不再逐步询问):

- CI 全绿且无 blocking 后按 SOP squash merge;
- merge 后删除远端分支、切回 main 并 `--ff-only` 同步、删除本地任务分支、`fetch --prune`。

调用 `/trellis:ship` 不授权:

- force-push;
- 清理 worktree(如有,仍需单独授权);
- 跳过 Trellis finalization。

全程只有两个硬停点:Step 1 preflight 失败;CI 修复循环超过 3 轮或出现实质范围变化(Step 5/6)。

若分支已经提前 finish 并包含可审查的 archived task evidence,`/trellis:ship` 不会再重复 finalization。若提前 finish 后远端 CI / remote review 暴露实质范围问题,不要在 completed task 下静默继续大改;停止并请求人工裁决,通常开 follow-up task。

merge 由本 command 在 CI 全绿且无 blocking 后自动执行,固定 squash——调用 ship 即授权合并。`rebase` / merge commit 属于偏离 SOP,必须用户明确说「偏离 SOP,用 rebase/merge commit」,且不通过本 command 执行。

## Step 1: Preflight

先运行硬检查:

```bash
python3 ./scripts/trellis_ship.py preflight --base main
```

必须全部满足:

1. 当前分支不是 `main`、`master` 等共享基线。
2. 工作区干净。
3. 当前分支相对 `origin/main` 有提交。
4. 当前 Trellis task 的 `branch` 等于当前 git branch,且 `base_branch` 是 `main`;或当前没有 active task,但本分支相对 `origin/main...HEAD` 的 diff 中包含匹配 `branch=<当前分支>`、`base_branch=main`、`status=completed` 的 `.trellis/tasks/archive/**/task.json`。
5. `origin/main` 最新 CI run 结论不是 failure(fail-open:离线/查不到不拦;确需在红 main 上继续时加 `--skip-main-check`)。

第二种状态表示 Trellis finalization 已经提前完成并随分支入库。它不能通过手写 `.trellis/.runtime` 达成;必须来自可审查的 archived task 文件。

任何一项失败都停止,不 push。

## Step 2: PR Body

准备或更新 PR 描述,必须使用 `.github/pull_request_template.md` 的章节顺序。标题必须是英文 Conventional Commits。

在创建或更新 PR 前,本地模拟 CI 的 PR 描述检查:

```bash
python3 ./scripts/check_pr_description.py \
  --title "<type>(<scope>): <summary>" \
  --body-file <pr-body.md>
```

Draft 状态:GitHub 原生支持 Draft PR,用 `--draft` 创建即可;不要把 `WIP:` 放进标题,避免破坏 Conventional title 校验。

## Step 3: Local Self-review + Pre-push Trellis Finalization

在任何远端写操作前,先做 fresh-eyes local review。Review 输入:

```bash
git diff origin/main...HEAD
```

Review 输出必须按以下前缀分组:

- `blocking:` 正确性、安全、数据、CI、明确行为回归、违反 spec/SOP/ship gate。
- `suggestion:` 具体但非阻塞的改进。
- `nit:` 纯风格或措辞。

若有任何 `blocking:`:

1. 停止 ship。
2. 列出 blocking findings。
3. 在 active task 下修复、验证、commit。
4. 回到 Step 1 重新 preflight。

若无 `blocking:`,继续确认 Trellis bookkeeping 会进入第一次 push 的最终 head。

若 Step 1 preflight 使用的是 archived task evidence,说明 finalization 已提前完成;确认本地无 active task、工作区干净后跳过本步骤剩余部分,进入 Step 4。

只有当 Step 1 preflight 使用的是 active task,才在这里完成 Trellis bookkeeping。这样 `.trellis/tasks/archive/**` 等可入库的任务归档会随第一次 push 进入同一个 PR,而不是 CI 后再追加一次 push 触发第二轮 CI。

执行:

```bash
/trellis:finish-work
```

若当前平台没有 `/trellis:finish-work` command,则按该 command 的语义手工执行:

```bash
python3 ./.trellis/scripts/task.py archive <current-task>
python3 ./.trellis/scripts/add_session.py --title "<session title>" --commit "<work-commit-hash>" --summary "<summary>"
```

本仓默认 `session_auto_commit: false`,因此上述命令可能只写文件/移动任务,不会自动 commit。随后必须:

1. 查看 `git status --short`。
2. 只 stage 可入库 Trellis bookkeeping(精确路径,禁止 `git add .trellis/`):
   - `.trellis/tasks/archive/**`
   - 必要的 `.trellis/tasks/<parent-or-child>/task.json`
   - `.trellis/workspace/**` session index 更新(单人开发默认 workspace 入库)
3. 不 stage:
   - `.trellis/.runtime/**`
   - 各平台 cache/runtime/local settings
4. 提交:

```bash
git add <exact-trellis-bookkeeping-paths>
git commit -m "chore(task): archive <task-name>"
```

5. 重新运行本地 preflight:

```bash
python3 ./scripts/trellis_ship.py preflight --base main
```

重新 preflight 必须改为使用 archived task evidence,且工作区必须干净。若失败,停止并在本地修复;不得 push,不得创建或更新 PR。若 Step 2 的 PR body 因 finalization 信息需要更新,回到 Step 2 重新跑本地 PR 描述检查。

## Step 4: Push + Draft PR

推送当前分支的最终 head:

```bash
git push -u origin "$(git branch --show-current)"
```

查找是否已有同分支 PR:

```bash
gh pr list --head "$(git branch --show-current)" --json number,url,isDraft --jq '.[0]'
```

没有现有 PR 时创建 Draft PR:

```bash
gh pr create --draft \
  --title "<type>(<scope>): <summary>" \
  --body-file <pr-body.md>
```

已有 PR 时更新标题和 body:

```bash
gh pr edit <pr-number> \
  --title "<type>(<scope>): <summary>" \
  --body-file <pr-body.md>
```

创建或更新后,报告 PR 编号、URL、head sha、Draft 状态。

## Step 5: CI Wait

等待 GitHub 状态检查:

```bash
python3 ./scripts/trellis_ship.py wait-ci --number <pr-number> --timeout 900 --interval 20
```

(交互场景可用 `gh pr checks <pr-number> --watch` 观察各 check 明细。)

处理规则:

- `success`:进入 remote review / AI Review triage。
- `failure` / `error`:进入自动修复循环(不询问用户):读取失败日志(`gh run view <run-id> --log-failed`,run-id 见失败 check 的 detailsUrl 或 `gh pr checks <pr-number>`),修复后追加 commit + push,再从 Step 5 重新等待。修复循环最多 3 轮;第 3 轮后仍失败则停止,报告失败 check、已尝试的修复与 PR URL,等待人工介入。{{formatter}} lint/format 类失败用仓内格式化命令修复。
- timeout:停止,报告 PR URL 和最后一次状态。

CI wait helper 会输出 PR head sha 与非 success/skipped 的 check 列表。若状态看起来来自旧事件或旧 run,不要凭感觉跳过;优先读取日志与明细。若状态聚合仍保留已修复的旧失败 check,追加一个普通空 commit 重触发干净 head 是可接受的补救方式:

```bash
git commit --allow-empty -m "chore(ci): retrigger pr checks"
git push
```

不要在 CI 红时进入 merge gate。

## Step 6: Remote Review / AI Review Triage

读取远端 review / comments,并对 CI 后的最终远端状态做一次收口确认。若平台支持子 agent,派 reviewer(Claude Code:`general-purpose` 子 agent);否则主 agent 切换到 review 口径自查。

AI Review(平台 bot 或外部审查工具)是 advisory,不是代码修改队列。处理规则:

- 最多追一轮 AI Review;一轮处理后若继续追加边界建议或风格建议,在 PR 描述中记录裁决,不继续循环改代码。
- 只有 `blocking` 或真实高信号问题触发代码修改:CI 失败、真实密钥、安全风险、数据风险、明确逻辑回归、违反 spec/SOP/ship gate。
- `suggestion:` / `nit:` 默认不改代码;写入 PR 描述的 AI Review 处理段,说明采纳、不采纳或 follow-up。
- 不得因为审查工具的总状态写「需要修改」,就自动把所有评论转成代码改动;必须逐条按上面规则分类。
- 非阻塞但有价值的建议进入 `docs/BACKLOG.md` / follow-up,不拖住当前 ship。

Review 输入可包括:

```bash
git diff origin/main...HEAD
gh pr view <pr-number> --comments
```

Review 输出必须按以下前缀分组:

- `blocking:` 正确性、安全、数据、CI、明确行为回归、违反 spec/SOP。
- `suggestion:` 具体但非阻塞的改进。
- `nit:` 纯风格或措辞。

若有任何 `blocking:`:

1. 停止 ship。
2. 列出 blocking findings。
3. 若是当前任务范围内的真实阻塞问题,修复、验证、追加 commit、push,然后回到 Step 5。
4. 若问题意味着实质范围变化或与已完成任务证据冲突,停止并请求人工裁决,通常开 follow-up task,不在 completed task 下静默继续大改。
5. PR body、CI 配置拼写、generated adapter 漂移等轻微交付问题可以追加修复 commit;修复后同样回到 Step 5。

若无 blocking:

1. 把 AI Review 评论的采纳、不采纳或 follow-up 结论写入 PR 描述的 AI Review 处理段。
2. 把 PR 从 Draft 转 ready:`gh pr ready <pr-number>`。
3. 进入 merge gate。

## Step 7: Squash Merge Gate

合并前再次收集:

```bash
gh pr view <pr-number> --json number,state,title,baseRefName,isDraft,mergeable,mergeStateStatus

python3 ./scripts/trellis_ship.py wait-ci --number <pr-number> --timeout 1 --interval 1
```

条件满足(CI 全绿、mergeable、无 blocking)即直接执行,不再询问用户——ship 调用本身就是合并授权:

```bash
python3 ./scripts/trellis_ship.py merge --number <pr-number> --cleanup
```

若 PR 落后于 main(mergeStateStatus=BEHIND),merge 会自动 `gh pr update-branch`、重等 CI 通过后再合并——分支保护对管理员也已强制(enforce_admins),真实组合必须先被测过。

`--cleanup` 在合并成功后自动:删除远端分支、切回 main、`git pull --ff-only`、按 head-oid 校验删除本地任务分支、`git fetch --prune`。

该脚本固定调用 `gh pr merge --squash`,并在远端状态不是 open / mergeable / non-draft / base=main,或本地 finalization 未完成时拒绝执行。

若 merge 失败:

1. 不回滚 Trellis finalization commit,不把 archived task 移回 active。
2. PR 保持 open。
3. 报告失败原因:权限、base 漂移、CI 状态、mergeable 状态或 GitHub 临时错误。
4. 若是 base 漂移或本地/远端状态变化,先同步/修复,必要时追加 commit + push。
5. 回到 Step 5 再等 CI,成功后从 Step 7 merge gate 重试。
6. 若长期无法合并,停止并请求人工裁决;可开 follow-up task 记录阻塞,不在本 command 中擅自改写历史或删除分支。

## Step 8: Handoff

`merge --cleanup` 已自动完成分支清理与同步。确认收尾状态:

```bash
git status --short --branch
```

报告:

- PR 编号和 merge sha;
- CI 最终状态;
- 本地当前分支和工作区状态;
- 已自动完成:远端分支删除、切回 main + `--ff-only` 同步、本地任务分支删除(head-oid 校验通过时)、remote prune;
- worktree 未自动清理(如有,需单独授权);
- Trellis finalization 已在第一次 push 前完成并随 PR 入库(workspace session index 一并入库,另一台机器 `git pull` 即可同步)。

