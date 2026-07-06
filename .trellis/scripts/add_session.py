#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Record a session as a one-line entry in the workspace index.md.

Journal files (journal-N.md) are retired (2026-07-05): their content
duplicated git log / PR descriptions / task archives, and the template
flow produced placeholder text. Existing journal files are kept on disk
as read-only history and listed as Archived in index.md. This script now
writes ONLY the index.md session history row (# / Date / Title / Commits
/ Branch) plus the current-status counters.

Usage:
    python3 add_session.py --title "Title" --commit "hash" [--package cli]
    python3 add_session.py --title "Title" --branch "feat/my-branch"

--summary is still accepted for call-site compatibility but is not
persisted — durable summaries belong in PR descriptions and task archives.

Branch resolution order:
    1. --branch CLI arg (explicit)
    2. task.json branch field (from active task)
    3. git branch --show-current (auto-detect)
    4. None (omitted gracefully)
"""

from __future__ import annotations

import argparse
import re
import sys
from datetime import datetime
from pathlib import Path

from common.paths import (
    DIR_TASKS,
    DIR_WORKFLOW,
    FILE_JOURNAL_PREFIX,
    get_repo_root,
    get_current_task,
    get_developer,
    get_workspace_dir,
)
from common.developer import ensure_developer
from common.git import run_git
from common.safe_commit import (
    print_gitignore_warning,
    safe_git_add,
    safe_trellis_paths_to_add,
)
from common.tasks import load_task
from common.config import (
    get_session_auto_commit,
    get_session_commit_message,
)


# =============================================================================
# Helper Functions
# =============================================================================

def get_current_session(index_file: Path) -> int:
    """Get current session number from index.md."""
    if not index_file.is_file():
        return 0

    content = index_file.read_text(encoding="utf-8")
    for line in content.splitlines():
        if "Total Sessions" in line:
            match = re.search(r":\s*(\d+)", line)
            if match:
                return int(match.group(1))
    return 0


def _extract_journal_num(filename: str) -> int:
    """Extract journal number from filename for sorting."""
    match = re.search(r"(\d+)", filename)
    return int(match.group(1)) if match else 0


def count_journal_files(dev_dir: Path) -> str:
    """List legacy journal files (all Archived since journal retirement)."""
    result_lines = []

    files = sorted(
        [f for f in dev_dir.glob(f"{FILE_JOURNAL_PREFIX}*.md") if f.is_file()],
        key=lambda f: _extract_journal_num(f.stem),
        reverse=True
    )

    for f in files:
        lines = len(f.read_text(encoding="utf-8").splitlines())
        result_lines.append(f"| `{f.name}` | ~{lines} | Archived |")

    return "\n".join(result_lines)


def update_index(
    index_file: Path,
    dev_dir: Path,
    title: str,
    commit: str,
    new_session: int,
    today: str,
    branch: str | None = None,
) -> bool:
    """Update index.md with new session info."""
    # Format commit for display
    commit_display = "-"
    if commit and commit != "-":
        commit_display = re.sub(r"([a-f0-9]{7,})", r"`\1`", commit.replace(",", ", "))

    files_table = count_journal_files(dev_dir)

    print(f"Updating index.md for session {new_session}...")
    print(f"  Title: {title}")
    print(f"  Commit: {commit_display}")
    print()

    content = index_file.read_text(encoding="utf-8")

    if "@@@auto:current-status" not in content:
        print("Error: Markers not found in index.md. Please ensure markers exist.", file=sys.stderr)
        return False

    # Process sections
    lines = content.splitlines()
    new_lines = []

    in_current_status = False
    in_active_documents = False
    in_session_history = False
    header_written = False

    for line in lines:
        if "@@@auto:current-status" in line:
            new_lines.append(line)
            in_current_status = True
            new_lines.append("- **Active File**: - (journal retired 2026-07-05)")
            new_lines.append(f"- **Total Sessions**: {new_session}")
            new_lines.append(f"- **Last Active**: {today}")
            continue

        if "@@@/auto:current-status" in line:
            in_current_status = False
            new_lines.append(line)
            continue

        if "@@@auto:active-documents" in line:
            new_lines.append(line)
            in_active_documents = True
            new_lines.append("| File | Lines | Status |")
            new_lines.append("|------|-------|--------|")
            new_lines.append(files_table)
            continue

        if "@@@/auto:active-documents" in line:
            in_active_documents = False
            new_lines.append(line)
            continue

        if "@@@auto:session-history" in line:
            new_lines.append(line)
            in_session_history = True
            header_written = False
            continue

        if "@@@/auto:session-history" in line:
            in_session_history = False
            new_lines.append(line)
            continue

        if in_current_status:
            continue

        if in_active_documents:
            continue

        if in_session_history:
            # Migrate old 4/6-column headers to 5-column Branch-only history.
            if re.match(
                r"^\|\s*#\s*\|\s*Date\s*\|\s*Title\s*\|\s*Commits\s*\|\s*Branch\s*\|\s*Base Branch\s*\|\s*$",
                line,
            ):
                new_lines.append("| # | Date | Title | Commits | Branch |")
                continue
            if re.match(r"^\|\s*#\s*\|\s*Date\s*\|\s*Title\s*\|\s*Commits\s*\|\s*Branch\s*\|\s*$", line):
                new_lines.append("| # | Date | Title | Commits | Branch |")
                continue
            if re.match(r"^\|\s*#\s*\|\s*Date\s*\|\s*Title\s*\|\s*Commits\s*\|\s*$", line):
                new_lines.append("| # | Date | Title | Commits | Branch |")
                continue
            if re.match(r"^\|[-| ]+\|\s*$", line) and not header_written:
                new_lines.append("|---|------|-------|---------|--------|")
                new_lines.append(f"| {new_session} | {today} | {title} | {commit_display} | `{branch or '-'}` |")
                header_written = True
                continue
            new_lines.append(line)
            continue

        new_lines.append(line)

    index_file.write_text("\n".join(new_lines), encoding="utf-8")
    print("[OK] Updated index.md successfully!")
    return True


# =============================================================================
# Main Function
# =============================================================================

def _auto_commit_workspace(repo_root: Path) -> None:
    """Stage Trellis-owned workspace + current-task paths and commit.

    Path scope is restricted to specific products: the current developer's
    journal files + index.md, and ONLY the current task directory (resolved
    via ``get_current_task``). We never `git add` the whole `.trellis/` tree
    or iterate over all active task dirs (#303: parallel-window dirty task
    dirs must not be bundled into the session auto-commit). If `.gitignore`
    blocks the specific paths we warn + skip — never retry with ``-f``.

    Honors ``session_auto_commit`` in ``.trellis/config.yaml``: when set to
    ``false``, this function returns immediately without touching git
    (journal/index files are still written to disk by the caller).
    """
    if not get_session_auto_commit(repo_root):
        print(
            "[OK] session_auto_commit: false — skipping git stage/commit.",
            file=sys.stderr,
        )
        return

    commit_msg = get_session_commit_message(repo_root)
    # Resolve the current task so staging is scoped to its dir only. The ref
    # is ``.trellis/tasks/<name>`` (or under archive/) — pass the bare name.
    current = get_current_task(repo_root)
    if current:
        task_name = Path(current).name
        paths = safe_trellis_paths_to_add(repo_root, task_name=task_name)
    else:
        # Current task unknown (0 or >=2 parallel sessions — exactly the
        # parallel-window case #303 is about). Do NOT fall back to the wide
        # `tasks_dir.iterdir()` scan; that would re-leak other tasks' dirty
        # dirs into the session commit. Stage only the developer's journal/
        # index and skip every task dir.
        paths = [
            p
            for p in safe_trellis_paths_to_add(repo_root, task_name=None)
            if not p.startswith(f"{DIR_WORKFLOW}/{DIR_TASKS}/")
        ]
    if not paths:
        print("[OK] No workspace changes to commit.", file=sys.stderr)
        return

    success, _, err = safe_git_add(paths, repo_root)
    if not success:
        if err and "ignored by" in err.lower():
            print_gitignore_warning(paths)
        else:
            print(
                f"[WARN] git add failed: {err.strip() if err else 'unknown error'}",
                file=sys.stderr,
            )
        return

    # Check if there are staged changes for the paths we just staged.
    rc, _, _ = run_git(
        ["diff", "--cached", "--quiet", "--", *paths], cwd=repo_root
    )
    if rc == 0:
        print("[OK] No workspace changes to commit.", file=sys.stderr)
        return

    rc, _, commit_err = run_git(["commit", "-m", commit_msg], cwd=repo_root)
    if rc == 0:
        print(f"[OK] Auto-committed: {commit_msg}", file=sys.stderr)
    else:
        print(
            f"[WARN] Auto-commit failed: {commit_err.strip()}",
            file=sys.stderr,
        )


def add_session(
    title: str,
    commit: str = "-",
    auto_commit: bool = True,
    branch: str | None = None,
) -> int:
    """Record a session as a one-line index.md entry (journal retired)."""
    repo_root = get_repo_root()
    ensure_developer(repo_root)

    developer = get_developer(repo_root)
    if not developer:
        print("Error: Developer not initialized", file=sys.stderr)
        return 1

    dev_dir = get_workspace_dir(repo_root)
    if not dev_dir:
        print("Error: Workspace directory not found", file=sys.stderr)
        return 1

    index_file = dev_dir / "index.md"
    today = datetime.now().strftime("%Y-%m-%d")

    current_session = get_current_session(index_file)
    new_session = current_session + 1

    print("========================================", file=sys.stderr)
    print("ADD SESSION (index one-liner)", file=sys.stderr)
    print("========================================", file=sys.stderr)
    print(f"Session: {new_session}", file=sys.stderr)
    print(f"Title: {title}", file=sys.stderr)
    print(f"Commit: {commit}", file=sys.stderr)
    print("", file=sys.stderr)

    if not update_index(
        index_file,
        dev_dir,
        title,
        commit,
        new_session,
        today,
        branch,
    ):
        return 1

    print("", file=sys.stderr)
    print(f"[OK] Session {new_session} recorded in index.md", file=sys.stderr)

    # Auto-commit workspace changes
    if auto_commit:
        print("", file=sys.stderr)
        _auto_commit_workspace(repo_root)

    return 0


# =============================================================================
# Main Entry
# =============================================================================

def main() -> int:
    """CLI entry point."""
    parser = argparse.ArgumentParser(
        description="Record a session as a one-line entry in index.md"
    )
    parser.add_argument("--title", required=True, help="Session title")
    parser.add_argument("--commit", default="-", help="Comma-separated commit hashes")
    parser.add_argument("--summary", default=None,
                        help="Accepted for compatibility; not persisted "
                             "(journal retired — summaries live in PR "
                             "descriptions / task archives)")
    parser.add_argument("--package", default=None,
                        help="Accepted for compatibility; not persisted "
                             "(package tags only existed in journal entries)")
    parser.add_argument("--branch", help="Branch name (auto-detected if omitted)")
    parser.add_argument("--no-commit", action="store_true",
                        help="Skip auto-commit of workspace changes")

    args = parser.parse_args()

    if args.summary or args.package:
        print("[note] --summary/--package are not persisted since journal "
              "retirement; keep summaries in the PR description / task archive.",
              file=sys.stderr)

    # Load active task once — used by branch resolution
    repo_root = get_repo_root()
    current = get_current_task(repo_root)
    task_data = load_task(repo_root / current) if current else None

    # Resolve branch: CLI → task.json → git auto-detect → None
    branch = args.branch

    if not branch:
        if task_data and task_data.raw.get("branch"):
            branch = task_data.raw["branch"]
        else:
            _, branch_out, _ = run_git(["branch", "--show-current"], cwd=repo_root)
            detected = branch_out.strip()
            if detected:
                branch = detected

    return add_session(
        args.title, args.commit,
        auto_commit=not args.no_commit,
        branch=branch,
    )


if __name__ == "__main__":
    sys.exit(main())
