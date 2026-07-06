#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Task Management Script.

Usage:
    python3 task.py create "<title>" [--slug <name>] [--assignee <dev>] [--priority P0|P1|P2|P3] [--parent <dir>] [--package <pkg>]
    python3 task.py add-context <dir> <file> <path> [reason] # Add jsonl entry
    python3 task.py validate <dir>              # Validate task context + planning gate
    python3 task.py list-context <dir>          # List jsonl entries
    python3 task.py start <dir>                 # Set active task
    python3 task.py switch <dir>                # Set active task pointer only (no status change)
    python3 task.py guard [--strict]           # Warn if git branch != active task's branch
    python3 task.py current [--source]          # Show active task
    python3 task.py finish                      # Clear active task
    python3 task.py set-branch <dir> <branch>   # Set git branch
    python3 task.py set-base-branch <dir> <branch>  # Set PR target branch
    python3 task.py set-scope <dir> <scope>     # Set scope for PR title
    python3 task.py set-strategy <dir> [options] # Set development strategy
    python3 task.py archive <task-dir>          # Archive completed task
    python3 task.py list                        # List active tasks
    python3 task.py list-archive [month]        # List archived tasks
    python3 task.py add-subtask <parent-dir> <child-dir>     # Link child to parent
    python3 task.py remove-subtask <parent-dir> <child-dir>  # Unlink child from parent
