#!/usr/bin/env python3
"""Two-tier PreToolUse hook enforcing the git/PR SOP.

Tier 1 — DENY (hard block via permissionDecision:"deny"):
  - git commit on a protected branch (main/master)
  - git push to main/master (on-branch or explicit refspec)
  - git push --force (without --with-lease)
  - git commit --no-verify / --no-gpg-sign
  - gh pr merge on a branch with an unfinalized Trellis task (route via /trellis:ship)

Tier 2 — ADVISORY (non-blocking reminder via additionalContext):
  - git add . / -A / --all
  - git checkout -b / switch -c (+ branch-name validation)
  - git branch -D / -d
  - git reset --hard / --soft
  - git rebase / git merge
  - gh pr create / ready / merge / review

Escape hatches (deny downgraded to advisory):
  - TRELLIS_HOOKS=0 or TRELLIS_DISABLE_HOOKS=1 (kill-switch)
  - Command or commit message contains [break-glass]: — carry it via the
    zsh-safe no-op prefix `: '[break-glass]:';` (a bare [break-glass]: prefix
    is a glob error in zsh)

Fail-open: malformed stdin, rev-parse failure, any exception -> silent exit 0.

Output contract (PreToolUse JSON, exit 0 always):
  Deny:    {"hookSpecificOutput": {"hookEventName":"PreToolUse",
            "permissionDecision":"deny", "permissionDecisionReason":"...",
            "additionalContext":"..."}}
  Advisory: {"hookSpecificOutput": {"hookEventName":"PreToolUse",
            "additionalContext":"..."}}

Cross-platform: pure Python stdlib. Works on macOS, Linux, Windows.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
import os
import re
import subprocess
import sys
from pathlib import Path

# Force UTF-8 on stdin/stdout/stderr on Windows.
if sys.platform.startswith("win"):
    import io as _io

    for _stream_name in ("stdin", "stdout", "stderr"):
        _stream = getattr(sys, _stream_name, None)
        if _stream is None:
            continue
        if hasattr(_stream, "reconfigure"):
            try:
                _stream.reconfigure(encoding="utf-8", errors="replace")
            except Exception:
                pass
        elif hasattr(_stream, "detach"):
            try:
                setattr(
                    sys,
                    _stream_name,
                    _io.TextIOWrapper(
                        _stream.detach(), encoding="utf-8", errors="replace"
                    ),
                )
            except Exception:
                pass


# ---------------------------------------------------------------------------
# Pattern definitions
# ---------------------------------------------------------------------------

# Advisory-tier patterns (regex applied to the stripped command).
_GOVERNED_PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    ("add-all", re.compile(r"\bgit\s+add\s+(?:-A\b|--all\b|\.(?:\s|$))")),
    ("force-push", re.compile(r"\bgit\s+push\b[^|;&\n]*--force(?!-with-lease)\b")),
    ("force-with-lease", re.compile(r"\bgit\s+push\b[^|;&\n]*--force-with-lease\b")),
    ("push", re.compile(r"\bgit\s+push\b")),
    ("branch-create", re.compile(r"\bgit\s+(?:checkout\s+-b|switch\s+-c)\b")),
    ("branch-delete", re.compile(r"\bgit\s+branch\s+(?:-D\b|-d\b|--delete\b)")),
    ("reset-hard", re.compile(r"\bgit\s+reset\b[^|;&\n]*--hard\b")),
    ("reset-soft", re.compile(r"\bgit\s+reset\b[^|;&\n]*--soft\b")),
    ("rebase", re.compile(r"\bgit\s+rebase\b")),
    ("merge", re.compile(r"\bgit\s+merge\b")),
    ("commit-bypass", re.compile(r"\bgit\s+commit\b[^|;&\n]*(?:--no-verify|--no-gpg-sign)\b")),
    ("pr-create", re.compile(r"\bgh\s+pr\s+create\b")),
    ("pr-ready", re.compile(r"\bgh\s+pr\s+ready\b")),
    ("pr-merge", re.compile(r"\bgh\s+pr\s+merge\b")),
    ("pr-review", re.compile(r"\bgh\s+pr\s+review\b")),
]

# Rationale snippets per advisory surface.
_RATIONALE: dict[str, str] = {
    "add-all": (
        "`git add .` / `-A` / `--all` is FORBIDDEN (Forbidden Git Operations) "
        "-- stage explicit paths to avoid leaking secrets, build artifacts, or "
        "unrelated changes."
    ),
    "force-push": (
        "Plain `--force` is FORBIDDEN by the SOP. Use `--force-with-lease`, "
        "and only on unpublished branches."
    ),
    "force-with-lease": (
        "`--force-with-lease` is allowed only on unpublished / pre-review "
        "branches. Avoid on branches with anchored review comments."
    ),
    "push": (
        "Verify the branch follows the naming convention. `main` is "
        "branch-protected -- direct push will be rejected."
    ),
    "branch-create": (
        "Confirm the branch name follows `<prefix>/<scope>-<brief>` "
        "(see Branch Naming Convention)."
    ),
    "branch-delete": (
        "Branch deletion is destructive and `allow_deletions:false` guards "
        "`main`. Confirm the branch is merged or backed up first."
    ),
    "reset-hard": (
        "`git reset --hard` discards working-tree changes AND moves the branch "
        "ref. Confirm nothing uncommitted is lost; on a pushed branch this "
        "rewrites your local view of history."
    ),
    "reset-soft": (
        "`git reset --soft` rewinds the branch ref but keeps changes staged "
        "(the SOP commit-reorg flow). Back up the branch first: "
        "`git branch <name>-backup`."
    ),
    "rebase": (
        "Rebase is allowed on private branches. For public branches with "
        "review comments, prefer merging `main` into the branch."
    ),
    "merge": (
        "Rebased branches must merge with `--ff-only` (NOT `--no-ff`). "
        "`required_linear_history` forbids merge commits. See the Merge And "
        "Cleanup section."
    ),
    "commit-bypass": (
        "`--no-verify` / `--no-gpg-sign` skip the safety net and are "
        "FORBIDDEN. Fix the hook failure instead."
    ),
    "pr-create": (
        "Open as `--draft` first. Apply self-review (nit/suggestion/blocking "
        "taxonomy) before marking Ready."
    ),
    "pr-ready": (
        "Before `gh pr ready`: all `blocking:` threads resolved, required "
        "checks green, and self-review recorded (PR Review Etiquette). Do not "
        "mark Ready prematurely."
    ),
    "pr-merge": (
        "Deliver task branches via `/trellis:ship` (finalize-before-push). If "
        "merging manually: confirm CI passed, all `blocking:` review threads are "
        "resolved, and the merge strategy matches the History Strategy Matrix. "
        "`--merge` (merge commit) is rejected by `required_linear_history` -- use "
        "`--squash` or `--rebase`."
    ),
    "pr-review": (
        "Use the `nit:` / `suggestion:` / `blocking:` prefix taxonomy on "
        "every inline comment."
    ),
}

# Branches that must never receive a direct commit.
_PROTECTED_BRANCHES = {"main", "master"}

# Plain `git commit` (any form) — triggers on-protected-branch check.
_COMMIT_RE = re.compile(r"\bgit\s+commit\b")

# Detect push-to-main via explicit refspec (e.g. `origin main`, `HEAD:main`).
_PUSH_MAIN_REFSPEC_RE = re.compile(
    r"\bgit\s+push\b[^|;&\n]*(?:\s+origin\s+(?:main|master)\b|\s+\S*:(?:main|master)\b)"
)

# Extract branch name from branch-create, handling quotes and flags.
_BRANCH_NAME_RE = re.compile(
    r"""\bgit\s+(?:checkout\s+-b|switch\s+-c)"""
    r"""(?:\s+-[fqt])*"""  # skip short flags like -f, -q, -t
    r"""\s+["']?([^"'\s]+)["']?"""
)

# Branch naming convention: <prefix>/<kebab>.
_VALID_BRANCH_RE = re.compile(
    r"^(?:feat|fix|hotfix|chore|docs|refactor|test|perf|revert)"
    r"/[a-z0-9]+(?:-[a-z0-9]+)*$"
)

# Detect `git -C <dir>` before the subcommand.
# Handles: git -C /path, git -C "/path with spaces", git -C '/path'
_GIT_C_DIR_RE = re.compile(
    r"""\bgit\s+-C\s+"""
    r"""(?:"([^"]+)"|'([^']+)'|(\S+))"""
)

