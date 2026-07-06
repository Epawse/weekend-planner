#!/usr/bin/env python3
"""GitHub Trellis ship helper.

This script backs the project-local `/trellis:ship` command. It intentionally
handles only hard, testable checks. Human-facing orchestration remains in
`.trellis/commands/ship.md`.

Remote operations are implemented with the GitHub CLI (`gh`).
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path


DEFAULT_REPO = "Epawse/weekend-planner"
DEFAULT_BASE = "main"
# Break-glass for legitimate multi-PR incremental delivery under one active
# task: merging a delivered slice while the parent task stays in_progress.
# Aligns with TRELLIS_ALLOW_PARALLEL in the planning gate.
INCREMENTAL_BREAK_GLASS_ENV = "TRELLIS_SHIP_INCREMENTAL"
SHARED_BRANCHES = {"main", "master"}
BRANCH_PATTERN = re.compile(
    r"^(feat|fix|hotfix|docs|chore|test|refactor|ci|build|perf|style|revert)/"
    r"[a-z0-9][a-z0-9-]*$"
)
# Terminal CI conclusions that mean the run can never turn green on its own.
FAILED_CHECK_STATES = {
    "FAILURE",
    "ERROR",
    "CANCELLED",
    "TIMED_OUT",
    "ACTION_REQUIRED",
    "STARTUP_FAILURE",
}
PASSED_CHECK_STATES = {"SUCCESS", "NEUTRAL", "SKIPPED", "EXPECTED"}


@dataclass
class CommandResult:
    returncode: int
    stdout: str
    stderr: str


@dataclass
class PullInfo:
    number: str | None
    state: str | None
    title: str | None
    base_ref: str | None
    head_sha: str | None
    head_ref: str | None
    is_draft: bool | None
    mergeable: str | None
    merge_state_status: str | None


@dataclass
class CiStatus:
    state: str
    context: str
    description: str


@dataclass
class CiReport:
    state: str | None
    statuses: list[CiStatus]
    output: str


@dataclass
class FinalizedTaskEvidence:
    task_path: Path
    branch: str
    base_branch: str


def run_command(args: list[str], cwd: Path | None = None) -> CommandResult:
    result = subprocess.run(
        args,
        cwd=cwd,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    return CommandResult(result.returncode, result.stdout, result.stderr)


def run_git(args: list[str], repo_root: Path) -> CommandResult:
    return run_command(["git", "-c", "i18n.logOutputEncoding=UTF-8", *args], cwd=repo_root)


def git_stdout(repo_root: Path, args: list[str]) -> str | None:
    result = run_git(args, repo_root)
    if result.returncode != 0:
        return None
    return result.stdout.strip()


def build_gh_command(*args: str) -> list[str]:
    return ["gh", *args]


def build_merge_command(
    repo: str,
    number: str,
    commit_title: str | None = None,
    delete_branch: bool = False,
) -> list[str]:
    # GitHub PR SOP locks the merge style to squash; rebase / merge commit are
    # explicit SOP deviations handled outside this helper. Remote branch
    # deletion rides along only when the caller passes --cleanup (the ship
    # auto flow); the bare merge subcommand keeps the old conservative shape.
    command = build_gh_command(
        "pr",
        "merge",
        number,
        "--repo",
        repo,
        "--squash",
    )
    if delete_branch:
        command.append("--delete-branch")
    if commit_title:
        command.extend(["--subject", commit_title])
    return command


def build_create_pull_command(
    repo: str,
    *,
    base: str,
    head: str,
    title: str,
    body_file: str,
) -> list[str]:
    # gh expands --body-file natively, so file-based bodies are the safe default.
    return build_gh_command(
        "pr",
        "create",
        "--repo",
        repo,
        "--base",
        base,
        "--head",
        head,
        "--draft",
        "--title",
        title,
        "--body-file",
        body_file,
    )


def build_edit_pull_command(
    repo: str,
    *,
    number: str,
    title: str | None = None,
    body_file: str | None = None,
) -> list[str]:
    command = build_gh_command(
        "pr",
        "edit",
        number,
        "--repo",
        repo,
    )
    if title is not None:
        command.extend(["--title", title])
    if body_file is not None:
        command.extend(["--body-file", body_file])
    return command


def build_ci_checks_command(number: str, repo: str | None = None) -> list[str]:
    command = build_gh_command("pr", "checks", number)
    if repo:
        command.extend(["--repo", repo])
    return command


def build_ci_logs_command(run_id: str) -> list[str]:
    return build_gh_command("run", "view", run_id, "--log-failed")


def parse_pull_info(output: str) -> PullInfo:
    """Parse `gh pr view --json ...` output into PullInfo."""
    try:
        data = json.loads(output)
    except json.JSONDecodeError:
        data = {}
    number = data.get("number")
    return PullInfo(
        number=str(number) if number is not None else None,
        state=(data.get("state") or None),
        title=data.get("title"),
        base_ref=data.get("baseRefName"),
        head_sha=(data.get("headRefOid") or None),
        head_ref=data.get("headRefName"),
        is_draft=data.get("isDraft"),
        mergeable=(data.get("mergeable") or None),
        merge_state_status=(data.get("mergeStateStatus") or None),
    )


def aggregate_ci_state(rollup: list[dict]) -> str | None:
    """Collapse a GitHub statusCheckRollup list to success/failure/pending."""
    if not rollup:
        return "success"
    pending = False
    for item in rollup:
        # CheckRun: status + conclusion; StatusContext: state.
        conclusion = (item.get("conclusion") or item.get("state") or "").upper()
        status = (item.get("status") or "").upper()
        if conclusion in FAILED_CHECK_STATES:
            return "failure"
        if status and status != "COMPLETED":
            pending = True
            continue
        if conclusion in PASSED_CHECK_STATES:
            continue
        if not conclusion or conclusion == "PENDING":
            pending = True
    return "pending" if pending else "success"


def parse_ci_statuses(rollup: list[dict]) -> list[CiStatus]:
    """Break a GitHub statusCheckRollup list into per-check statuses."""
    statuses: list[CiStatus] = []
    for item in rollup:
        state = (item.get("conclusion") or item.get("state") or item.get("status") or "").lower()
        if not state:
            continue
        if state == "in_progress" or state == "queued" or state == "waiting":
            state = "pending"
        context = item.get("name") or item.get("context") or "unknown"
        description = item.get("description") or item.get("detailsUrl") or ""
        statuses.append(CiStatus(state=state, context=context, description=description))
    return statuses


def format_ci_blockers(statuses: list[CiStatus]) -> str:
    blockers = [
        status
        for status in statuses
        if status.state not in {"success", "skipped", "neutral", "expected"}
    ]
    if not blockers:
        return "CI contexts: all parsed contexts are success/skipped"
    return "CI blocking contexts: " + "; ".join(
        f"{status.state}:{status.context}"
        + (f" ({status.description})" if status.description else "")
        for status in blockers
    )


def evaluate_preflight(
    *,
    branch: str | None,
    dirty_paths: list[str],
    ahead_count: int | None,
    task_branch: str | None,
    task_base_branch: str | None,
    expected_base: str,
    task_present: bool = False,
    finalized_task: FinalizedTaskEvidence | None = None,
) -> list[str]:
    errors: list[str] = []
    if not branch:
        errors.append("当前不在可识别的本地分支上。")
    elif branch in SHARED_BRANCHES:
        errors.append(f"不能从共享基线分支 `{branch}` ship。")
    elif not BRANCH_PATTERN.match(branch):
        errors.append(
            f"分支名 `{branch}` 不符合 SOP："
            "<type>/<short-name>，type 用 feat/fix/hotfix/docs/chore/test/refactor/ci/build/perf/style/revert。"
        )

    if dirty_paths:
        errors.append("工作区不干净：" + ", ".join(dirty_paths))

    if ahead_count is None:
        errors.append(f"无法确认当前分支相对 origin/{expected_base} 的 ahead commit。")
    elif ahead_count <= 0:
        errors.append(f"当前分支相对 origin/{expected_base} 没有待 ship 的提交。")

    if task_branch:
        if branch and task_branch != branch:
            errors.append(
                f"活动任务分支 `{task_branch}` 与当前 git 分支 `{branch}` 不一致。"
            )
        if task_base_branch != expected_base:
            errors.append(
                f"活动任务 base_branch `{task_base_branch}` 不是 `{expected_base}`。"
            )
    elif task_present:
        errors.append("活动任务未记录 branch。")
        if task_base_branch != expected_base:
            errors.append(
                f"活动任务 base_branch `{task_base_branch}` 不是 `{expected_base}`。"
            )
    elif not finalized_task:
        errors.append(
            "没有活动 Trellis task，也没有当前分支已归档任务的可审查证据。"
        )

    return errors


def validate_pull_ready(info: PullInfo, *, expected_base: str) -> list[str]:
    errors: list[str] = []
    state = (info.state or "").upper()
    if state != "OPEN":
        errors.append(f"PR 状态不是 open：{info.state}")
    if info.base_ref != expected_base:
        errors.append(f"PR 目标分支不是 {expected_base}：{info.base_ref}")
    mergeable = (info.mergeable or "").upper()
    if mergeable == "CONFLICTING":
        errors.append("PR 不可合并：存在冲突（CONFLICTING）。")
    elif mergeable not in {"MERGEABLE"}:
        errors.append(f"PR mergeable 状态未就绪：{info.mergeable}（GitHub 可能仍在计算，稍后重试）。")
    if info.is_draft is not False:
        errors.append(f"PR 仍是 Draft：isDraft={info.is_draft}")
    merge_state = (info.merge_state_status or "").upper()
    if merge_state in {"DIRTY", "BLOCKED"}:
        errors.append(f"PR 被阻塞：mergeStateStatus={info.merge_state_status}")
    return errors


def load_active_task(repo_root: Path) -> tuple[str | None, str | None, Path | None, str | None]:
    current = run_command(
        ["python3", ".trellis/scripts/task.py", "current"],
        cwd=repo_root,
    )
    if current.returncode != 0:
        detail = current.stderr.strip() or current.stdout.strip()
        return None, None, None, detail or "task.py current failed"
    task_path_text = current.stdout.strip().splitlines()[-1].strip()
    task_path = (repo_root / task_path_text).resolve()
    task_json = task_path / "task.json"
    if not task_json.is_file():
        return None, None, task_path, f"task.json not found: {task_json}"
    try:
        data = json.loads(task_json.read_text(encoding="utf-8"))
    except Exception as exc:  # pragma: no cover - defensive diagnostics
        return None, None, task_path, f"failed to read task.json: {exc}"
    return data.get("branch"), data.get("base_branch"), task_path, None


def load_finalized_task_evidence(
    repo_root: Path,
    *,
    branch: str | None,
    expected_base: str,
) -> FinalizedTaskEvidence | None:
    """Find archived-task evidence for the current branch in the branch diff.

    `.trellis/` is tracked by the main repo, so a finalized branch carries its
    archived task.json in `origin/<base>...HEAD` — reviewable evidence that
    cannot be faked by writing local runtime state.
    """
    if not branch:
        return None

    diff_output = git_stdout(
        repo_root,
        [
            "diff",
            "--name-only",
            f"origin/{expected_base}...HEAD",
            "--",
            ".trellis/tasks/archive",
        ],
    )
    if diff_output is None:
        return None

    for relative in diff_output.splitlines():
        relative = relative.strip()
        if not relative.endswith("/task.json"):
            continue

        task_json = repo_root / relative
        if not task_json.is_file():
            continue

        try:
            data = json.loads(task_json.read_text(encoding="utf-8"))
        except Exception:
            continue

        if (
            data.get("status") == "completed"
            and data.get("branch") == branch
            and data.get("base_branch") == expected_base
        ):
            return FinalizedTaskEvidence(
                task_path=task_json.parent,
                branch=branch,
                base_branch=expected_base,
            )

    return None


def validate_local_merge_ready(repo_root: Path) -> list[str]:
    errors: list[str] = []

    status = git_stdout(repo_root, ["status", "--porcelain"])
    dirty_paths = [line for line in (status or "").splitlines() if line.strip()]
    if dirty_paths:
        errors.append("本地工作区不干净：" + ", ".join(dirty_paths))

    unpushed = git_stdout(repo_root, ["rev-list", "--count", "@{u}..HEAD"])
    if unpushed is None:
        errors.append("无法确认当前分支是否还有未 push 提交；请先设置 upstream 并 push。")
    elif unpushed != "0":
        errors.append(f"当前分支还有 {unpushed} 个未 push 提交。")

    current = run_command(["python3", ".trellis/scripts/task.py", "current"], cwd=repo_root)
    if current.returncode == 0 and current.stdout.strip():
        active = current.stdout.strip().splitlines()[-1].strip()
        if os.environ.get(INCREMENTAL_BREAK_GLASS_ENV, "").strip() not in ("", "0"):
            # Multi-PR incremental delivery: merge a delivered slice while the
            # parent task legitimately stays in_progress. Downgrade the blocker
            # to a recorded warning instead of refusing the merge.
            print(
                f"warning: incremental merge under active task `{active}` "
                f"（{INCREMENTAL_BREAK_GLASS_ENV}=1 破玻璃）——多 PR 增量交付通道，"
                "parent 未收尾即 merge；确认这是有意的分批交付。",
                file=sys.stderr,
            )
        else:
            errors.append(
                f"仍有活动 Trellis task `{active}`；"
                "先在 `/trellis:ship` 的 finalization 阶段运行 `/trellis:finish-work`，"
                "提交并 push 可入库的 Trellis bookkeeping 后再 merge。"
                "（多 PR 增量交付：设 TRELLIS_SHIP_INCREMENTAL=1 破玻璃。）"
            )

    return errors


def fetch_base_branch_health(repo: str, base: str) -> str | None:
    """Aggregate check-run health of the base branch HEAD commit: 'failure'
    if any completed check failed, 'in_progress' while running, 'success'
    when all green/skipped, or None when unavailable (offline, no checks) —
    callers treat None as unknown, never as red.

    Deliberately reads the HEAD commit's check-runs rather than the latest
    workflow run: `gh run list --limit 1` can return an unrelated green
    workflow (e.g. Release) and mask a red CI on the same commit."""
    result = run_command(
        build_gh_command(
            "api", f"repos/{repo}/commits/{base}/check-runs",
            "--jq", "[.check_runs[] | {status, conclusion}]",
        )
    )
    if result.returncode != 0:
        return None
    try:
        checks = json.loads(result.stdout)
    except json.JSONDecodeError:
        return None
    if not checks:
        return None
    conclusions = {c.get("conclusion") for c in checks if c.get("status") == "completed"}
    if any(c.get("status") != "completed" for c in checks):
        return "in_progress" if "failure" not in conclusions else "failure"
    if "failure" in conclusions or "timed_out" in conclusions:
        return "failure"
    return "success"


def cmd_preflight(args: argparse.Namespace) -> int:
    repo_root = Path(args.repo_root).resolve()
    branch = git_stdout(repo_root, ["branch", "--show-current"])
    status = git_stdout(repo_root, ["status", "--porcelain"])
    dirty_paths = [line for line in (status or "").splitlines() if line.strip()]
    ahead_text = git_stdout(repo_root, ["rev-list", "--count", f"origin/{args.base}..HEAD"])
    ahead_count = int(ahead_text) if ahead_text and ahead_text.isdigit() else None
    task_branch, task_base_branch, task_path, task_error = load_active_task(repo_root)
    finalized_task = None
    if not task_branch and task_path is None:
        finalized_task = load_finalized_task_evidence(
            repo_root,
            branch=branch,
            expected_base=args.base,
        )

    errors = evaluate_preflight(
        branch=branch,
        dirty_paths=dirty_paths,
        ahead_count=ahead_count,
        task_branch=task_branch,
        task_base_branch=task_base_branch,
        expected_base=args.base,
        task_present=task_path is not None,
        finalized_task=finalized_task,
    )
    if task_error and not finalized_task:
        errors.append(f"活动任务查询失败：{task_error}")

    # Mechanical merge-review evidence: whitespace/conflict-marker scan and
    # planning-gate validation. These replace the agent merge-review's
    # mechanical checklist items; the agent gate remains only for cross-repo
    # contract changes (see workflow.md Phase 3.1).
    diff_check = run_git(
        ["diff", "--check", f"origin/{args.base}...HEAD"], repo_root
    )
    if diff_check.returncode != 0:
        sample = [ln for ln in diff_check.stdout.splitlines() if ln.strip()][:5]
        errors.append("git diff --check 未通过：" + "；".join(sample))
    if task_path is not None and task_error is None:
        validate = run_command(
            [
                "python3", ".trellis/scripts/task.py", "validate",
                str(task_path.relative_to(repo_root)),
            ],
            cwd=repo_root,
        )
        if validate.returncode != 0:
            detail = (validate.stderr.strip() or validate.stdout.strip()).splitlines()
            errors.append("task.py validate 未通过：" + " / ".join(detail[-3:]))

    # Base-health gate (fail-open): do not stack a new PR onto a red main.
    # A definitive failure conclusion on main's latest run blocks; network
    # errors or in-progress runs only warn — offline preflight keeps working.
    if not args.skip_main_check:
        health = fetch_base_branch_health(args.repo, args.base)
        if health == "failure":
            errors.append(
                f"origin/{args.base} 最新 CI run 结论为 failure —— 先修 {args.base} 再叠新 PR"
                "（确需继续可加 --skip-main-check）"
            )
        elif health not in {"success", None}:
            print(f"note: origin/{args.base} latest CI run state is '{health}' (not blocking)")

    if errors:
        print("ship preflight failed:", file=sys.stderr)
        for error in errors:
            print(f"- {error}", file=sys.stderr)
        return 1

    print("ship preflight passed")
    print(f"- branch: {branch}")
    print(f"- base: {args.base}")
    print(f"- ahead commits: {ahead_count}")
    if task_path:
        print(f"- task: {task_path.relative_to(repo_root)}")
    elif finalized_task:
        print(f"- finalized task: {finalized_task.task_path.relative_to(repo_root)}")
    return 0


def fetch_ci_report(repo: str, number: str) -> CiReport:
    result = run_command(
        build_gh_command(
            "pr",
            "view",
            number,
            "--repo",
            repo,
            "--json",
            "statusCheckRollup",
        )
    )
    output = result.stdout + result.stderr
    if result.returncode != 0:
        return CiReport(state="error", statuses=[], output=output)
    try:
        rollup = json.loads(result.stdout).get("statusCheckRollup") or []
    except json.JSONDecodeError:
        return CiReport(state="error", statuses=[], output=output)
    return CiReport(
        state=aggregate_ci_state(rollup),
        statuses=parse_ci_statuses(rollup),
        output=output,
    )


def fetch_ci_state(repo: str, number: str) -> tuple[str | None, str]:
    report = fetch_ci_report(repo, number)
    return report.state, report.output


def cmd_wait_ci(args: argparse.Namespace) -> int:
    deadline = time.monotonic() + args.timeout
    error_streak = 0
    last_state = None
    last_report = CiReport(state=None, statuses=[], output="")
    pull_info, _ = get_pull(args.repo, args.number)
    head_sha = pull_info.head_sha if pull_info else None

    while True:
        report = fetch_ci_report(args.repo, args.number)
        last_state = report.state
        last_report = report
        head_suffix = f" (head: {head_sha})" if head_sha else ""
        print(f"CI state: {report.state or 'unknown'}{head_suffix}")
        if report.statuses:
            print(format_ci_blockers(report.statuses))

        if report.state == "success":
            error_streak = 0
            return 0
        if report.state == "error" and error_streak < 1:
            # GitHub's status rollup transiently reports "error" while checks
            # are still spinning up/transitioning; require two consecutive
            # error polls before treating it as terminal.
            error_streak += 1
            print("CI state 'error' may be a transient rollup blip; confirming on next poll...")
            if time.monotonic() < deadline:
                time.sleep(args.interval)
                continue
        if report.state in {"failure", "error"}:
            if report.statuses:
                print(format_ci_blockers(report.statuses), file=sys.stderr)
            print(report.output, file=sys.stderr)
            print(
                "查看各 check 明细可用："
                + " ".join(build_ci_checks_command(args.number, args.repo)),
                file=sys.stderr,
            )
            print(
                "读取失败日志可用：gh run view <run-id> --log-failed（run-id 见失败 check 的 detailsUrl）",
                file=sys.stderr,
            )
            return 1
        if report.state not in {"error"}:
            error_streak = 0
        if time.monotonic() >= deadline:
            print(
                f"CI wait timed out after {args.timeout}s; last state: {last_state}",
                file=sys.stderr,
            )
            if last_report.statuses:
                print(format_ci_blockers(last_report.statuses), file=sys.stderr)
            if last_report.output:
                print(last_report.output, file=sys.stderr)
            return 2
        time.sleep(args.interval)


def get_pull(repo: str, number: str) -> tuple[PullInfo | None, str]:
    result = run_command(
        build_gh_command(
            "pr",
            "view",
            number,
            "--repo",
            repo,
            "--json",
            "number,state,title,baseRefName,headRefName,headRefOid,isDraft,mergeable,mergeStateStatus",
        )
    )
    output = result.stdout + result.stderr
    if result.returncode != 0:
        return None, output
    return parse_pull_info(result.stdout), output


def cmd_merge(args: argparse.Namespace) -> int:
    repo_root = Path(args.repo_root).resolve()

    info, raw = get_pull(args.repo, args.number)
    if info is None:
        print("无法读取 PR 状态：", file=sys.stderr)
        print(raw, file=sys.stderr)
        return 1

    # Up-to-date guard: with branch protection enforced for admins, a PR left
    # behind by newer main commits must absorb them (and re-run CI on the real
    # combination) before merge. Without this, parallel PRs that are each green
    # against an older main can break main after the squash.
    if info.merge_state_status == "BEHIND":
        print("PR is behind base; updating branch to retest the real combination...")
        update = run_command(build_gh_command("pr", "update-branch", args.number, "--repo", args.repo))
        sys.stdout.write(update.stdout)
        if update.returncode != 0:
            sys.stderr.write(update.stderr)
            print("ship merge blocked: update-branch failed; resolve conflicts manually", file=sys.stderr)
            return 1
        wait_args = argparse.Namespace(
            repo=args.repo, number=args.number, timeout=900.0, interval=20.0, repo_root=args.repo_root
        )
        if cmd_wait_ci(wait_args) != 0:
            print("ship merge blocked: CI failed after update-branch", file=sys.stderr)
            return 1
        info, raw = get_pull(args.repo, args.number)
        if info is None:
            print("无法读取 PR 状态：", file=sys.stderr)
            print(raw, file=sys.stderr)
            return 1

    errors = validate_pull_ready(info, expected_base=args.base)
    errors.extend(validate_local_merge_ready(repo_root))
    if errors:
        print("ship merge blocked:", file=sys.stderr)
        for error in errors:
            print(f"- {error}", file=sys.stderr)
        return 1

    command = build_merge_command(args.repo, args.number, delete_branch=args.cleanup)
    result = run_command(command, cwd=repo_root)
    sys.stdout.write(result.stdout)
    sys.stderr.write(result.stderr)
    if result.returncode != 0:
        return result.returncode

    print(f"merged PR #{args.number} via squash")
    if args.cleanup:
        return post_merge_cleanup(repo_root, info, args)
    return 0


def post_merge_cleanup(repo_root: Path, info: PullInfo, args: argparse.Namespace) -> int:
    """Post-merge local sync: switch to base, ff-pull, drop the merged task
    branch, prune remotes.

    Squash merges always look unmerged to `git branch -d`, so the safety
    check is oid-based instead: the local branch is force-deleted only when
    the merged PR head oid still equals the local tip (gh --delete-branch
    may have already removed it; both cases are fine).
    """
    branch = info.head_ref
    merged_info, raw = get_pull(args.repo, args.number)
    if merged_info is None or merged_info.state != "MERGED":
        print("cleanup skipped: PR state is not MERGED after merge call", file=sys.stderr)
        print(raw, file=sys.stderr)
        return 1

    current = git_stdout(repo_root, ["branch", "--show-current"])
    if current != args.base:
        result = run_git(["switch", args.base], repo_root)
        if result.returncode != 0:
            sys.stderr.write(result.stderr)
            print(f"cleanup blocked: cannot switch to {args.base}", file=sys.stderr)
            return 1
    result = run_git(["pull", "--ff-only"], repo_root)
    sys.stdout.write(result.stdout)
    if result.returncode != 0:
        sys.stderr.write(result.stderr)
        print("cleanup: ff-only pull failed; resolve manually", file=sys.stderr)
        return 1

    if branch and git_stdout(repo_root, ["rev-parse", "--verify", "--quiet", branch]):
        local_sha = git_stdout(repo_root, ["rev-parse", branch])
        if merged_info.head_sha and local_sha == merged_info.head_sha:
            run_git(["branch", "-D", branch], repo_root)
            print(f"cleanup: deleted local branch {branch}")
        else:
            print(
                f"cleanup: kept local branch {branch} (tip != merged PR head; delete manually)",
                file=sys.stderr,
            )
    run_git(["fetch", "--prune", "origin"], repo_root)
    print(f"cleanup done: on {args.base}, remotes pruned")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="GitHub Trellis ship helper")
    parser.add_argument("--repo-root", default=".", help="Main repository root")
    subparsers = parser.add_subparsers(dest="command", required=True)

    preflight = subparsers.add_parser("preflight", help="Run local ship preflight checks")
    preflight.add_argument("--base", default=DEFAULT_BASE, help="Expected base branch")
    preflight.add_argument("--repo", default=DEFAULT_REPO, help="GitHub repo (owner/name)")
    preflight.add_argument(
        "--skip-main-check",
        action="store_true",
        help="Skip the base-branch CI health gate (use when intentionally shipping onto a known-red base)",
    )
    preflight.set_defaults(func=cmd_preflight)

    wait_ci = subparsers.add_parser("wait-ci", help="Wait for GitHub PR CI status")
    wait_ci.add_argument("--repo", default=DEFAULT_REPO, help="GitHub repo (owner/name)")
    wait_ci.add_argument("--number", required=True, help="PR number")
    wait_ci.add_argument("--timeout", type=float, default=900.0, help="Seconds before giving up")
    wait_ci.add_argument("--interval", type=float, default=20.0, help="Poll interval seconds")
    wait_ci.set_defaults(func=cmd_wait_ci)

    merge = subparsers.add_parser("merge", help="Squash-merge a ready PR (guarded)")
    merge.add_argument("--repo", default=DEFAULT_REPO, help="GitHub repo (owner/name)")
    merge.add_argument(
        "--cleanup",
        action="store_true",
        help="After merge: delete remote branch, switch to base, ff-pull, drop local branch, prune",
    )
    merge.add_argument("--number", required=True, help="PR number")
    merge.add_argument("--base", default=DEFAULT_BASE, help="Expected base branch")
    merge.set_defaults(func=cmd_merge)

    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