"""

from __future__ import annotations

import argparse
import sys

from common.log import Colors, colored
from common.paths import (
    DIR_WORKFLOW,
    DIR_TASKS,
    FILE_TASK_JSON,
    get_repo_root,
    get_developer,
    get_tasks_dir,
    get_current_task,
)
from common.active_task import (
    clear_active_task,
    resolve_active_task,
    resolve_context_key,
    set_active_task,
)
from common.io import read_json, write_json
from common.planning_gate import evaluate_planning_gate, format_planning_gate_result
from common.git import run_git
from common.task_utils import resolve_task_dir, run_task_hooks
from common.tasks import iter_active_tasks, children_progress

# Import command handlers from split modules (also re-exports for plan.py compatibility)
from common.task_store import (
    cmd_create,
    cmd_archive,
    cmd_set_branch,
    cmd_set_base_branch,
    cmd_set_scope,
    cmd_set_strategy,
    cmd_set_deep_review,
    cmd_add_subtask,
    cmd_remove_subtask,
)
from common.task_context import (
    cmd_add_context,
    cmd_validate,
    cmd_list_context,
)


# =============================================================================
# Command: start / finish
# =============================================================================

def _current_git_branch(repo_root) -> str | None:
    """Return the current git branch name, or None when unavailable.

    Uses `symbolic-ref` so a detached HEAD (no branch) returns None rather
    than a commit hash. run_git swallows the "no git" case (rc != 0), so this
    is safe to call in environments without git.
    """
    rc, out, _ = run_git(["symbolic-ref", "--quiet", "--short", "HEAD"], cwd=repo_root)
    if rc != 0:
        return None
    branch = out.strip()
    return branch or None


def _record_task_branch(task_json_path, repo_root) -> str | None:
    """Stamp the current git branch into task.json's `branch` field.

    M7 prerequisite: `task.py guard` compares this field with the live git
    branch, so `start` is where the task↔branch binding is captured. Only
    writes when on a real branch; never overwrites with an empty value.
    Returns the branch it recorded, or None when nothing was written.
    """
    branch = _current_git_branch(repo_root)
    if not branch:
        return None
    if not task_json_path.is_file():
        return None
    data = read_json(task_json_path)
    if not data:
        return None
    if data.get("branch") == branch:
        return branch
    data["branch"] = branch
    if write_json(task_json_path, data):
        return branch
    return None


def cmd_start(args: argparse.Namespace) -> int:
    """Set active task."""
    repo_root = get_repo_root()
    task_input = args.dir

    if not task_input:
        print(colored("Error: task directory or name required", Colors.RED))
        return 1

    # Resolve task directory (supports task name, relative path, or absolute path)
    full_path = resolve_task_dir(task_input, repo_root)

    if not full_path.is_dir():
        print(colored(f"Error: Task not found: {task_input}", Colors.RED))
        print("Hint: Use task name (e.g., 'my-task') or full path (e.g., '.trellis/tasks/01-31-my-task')")
        return 1

    # Convert to relative path for storage
    try:
        task_dir = full_path.relative_to(repo_root).as_posix()
    except ValueError:
        task_dir = str(full_path)

    task_json_path = full_path / FILE_TASK_JSON

    if task_json_path.is_file():
        data = read_json(task_json_path)
        if data and data.get("status") == "planning":
            gate_result = evaluate_planning_gate(full_path, repo_root)
            if not gate_result.ok:
                print(colored(format_planning_gate_result(gate_result), Colors.RED))
                print(
                    "请补齐规划产物后重试；任务状态保持 planning。",
                    file=sys.stderr,
                )
                return 1

    if not resolve_context_key():
        # Degraded mode: no session identity available.
        # Hook didn't inject TRELLIS_CONTEXT_ID (common on Windows + Claude Code,
        # --continue resume path, fork distribution, hooks disabled, etc.). Skip
        # per-session pointer write; AI continues based on conversation context.
        print(colored(
            "ℹ Session identity not available; active-task pointer not persisted "
            "this session (degraded mode). AI continues based on conversation context.",
            Colors.YELLOW,
        ))
        print(colored(
            "Hint: run inside an AI IDE/session that exposes session identity, "
            "or set TRELLIS_CONTEXT_ID before running task.py start.",
            Colors.YELLOW,
        ))

        # Still flip task.json status: planning → in_progress so downstream phases proceed.
        if task_json_path.is_file():
            data = read_json(task_json_path)
            if data and data.get("status") == "planning":
                data["status"] = "in_progress"
                if write_json(task_json_path, data):
                    print(colored("✓ Status: planning → in_progress (degraded)", Colors.GREEN))
            # M7: bind task to the branch it's started on (guard reads this).
            recorded = _record_task_branch(task_json_path, repo_root)
            if recorded:
                print(colored(f"✓ Branch recorded: {recorded}", Colors.GREEN))
            run_task_hooks("after_start", task_json_path, repo_root)
        return 0

    active = set_active_task(task_dir, repo_root)
    if active:
        print(colored(f"✓ Current task set to: {task_dir}", Colors.GREEN))
        print(f"Source: {active.source}")

        if task_json_path.is_file():
            data = read_json(task_json_path)
            if data and data.get("status") == "planning":
                data["status"] = "in_progress"
                if write_json(task_json_path, data):
                    print(colored("✓ Status: planning → in_progress", Colors.GREEN))
            # M7: bind task to the branch it's started on (guard reads this).
            recorded = _record_task_branch(task_json_path, repo_root)
            if recorded:
                print(colored(f"✓ Branch recorded: {recorded}", Colors.GREEN))

        print()
        print(colored("The hook will now inject context from this task's jsonl files.", Colors.BLUE))

        run_task_hooks("after_start", task_json_path, repo_root)
        return 0
    else:
        print(colored("Error: Failed to set current task", Colors.RED))
        return 1


def cmd_finish(args: argparse.Namespace) -> int:
    """Clear active task."""
    repo_root = get_repo_root()
    active = clear_active_task(repo_root)
    current = active.task_path

    if not current:
        print(colored("No current task set", Colors.YELLOW))
        return 0

    # Resolve task.json path before clearing
    task_json_path = repo_root / current / FILE_TASK_JSON

    print(colored(f"✓ Cleared current task (was: {current})", Colors.GREEN))
    print(f"Source: {active.source}")

    if task_json_path.is_file():
        run_task_hooks("after_finish", task_json_path, repo_root)
    return 0


def cmd_switch(args: argparse.Namespace) -> int:
    """Set the active-task pointer without touching task.json status.

    M2: `start` is the only command that moves the session pointer, but it
    also flips status planning → in_progress. There was no clean way to fix
    the pointer during the "planning done, waiting for start" gap, or to
    recover after archiving the active task left a stale fallback pointing
    at the wrong task. `switch` is pointer-only — status is never changed.
    """
    repo_root = get_repo_root()
    task_input = args.dir

    if not task_input:
        print(colored("Error: task directory or name required", Colors.RED))
        return 1

    full_path = resolve_task_dir(task_input, repo_root)

    if not full_path.is_dir():
        print(colored(f"Error: Task not found: {task_input}", Colors.RED))
        print("Hint: Use task name (e.g., 'my-task') or full path (e.g., '.trellis/tasks/01-31-my-task')")
        return 1

    try:
        task_dir = full_path.relative_to(repo_root).as_posix()
    except ValueError:
        task_dir = str(full_path)

    if not resolve_context_key():
        # No session identity: pointer is session-scoped, so there is nothing
        # to write. Unlike `start`, `switch` has no status side effect, so
        # degraded mode is a clean no-op (report it, exit 0).
        print(colored(
            "ℹ Session identity not available; active-task pointer not persisted "
            "this session (degraded mode). switch is a no-op here.",
            Colors.YELLOW,
        ))
        print(colored(
            "Hint: run inside an AI IDE/session that exposes session identity, "
            "or set TRELLIS_CONTEXT_ID before running task.py switch.",
            Colors.YELLOW,
        ))
        return 0

    active = set_active_task(task_dir, repo_root)
    if active:
        print(colored(f"✓ Current task set to: {task_dir}", Colors.GREEN))
        print(f"Source: {active.source}")
        print(colored("(status unchanged — use task.py start to flip planning → in_progress)", Colors.BLUE))
        return 0

    print(colored("Error: Failed to set current task", Colors.RED))
    return 1


def cmd_guard(args: argparse.Namespace) -> int:
    """Warn when the git branch diverges from the active task's branch.

    M7: pre-commit already blocks shared baselines, but nothing checked that
    the working branch matches the task you think you're on. `guard` compares
    the active task's task.json `branch` (stamped by `start`) against the live
    git branch.

    Three states:
      - match / no active task / empty branch field / no git: silent exit 0
      - mismatch (default): one-line Chinese warning, exit 0 (soft)
      - mismatch with --strict: same warning, exit 1

    Designed for zero dependency on colleagues' setups: any missing piece
    (no runtime pointer, no branch field, no git) degrades to a silent exit 0
    so wiring this into a shared pre-commit hook never breaks anyone.
    """
    repo_root = get_repo_root()

    # No active task → nothing to guard. Silent success.
    active = resolve_active_task(repo_root)
    if not active.task_path:
        return 0

    task_dir = repo_root / active.task_path
    task_json_path = task_dir / FILE_TASK_JSON
    if not task_json_path.is_file():
        return 0

    data = read_json(task_json_path)
    if not data:
        return 0

    task_branch = data.get("branch")
    if not isinstance(task_branch, str) or not task_branch.strip():
        # Field empty/missing (e.g. task started before M7, or detached HEAD
        # at start time). Guard has no expectation to enforce → silent 0.
        return 0
    task_branch = task_branch.strip()

    git_branch = _current_git_branch(repo_root)
    if not git_branch:
        # No git / detached HEAD → cannot compare. Silent 0 (zero-dependency).
        return 0

    if git_branch == task_branch:
        return 0

    task_name = data.get("name") or task_dir.name
    print(colored(
        f"⚠ 分支与活动任务不一致：当前 git 分支 '{git_branch}'，"
        f"任务 '{task_name}' 记录的分支为 '{task_branch}'。",
        Colors.YELLOW,
    ))
    return 1 if getattr(args, "strict", False) else 0


def cmd_current(args: argparse.Namespace) -> int:
    """Show active task."""
    repo_root = get_repo_root()
    active = resolve_active_task(repo_root)

    if args.source:
        print(f"Current task: {active.task_path or '(none)'}")
        print(f"Source: {active.source}")
        if active.stale:
            print("State: stale")
        return 0 if active.task_path else 1

    if active.task_path:
        print(active.task_path)
        return 0

    return 1


# =============================================================================
# Command: list
# =============================================================================

def cmd_list(args: argparse.Namespace) -> int:
    """List active tasks."""
    repo_root = get_repo_root()
    tasks_dir = get_tasks_dir(repo_root)
    current_task = get_current_task(repo_root)
    developer = get_developer(repo_root)
    filter_mine = args.mine
    filter_status = args.status

    if filter_mine:
        if not developer:
            print(colored("Error: No developer set. Run init_developer.py first", Colors.RED), file=sys.stderr)
            return 1
        print(colored(f"My tasks (assignee: {developer}):", Colors.BLUE))
    else:
        print(colored("All active tasks:", Colors.BLUE))
    print()

    # Single pass: collect all tasks via shared iterator
    all_tasks = {t.dir_name: t for t in iter_active_tasks(tasks_dir)}
    all_statuses = {name: t.status for name, t in all_tasks.items()}

    # Display tasks hierarchically
    count = 0

    def _print_task(dir_name: str, indent: int = 0) -> None:
        nonlocal count
        t = all_tasks[dir_name]

        # Apply --mine filter
        if filter_mine and (t.assignee or "-") != developer:
            return

        # Apply --status filter
        if filter_status and t.status != filter_status:
            return

        relative_path = f"{DIR_WORKFLOW}/{DIR_TASKS}/{dir_name}"
        marker = ""
        if relative_path == current_task:
            marker = f" {colored('<- current', Colors.GREEN)}"

        # Children progress
        progress = children_progress(t.children, all_statuses)

        # Package tag
        pkg_tag = f" @{t.package}" if t.package else ""

        prefix = "  " * indent + "  - "

        if filter_mine:
            print(f"{prefix}{dir_name}/ ({t.status}){pkg_tag}{progress}{marker}")
        else:
            print(f"{prefix}{dir_name}/ ({t.status}){pkg_tag}{progress} [{colored(t.assignee or '-', Colors.CYAN)}]{marker}")
        count += 1

        # Print children indented
        for child_name in t.children:
            if child_name in all_tasks:
                _print_task(child_name, indent + 1)

    # Display only top-level tasks (those without a parent)
    for dir_name in sorted(all_tasks.keys()):
        if not all_tasks[dir_name].parent:
            _print_task(dir_name)

    if count == 0:
        if filter_mine:
            print("  (no tasks assigned to you)")
        else:
            print("  (no active tasks)")

    print()
    print(f"Total: {count} task(s)")
    return 0


# =============================================================================
# Command: list-archive
# =============================================================================

def cmd_list_archive(args: argparse.Namespace) -> int:
    """List archived tasks."""
    repo_root = get_repo_root()
    tasks_dir = get_tasks_dir(repo_root)
    archive_dir = tasks_dir / "archive"
    month = args.month

    print(colored("Archived tasks:", Colors.BLUE))
    print()

    if month:
        month_dir = archive_dir / month
        if month_dir.is_dir():
            print(f"[{month}]")
            for d in sorted(month_dir.iterdir()):
                if d.is_dir():
                    print(f"  - {d.name}/")
        else:
            print(f"  No archives for {month}")
    else:
        if archive_dir.is_dir():
            for month_dir in sorted(archive_dir.iterdir()):
                if month_dir.is_dir():
                    month_name = month_dir.name
                    count = sum(1 for d in month_dir.iterdir() if d.is_dir())
                    print(f"[{month_name}] - {count} task(s)")

    return 0


# =============================================================================
# Help
# =============================================================================

def show_usage() -> None:
    """Show usage help."""
    print("""Task Management Script