# Strip `git -C <dir>` from command so patterns like `\bgit\s+commit\b` still match.
_GIT_C_STRIP_RE = re.compile(
    r"""(\bgit)\s+-C\s+(?:"[^"]*"|'[^']*'|\S+)"""
)

# Regex to strip -m / -F message arguments before pattern matching.
# Handles: -m "...", -m '...', -m<word>, -F <file>
_MSG_ARG_RE = re.compile(
    r"""\s-[mF]\s*"[^"]*\""""  # -m "..." or -F "..."
    r"""|"""
    r"""\s-[mF]\s*'[^']*'"""  # -m '...' or -F '...'
    r"""|"""
    r"""\s-[mF]\s+\S+"""  # -m <word> or -F <file> (unquoted, space-separated)
)

# Regex to strip long-form text arguments (--body, --title, --subject, --message)
# that may contain governed keywords as documentation text.
# Handles: --body "...", --body '...', --body "$(cat <<'EOF'...EOF)"
_LONG_ARG_RE = re.compile(
    r"""\s--(?:body|title|subject|message)\s+"[^"]*\""""
    r"""|"""
    r"""\s--(?:body|title|subject|message)\s+'[^']*'"""
    r"""|"""
    r"""\s--(?:body|title|subject|message)\s+"\$\(cat\s+<<'?[A-Z_]+'?\n[\s\S]*?\n[A-Z_]+\n\)\""""
    r"""|"""
    r"""\s--(?:body|title|subject|message)\s+\S+"""
)


