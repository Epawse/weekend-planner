#!/usr/bin/env python3
"""Read-only Trellis branch/task report for GitHub projects.

The report is advisory. It helps humans decide what to inspect next, but it
does not prove GitHub merge state and never authorizes cleanup by itself.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path


PROTECTED_BRANCHES = {"main", "master"}
ARCHIVED_STATUSES = {"archived", "completed"}


@dataclass(frozen=True)
class GitRefs:
    local: set[str]
    remote: set[str]


@dataclass(frozen=True)
class TaskInfo:
    path: Path
    branch: str
    base_branch: str
    status: str


@dataclass(frozen=True)
class BranchRow:
    branch: str
    local: bool
    remote: bool
    tasks: tuple[TaskInfo, ...]
    cleanup: str


def run_git(args: list[str], repo_root: Path) -> str:
    result = subprocess.run(
        ["git", "-c", "i18n.logOutputEncoding=UTF-8", *args],
        cwd=repo_root,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    if result.returncode != 0:
        message = result.stderr.strip() or result.stdout.strip()
        raise RuntimeError(message or f"git command failed: {' '.join(args)}")
    return result.stdout


def normalize_ref(refname: str) -> tuple[str, str] | None:
    if refname.startswith("refs/heads/"):
        branch = refname.removeprefix("refs/heads/")
        return ("local", branch) if branch else None

    if refname.startswith("refs/remotes/origin/"):
        branch = refname.removeprefix("refs/remotes/origin/")
        if branch == "HEAD" or not branch:
            return None
        return "remote", branch

    return None


def parse_refs(refnames: list[str]) -> GitRefs:
    local: set[str] = set()
    remote: set[str] = set()

    for raw_ref in refnames:
        normalized = normalize_ref(raw_ref.strip())
        if not normalized:
            continue
        kind, branch = normalized
        if kind == "local":
            local.add(branch)
        elif kind == "remote":
            remote.add(branch)

    return GitRefs(local=local, remote=remote)


def discover_refs(repo_root: Path) -> GitRefs:
    output = run_git(
        ["for-each-ref", "--format=%(refname)", "refs/heads", "refs/remotes/origin"],
        repo_root,
    )
    return parse_refs(output.splitlines())


def task_status(path: Path, tasks_root: Path, raw_status: object) -> str:
    try:
        relative_parts = path.relative_to(tasks_root).parts
    except ValueError:
        relative_parts = path.parts

    if "archive" in relative_parts:
        return "archived"
    if isinstance(raw_status, str) and raw_status.strip():
        return raw_status.strip()
    return "-"


def load_tasks(repo_root: Path) -> list[TaskInfo]:
    tasks_root = repo_root / ".trellis" / "tasks"
    if not tasks_root.exists():
        return []

    tasks: list[TaskInfo] = []
    for task_json in sorted(tasks_root.glob("**/task.json")):
        try:
            raw = json.loads(task_json.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue

        branch = raw.get("branch")
        if not isinstance(branch, str) or not branch.strip():
            continue

        base_branch = raw.get("base_branch")
        tasks.append(
            TaskInfo(
                path=task_json.parent.relative_to(repo_root),
                branch=branch.strip(),
                base_branch=base_branch.strip()
                if isinstance(base_branch, str) and base_branch.strip()
                else "-",
                status=task_status(task_json, tasks_root, raw.get("status")),
            )
        )

    return tasks


def classify_cleanup(
    *,
    branch: str,
    local: bool,
    remote: bool,
    tasks: tuple[TaskInfo, ...],
) -> str:
    if branch in PROTECTED_BRANCHES:
        return "protected"

    if tasks and any(task.status not in ARCHIVED_STATUSES for task in tasks):
        return "active-task"

    if local and remote and tasks and all(task.status in ARCHIVED_STATUSES for task in tasks):
        return "candidate"

    return "review"


def build_rows(refs: GitRefs, tasks: list[TaskInfo]) -> list[BranchRow]:
    tasks_by_branch: dict[str, list[TaskInfo]] = {}
    for task in tasks:
        tasks_by_branch.setdefault(task.branch, []).append(task)

    branch_names = set(refs.local) | set(refs.remote) | set(tasks_by_branch)
    rows: list[BranchRow] = []

    for branch in sorted(branch_names):
        branch_tasks = tuple(sorted(tasks_by_branch.get(branch, []), key=lambda item: str(item.path)))
        local = branch in refs.local
        remote = branch in refs.remote
        rows.append(
            BranchRow(
                branch=branch,
                local=local,
                remote=remote,
                tasks=branch_tasks,
                cleanup=classify_cleanup(
                    branch=branch,
                    local=local,
                    remote=remote,
                    tasks=branch_tasks,
                ),
            )
        )

    return rows


def join_unique(values: list[str]) -> str:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        if value not in seen:
            seen.add(value)
            result.append(value)
    return ", ".join(result) if result else "-"


def task_paths(tasks: tuple[TaskInfo, ...]) -> str:
    if not tasks:
        return "-"
    return "; ".join(str(task.path) for task in tasks)


def render_table(rows: list[BranchRow]) -> str:
    headers = ["branch", "local", "remote", "task_status", "base", "cleanup", "task"]
    table_rows: list[list[str]] = []

    for row in rows:
        table_rows.append(
            [
                row.branch,
                "yes" if row.local else "no",
                "yes" if row.remote else "no",
                join_unique([task.status for task in row.tasks]),
                join_unique([task.base_branch for task in row.tasks]),
                row.cleanup,
                task_paths(row.tasks),
            ]
        )

    widths = [
        max(len(headers[index]), *(len(row[index]) for row in table_rows))
        if table_rows
        else len(headers[index])
        for index in range(len(headers))
    ]

    def format_row(values: list[str]) -> str:
        return "  ".join(value.ljust(widths[index]) for index, value in enumerate(values))

    lines = [format_row(headers), format_row(["-" * width for width in widths])]
    lines.extend(format_row(row) for row in table_rows)
    return "\n".join(lines)


def build_report(repo_root: Path) -> str:
    refs = discover_refs(repo_root)
    tasks = load_tasks(repo_root)
    rows = build_rows(refs, tasks)
    notes = [
        "",
        "cleanup labels are advisory:",
        "- protected: shared baseline or historical shared branch; do not delete.",
        "- active-task: linked Trellis task is still active.",
        "- candidate: linked task is archived/completed and both local+remote refs exist.",
        "- review: inspect manually; branch lacks complete local/remote/task evidence.",
    ]
    return render_table(rows) + "\n" + "\n".join(notes)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Show local/remote branches and linked Trellis task metadata."
    )
    parser.add_argument(
        "--repo-root",
        default=Path(__file__).resolve().parents[1],
        type=Path,
        help="Repository root. Defaults to the parent of scripts/.",
    )
    args = parser.parse_args(argv)

    try:
        print(build_report(args.repo_root.resolve()))
    except RuntimeError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