Usage:
  python3 task.py create <title>                     Create new task directory
  python3 task.py create <title> --package <pkg>     Create task for a specific package
  python3 task.py create <title> --parent <dir>      Create task as child of parent
  python3 task.py add-context <dir> <jsonl> <path> [reason]  Add entry to jsonl
  python3 task.py validate <dir>                     Validate task context + planning gate
  python3 task.py list-context <dir>                 List jsonl entries
  python3 task.py start <dir>                        Set active task
  python3 task.py switch <dir>                       Set active task pointer only (no status change)
  python3 task.py guard [--strict]                   Warn if git branch != active task's branch
  python3 task.py current [--source]                 Show active task
  python3 task.py finish                             Clear active task
  python3 task.py set-branch <dir> <branch>          Set git branch
  python3 task.py set-base-branch <dir> <branch>     Set PR target branch
  python3 task.py set-scope <dir> <scope>            Set scope for PR title
  python3 task.py set-strategy <dir> [options]       Set development strategy
  python3 task.py set-deep-review <dir> <state>      Set deep-review ledger (pending|done|waived)
  python3 task.py archive <task-dir>                 Archive completed task
  python3 task.py add-subtask <parent> <child>       Link child task to parent
  python3 task.py remove-subtask <parent> <child>    Unlink child from parent
  python3 task.py list [--mine] [--status <status>]  List tasks
  python3 task.py list-archive [YYYY-MM]             List archived tasks