# ---------------------------------------------------------------------------
# Helper functions
# ---------------------------------------------------------------------------


def _strip_message_args(cmd: str) -> str:
    """Remove -m/-F and --body/--title/--subject/--message arguments.

    Prevents commit messages and PR body text containing governed keywords
    (e.g. "git push --force") from self-triggering the hook.
    """
    result = _LONG_ARG_RE.sub("", cmd)
    return _MSG_ARG_RE.sub("", result)


def _strip_git_c(cmd: str) -> str:
    """Strip `git -C <dir>` from the command, leaving `git <subcommand>`.

    This allows patterns like `\\bgit\\s+commit\\b` to match commands that use
    `-C <dir>` to specify the working directory.
    """
    return _GIT_C_STRIP_RE.sub(r"\1", cmd)


def _resolve_git_dir(cmd: str, payload_cwd: str | None) -> str | None:
    """Determine the git working directory for branch detection.

    Priority: explicit `git -C <dir>` in the command > payload cwd > None.
    """
    m = _GIT_C_DIR_RE.search(cmd)
    if m:
        # Groups: (1) double-quoted, (2) single-quoted, (3) unquoted
        return m.group(1) or m.group(2) or m.group(3)
    return payload_cwd


def _resolve_branch(git_dir: str | None) -> str | None:
    """Best-effort current branch name via `git rev-parse`. None on any failure."""
    try:
        git_cmd = ["git"]
        if git_dir:
            git_cmd.extend(["-C", git_dir])
        git_cmd.extend(["rev-parse", "--abbrev-ref", "HEAD"])
        result = subprocess.run(
            git_cmd,
            capture_output=True,
            text=True,
            timeout=3,
        )
    except Exception:
        return None
    if result.returncode != 0:
        return None
    branch = result.stdout.strip()
    # "HEAD" is returned for detached HEAD state — treat as unknown.
    if not branch or branch == "HEAD":
        return None
    return branch


def _repo_root(git_dir: str | None) -> Path | None:
    """Best-effort repo root via `git rev-parse --show-toplevel`. None on failure."""
    try:
        git_cmd = ["git"]
        if git_dir:
            git_cmd.extend(["-C", git_dir])
        git_cmd.extend(["rev-parse", "--show-toplevel"])
        result = subprocess.run(git_cmd, capture_output=True, text=True, timeout=3)
    except Exception:
        return None
    if result.returncode != 0:
        return None
    top = result.stdout.strip()
    return Path(top) if top else None


def _unfinalized_task_for_branch(git_dir: str | None, branch: str | None) -> str | None:
    """Return "<name> (status=<status>)" when the current branch has a non-archived
    Trellis task in status "in_progress"; else None.

    Branch-based, session-agnostic, pure file reads. Fail-open: any error (no repo,
    no `.trellis`, unreadable/invalid task.json) returns None so the hook never blocks
    on its own failure. A finalized task lives under `tasks/archive/**` and is not
    matched by the single-level `*/task.json` glob, so archiving flips merge from
    blocked to allowed.
    """
    if not branch:
        return None
    try:
        root = _repo_root(git_dir)
        if root is None:
            return None
        tasks_dir = root / ".trellis" / "tasks"
        if not tasks_dir.is_dir():
            return None
        for task_json in tasks_dir.glob("*/task.json"):
            if "archive" in task_json.relative_to(tasks_dir).parts:
                continue
            try:
                data = json.loads(task_json.read_text(encoding="utf-8"))
            except (OSError, ValueError):
                continue
            if not isinstance(data, dict):
                continue
            # Only in_progress work blocks a merge: it may have evidence that
            # is not yet finalized into the PR. A planning task has produced
            # nothing to finalize — coordination parents in particular sit on
            # main in planning state for their whole multi-child lifetime and
            # must not block unrelated merges (e.g. release-bot PRs).
            if data.get("branch") == branch and data.get("status") == "in_progress":
                name = data.get("name") or task_json.parent.name
                return f"{name} (status={data.get('status')})"
    except Exception:
        return None
    return None


def _extract_command(input_data: dict) -> str | None:
    """Pull the bash command out of the PreToolUse payload."""
    if input_data.get("tool_name") != "Bash":
        return None
    tool_input = input_data.get("tool_input") or {}
    cmd = tool_input.get("command")
    if not isinstance(cmd, str) or not cmd.strip():
        return None
    return cmd


def _has_break_glass(cmd: str) -> bool:
    """Check if the command contains the [break-glass]: escape marker.

    Substring match on purpose: a bare `[break-glass]:` prefix is a glob error
    in zsh, so the documented carrier is a quoted no-op — `: '[break-glass]:';`
    — but any form that keeps the literal marker in the command works.
    """
    return "[break-glass]:" in cmd


# `git push` positional args (everything after `push` up to a shell separator).
_PUSH_ARGS_RE = re.compile(r"\bgit\s+push\s+([^|;&\n]*)")


def _push_has_explicit_refspec(stripped_cmd: str) -> bool:
    """True iff the push names both a remote and at least one refspec.

    Used only AFTER the explicit main/master refspec rule has not matched, so
    a surviving refspec is known to target a non-protected ref. Flag-value
    false positives (e.g. `--push-option x`) err toward allowing, which is
    the lesser failure next to blocking legitimate release-branch pushes.
    """
    m = _PUSH_ARGS_RE.search(stripped_cmd)
    if not m:
        return False
    tokens = [t for t in m.group(1).split() if t and not t.startswith("-")]
    return len(tokens) >= 2


def _match_surfaces(cmd: str) -> list[str]:
    """Return advisory surface labels that match the (stripped) command."""
    matched: list[str] = []
    for label, pattern in _GOVERNED_PATTERNS:
        if pattern.search(cmd):
            matched.append(label)
    # Dedupe: more specific push variants subsume generic push.
    if "force-push" in matched and "push" in matched:
        matched.remove("push")
    if "force-with-lease" in matched and "push" in matched:
        matched.remove("push")
    return matched


def _dynamic_advisory_surfaces(
    cmd: str, branch: str | None
) -> list[tuple[str, str]]:
    """State/argument-dependent advisory surfaces (non-deny tier)."""
    surfaces: list[tuple[str, str]] = []

    # Branch-name convention check on branch-create.
    name_match = _BRANCH_NAME_RE.search(cmd)
    if name_match:
        name = name_match.group(1)
        if not _VALID_BRANCH_RE.match(name):
            surfaces.append(
                (
                    "branch-name-invalid",
                    f"Branch name `{name}` does NOT match "
                    "`<prefix>/<scope>-<brief>` (prefix in "
                    "feat|fix|hotfix|chore|docs|refactor|test|perf|revert, "
                    "lowercase kebab-case). Rename before pushing.",
                )
            )

    return surfaces


# ---------------------------------------------------------------------------
# Deny-tier evaluation
# ---------------------------------------------------------------------------