Monorepo options:
  --package <pkg>      Package name (validated against config.yaml packages)

List options:
  --mine, -m           Show only tasks assigned to current developer
  --status, -s <s>     Filter by status (planning, in_progress, review, completed)

Examples:
  python3 task.py create "Add login feature" --slug add-login
  python3 task.py create "Add login feature" --slug add-login --package cli
  python3 task.py create "Child task" --slug child --parent .trellis/tasks/01-21-parent
  python3 task.py add-context <dir> implement .trellis/spec/cli/backend/auth.md "Auth guidelines"
  python3 task.py set-branch <dir> task/add-login
  python3 task.py set-strategy <dir> --execution current-session --git-mode branch --development-mode default --spec-review disabled --code-review enabled --architecture-review disabled --merge-review enabled
  python3 task.py start .trellis/tasks/01-21-add-login
  python3 task.py switch .trellis/tasks/01-21-add-login  # Move pointer without flipping status
  python3 task.py guard                              # Warn if on the wrong branch
  python3 task.py guard --strict                     # Exit 1 on branch mismatch
  python3 task.py current --source
  python3 task.py finish
  python3 task.py archive add-login
  python3 task.py add-subtask parent-task child-task  # Link existing tasks
  python3 task.py remove-subtask parent-task child-task
  python3 task.py list                               # List all active tasks
  python3 task.py list --mine                        # List my tasks only
  python3 task.py list --mine --status in_progress   # List my in-progress tasks