# Deny reasons (model-facing: tells the agent what's wrong and how to fix).
_DENY_REASONS: dict[str, str] = {
    "commit-on-protected": (
        "Blocked by git-pr-sop: committing directly on `{branch}` is "
        "forbidden (branch-protected integration baseline). Create a feature "
        "branch first: `git checkout -b <prefix>/<scope>-<brief>`"
    ),
    "push-to-main": (
        "Blocked by git-pr-sop: pushing directly to `{branch}` is forbidden "
        "(branch-protected). Push to a feature branch and open a PR instead."
    ),
    "force-push": (
        "Blocked by git-pr-sop: `git push --force` is forbidden. Use "
        "`--force-with-lease` on unpublished branches only."
    ),
    "commit-bypass": (
        "Blocked by git-pr-sop: `--no-verify`/`--no-gpg-sign` bypass safety "
        "hooks and are forbidden. Fix the hook failure instead."
    ),
    "merge-unfinalized-task": (
        "Blocked by git-pr-sop: branch `{branch}` has an unfinalized Trellis task "
        "{task}. Do not `gh pr merge` directly -- route delivery through "
        "`/trellis:ship` (or `python3 ./scripts/trellis_ship.py merge`), which "
        "finalizes the task into the PR before merge. Escape: start the command "
        "with `: '[break-glass]:';` (zsh-safe no-op carrying the marker) or set "
        "`TRELLIS_HOOKS=0`."
    ),
}


def _evaluate_deny(
    cmd: str, stripped_cmd: str, branch: str | None
) -> tuple[str | None, str | None]:
    """Evaluate deny-tier surfaces. Returns (deny_label, reason) or (None, None).

    Only the first matching deny is returned (they are mutually exclusive in
    practice, but if multiple match, the first wins).
    """
    # 1. commit --no-verify / --no-gpg-sign
    if re.search(
        r"\bgit\s+commit\b[^|;&\n]*(?:--no-verify|--no-gpg-sign)\b", stripped_cmd
    ):
        return "commit-bypass", _DENY_REASONS["commit-bypass"]

    # 2. git push --force (without --with-lease)
    if re.search(
        r"\bgit\s+push\b[^|;&\n]*--force(?!-with-lease)\b", stripped_cmd
    ):
        return "force-push", _DENY_REASONS["force-push"]

    # 3. push-to-main: on main/master OR explicit refspec to main
    if re.search(r"\bgit\s+push\b", stripped_cmd):
        # Explicit refspec to main/master
        if _PUSH_MAIN_REFSPEC_RE.search(stripped_cmd):
            target = "main"
            if "master" in stripped_cmd:
                target = "master"
            return "push-to-main", _DENY_REASONS["push-to-main"].format(
                branch=target
            )
        # On main/master and pushing. Only a bare push (which would push the
        # current protected branch) is denied; a push whose explicit refspec
        # targets a non-protected branch (already vetted by the refspec rule
        # above — e.g. `git push origin changeset-release/main` after an
        # in-command checkout, or `git push -u origin feat/x` right after
        # `git switch -c feat/x`) must not be blocked just because the hook
        # ran while HEAD was still on main.
        if branch in _PROTECTED_BRANCHES and not _push_has_explicit_refspec(
            stripped_cmd
        ):
            return "push-to-main", _DENY_REASONS["push-to-main"].format(
                branch=branch
            )

    # 4. commit on protected branch
    if _COMMIT_RE.search(stripped_cmd):
        if branch in _PROTECTED_BRANCHES:
            return "commit-on-protected", _DENY_REASONS[
                "commit-on-protected"
            ].format(branch=branch)

    return None, None


# ---------------------------------------------------------------------------
# Output builders
# ---------------------------------------------------------------------------


def _build_reminder_text(surfaces: list[tuple[str, str]]) -> str:
    """Build the <git-sop-reminder> block from matched surfaces."""
    lines = [
        "<git-sop-reminder>",
        "This Bash command touches a git/PR surface governed by "
        "`.trellis/spec/guides/git-pr-sop.md`.",
        "Consult the SOP for: Branch Naming, Commit Rules, History Strategy "
        "Matrix, Branch Protection, PR Review Etiquette, Hotfix Procedure.",
        "",
        "Surfaces matched:",
    ]
    for label, rationale in surfaces:
        lines.append(f"  - {label}: {rationale}")
    lines.append("</git-sop-reminder>")
    return "\n".join(lines)


def _record_metric(git_dir: str | None, tier: str, labels: list[str]) -> None:
    """Append a one-line usage record for constraint-pruning analytics.

    Fail-open by design: metrics must never break the hook. Records land in
    .trellis/.runtime/ (never committed), one JSON object per line.
    """
    try:
        root = git_dir or os.getcwd()
        runtime = os.path.join(root, ".trellis", ".runtime")
        if not os.path.isdir(os.path.join(root, ".trellis")):
            return
        os.makedirs(runtime, exist_ok=True)
        record = {
            "ts": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "hook": "git-sop",
            "tier": tier,
            "labels": labels,
        }
        with open(os.path.join(runtime, "hook-metrics.jsonl"), "a", encoding="utf-8") as fh:
            fh.write(json.dumps(record, ensure_ascii=False) + "\n")
    except Exception:
        pass


def _emit_deny(reason: str, advisory_text: str) -> None:
    """Print deny JSON to stdout (exit 0)."""
    output: dict = {
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "deny",
            "permissionDecisionReason": reason,
        }
    }
    if advisory_text:
        output["hookSpecificOutput"]["additionalContext"] = advisory_text
    print(json.dumps(output))


def _emit_advisory(advisory_text: str) -> None:
    """Print advisory-only JSON to stdout (exit 0)."""
    output = {
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "additionalContext": advisory_text,
        }
    }
    print(json.dumps(output))


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main() -> int:
    # Honor global hook kill-switches.
    if os.environ.get("TRELLIS_HOOKS") == "0" or os.environ.get(
        "TRELLIS_DISABLE_HOOKS"
    ) == "1":
        return 0

    try:
        data = json.load(sys.stdin)
    except (json.JSONDecodeError, ValueError):
        return 0

    cmd = _extract_command(data)
    if cmd is None:
        return 0

    # Read payload cwd for deterministic branch detection.
    payload_cwd = data.get("cwd")
    if not isinstance(payload_cwd, str):
        payload_cwd = None

    # Strip -m/-F message bodies to prevent self-triggering,
    # then strip -C <dir> so patterns like `\bgit\s+commit\b` still match.
    stripped_cmd = _strip_message_args(cmd)
    stripped_cmd = _strip_git_c(stripped_cmd)

    # Resolve git working directory and current branch.
    git_dir = _resolve_git_dir(cmd, payload_cwd)
    branch = _resolve_branch(git_dir)

    # --- Deny tier ---
    deny_label, deny_reason = _evaluate_deny(cmd, stripped_cmd, branch)

    # gh pr merge on a branch with an unfinalized Trellis task -> deny.
    # Forces delivery through /trellis:ship (finalize-before-push). trellis_ship.py
    # merge spawns `gh pr merge` as a subprocess, not an agent Bash call, so it is
    # not intercepted here.
    if not deny_label and re.search(r"\bgh\s+pr\s+merge\b", stripped_cmd):
        unfinalized = _unfinalized_task_for_branch(git_dir, branch)
        if unfinalized:
            deny_label = "merge-unfinalized-task"
            deny_reason = _DENY_REASONS["merge-unfinalized-task"].format(
                branch=branch, task=unfinalized
            )

    # --- Advisory tier ---
    advisory_surfaces: list[tuple[str, str]] = [
        (label, _RATIONALE.get(label, "Check the SOP for applicable rules."))
        for label in _match_surfaces(stripped_cmd)
    ]
    advisory_surfaces.extend(_dynamic_advisory_surfaces(stripped_cmd, branch))

    # Also add commit-on-protected as advisory text when deny fires for it.
    if deny_label == "commit-on-protected":
        advisory_surfaces.append(
            (
                "commit-on-protected",
                f"You are committing directly on `{branch}` -- the integration "
                "baseline. SOP mandates a feature branch "
                "(`<prefix>/<scope>-<brief>`). Create one first.",
            )
        )
    elif deny_label == "push-to-main":
        advisory_surfaces.append(
            (
                "push-to-main",
                "Direct push to `main`/`master` is forbidden. Push to a "
                "feature branch and open a PR.",
            )
        )

    # Build advisory text (used in both deny and advisory-only paths).
    advisory_text = ""
    if advisory_surfaces:
        advisory_text = _build_reminder_text(advisory_surfaces)

    # --- Escape hatch: break-glass downgrades deny to advisory ---
    if deny_label and _has_break_glass(cmd):
        _record_metric(git_dir, "break-glass", [deny_label])
        deny_label = None
        deny_reason = None

    # --- Emit output ---
    if deny_label and deny_reason:
        _record_metric(git_dir, "deny", [deny_label])
        _emit_deny(deny_reason, advisory_text)
    elif advisory_text:
        _record_metric(git_dir, "advisory", [label for label, _ in advisory_surfaces])
        _emit_advisory(advisory_text)
    # else: no output, silent exit 0.

    return 0


if __name__ == "__main__":
    sys.exit(main())