""")


# =============================================================================
# Main Entry
# =============================================================================

def main() -> int:
    """CLI entry point."""
    # Deprecation guard: `init-context` was removed in v0.5.0-beta.12.
    # Detect early so argparse doesn't mask the real reason with a generic
    # "invalid choice" error.
    if len(sys.argv) >= 2 and sys.argv[1] == "init-context":
        print(
            colored(
                "Error: `task.py init-context` was removed in v0.5.0-beta.12.",
                Colors.RED,
            ),
            file=sys.stderr,
        )
        print(
            "implement.jsonl / check.jsonl are now seeded on `task.py create` for",
            file=sys.stderr,
        )
        print(
            "sub-agent-capable platforms and curated by the AI during planning when needed.",
            file=sys.stderr,
        )
        print("See .trellis/workflow.md planning artifact guidance or run:", file=sys.stderr)
        print(
            "  python3 ./.trellis/scripts/get_context.py --mode phase --step 1",
            file=sys.stderr,
        )
        print(
            "Use `task.py add-context <dir> implement|check <path> <reason>` to append entries.",
            file=sys.stderr,
        )
        return 2

    parser = argparse.ArgumentParser(
        description="Task Management Script",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    subparsers = parser.add_subparsers(dest="command", help="Commands")

    # create
    p_create = subparsers.add_parser("create", help="Create new task")
    p_create.add_argument("title", help="Task title")
    p_create.add_argument("--slug", "-s", help="Task slug")
    p_create.add_argument("--assignee", "-a", help="Assignee developer")
    p_create.add_argument("--priority", "-p", default="P2", help="Priority (P0-P3)")
    p_create.add_argument("--description", "-d", help="Task description")
    p_create.add_argument("--parent", help="Parent task directory (establishes subtask link)")
    p_create.add_argument("--package", help="Package name for monorepo projects")

    # add-context
    p_add = subparsers.add_parser("add-context", help="Add context entry")
    p_add.add_argument("dir", help="Task directory")
    p_add.add_argument("file", help="JSONL file (implement|check)")
    p_add.add_argument("path", help="File path to add")
    p_add.add_argument("reason", nargs="?", help="Reason for adding")

    # validate
    p_validate = subparsers.add_parser("validate", help="Validate task context + planning gate")
    p_validate.add_argument("dir", help="Task directory")

    # list-context
    p_listctx = subparsers.add_parser("list-context", help="List context entries")
    p_listctx.add_argument("dir", help="Task directory")

    # start
    p_start = subparsers.add_parser("start", help="Set active task")
    p_start.add_argument("dir", help="Task directory")

    # switch
    p_switch = subparsers.add_parser(
        "switch", help="Set active task pointer only (no status change)"
    )
    p_switch.add_argument("dir", help="Task directory")

    # guard
    p_guard = subparsers.add_parser(
        "guard", help="Warn if git branch differs from active task's branch"
    )
    p_guard.add_argument(
        "--strict",
        action="store_true",
        help="Exit 1 on mismatch (default: warn and exit 0)",
    )

    # current
    p_current = subparsers.add_parser("current", help="Show active task")
    p_current.add_argument("--source", action="store_true",
                           help="Show active task source")

    # finish
    subparsers.add_parser("finish", help="Clear active task")

    # set-branch
    p_branch = subparsers.add_parser("set-branch", help="Set git branch")
    p_branch.add_argument("dir", help="Task directory")
    p_branch.add_argument("branch", help="Branch name")

    # set-base-branch
    p_base = subparsers.add_parser("set-base-branch", help="Set PR target branch")
    p_base.add_argument("dir", help="Task directory")
    p_base.add_argument("base_branch", help="Base branch name (PR target)")

    # set-scope
    p_scope = subparsers.add_parser("set-scope", help="Set scope")
    p_scope.add_argument("dir", help="Task directory")
    p_scope.add_argument("scope", help="Scope name")

    # set-strategy
    p_strategy = subparsers.add_parser("set-strategy", help="Set development strategy")
    p_strategy.add_argument("dir", help="Task directory")
    p_strategy.add_argument("--execution", choices=("current-session", "subagent"))
    p_strategy.add_argument("--git-mode", choices=("branch", "worktree"))
    p_strategy.add_argument("--development-mode", choices=("default", "tdd"))
    p_strategy.add_argument("--spec-review", dest="spec_review", choices=("enabled", "disabled"))
    p_strategy.add_argument("--code-review", dest="code_review", choices=("enabled", "disabled"))
    p_strategy.add_argument("--architecture-review", dest="architecture_review", choices=("enabled", "disabled"))
    p_strategy.add_argument("--merge-review", dest="merge_review", choices=("enabled", "disabled"))
    p_strategy.add_argument("--grill-me", dest="grill_me", choices=("enabled", "disabled"))

    # set-deep-review
    p_deep = subparsers.add_parser(
        "set-deep-review", help="Set deep-review ledger state"
    )
    p_deep.add_argument("dir", help="Task directory (active or archived)")
    p_deep.add_argument("state", choices=("pending", "done", "waived"),
                        help="done is stamped as done@YYYY-MM-DD")

    # archive
    p_archive = subparsers.add_parser("archive", help="Archive task")
    p_archive.add_argument("name", help="Task directory or name")
    p_archive.add_argument("--no-commit", action="store_true", help="Skip auto git commit after archive")

    # list
    p_list = subparsers.add_parser("list", help="List tasks")
    p_list.add_argument("--mine", "-m", action="store_true", help="My tasks only")
    p_list.add_argument("--status", "-s", help="Filter by status")

    # add-subtask
    p_addsub = subparsers.add_parser("add-subtask", help="Link child task to parent")
    p_addsub.add_argument("parent_dir", help="Parent task directory")
    p_addsub.add_argument("child_dir", help="Child task directory")

    # remove-subtask
    p_rmsub = subparsers.add_parser("remove-subtask", help="Unlink child task from parent")
    p_rmsub.add_argument("parent_dir", help="Parent task directory")
    p_rmsub.add_argument("child_dir", help="Child task directory")

    # list-archive
    p_listarch = subparsers.add_parser("list-archive", help="List archived tasks")
    p_listarch.add_argument("month", nargs="?", help="Month (YYYY-MM)")

    args = parser.parse_args()

    if not args.command:
        show_usage()
        return 1

    commands = {
        "create": cmd_create,
        "add-context": cmd_add_context,
        "validate": cmd_validate,
        "list-context": cmd_list_context,
        "start": cmd_start,
        "switch": cmd_switch,
        "guard": cmd_guard,
        "current": cmd_current,
        "finish": cmd_finish,
        "set-branch": cmd_set_branch,
        "set-base-branch": cmd_set_base_branch,
        "set-scope": cmd_set_scope,
        "set-strategy": cmd_set_strategy,
        "set-deep-review": cmd_set_deep_review,
        "archive": cmd_archive,
        "add-subtask": cmd_add_subtask,
        "remove-subtask": cmd_remove_subtask,
        "list": cmd_list,
        "list-archive": cmd_list_archive,
    }

    if args.command in commands:
        return commands[args.command](args)
    else:
        show_usage()
        return 1


if __name__ == "__main__":
    sys.exit(main())
