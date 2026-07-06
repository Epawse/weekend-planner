"""Shared builder for the SessionStart local-setup hints block.

Used by both the Claude Code and Codex `session-start.py` hooks so the
onboarding nudge for incomplete local Trellis setup stays identical across
platforms instead of living in one platform's hook only.

Normal sessions receive an empty string. When a local-only prerequisite is
missing, this returns AI-facing timing/wording constraints rather than turning
SessionStart into a user-facing setup wizard.
"""

from __future__ import annotations

from pathlib import Path

from .git import run_git
from .paths import get_developer


def _repo_relative(repo_root: Path, path: Path) -> str:
    try:
        return path.relative_to(repo_root).as_posix()
    except ValueError:
        return str(path)


def _hooks_path(repo_root: Path) -> str:
    code, out, _ = run_git(["config", "--get", "core.hooksPath"], cwd=repo_root)
    if code != 0:
        return ""
    return out.strip()


def build_local_setup_hints(repo_root: Path) -> str:
    """Return non-invasive AI guidance for incomplete local Trellis setup.

    Normal sessions should receive no extra text. When a local-only prerequisite
    is missing, this gives the AI timing and wording constraints instead of
    turning SessionStart into a user-facing setup wizard.
    """
    trellis_dir = repo_root / ".trellis"
    developer_file = trellis_dir / ".developer"
    workspace_dir = trellis_dir / "workspace"
    hints: list[str] = []
    needs_first_reply_aside = False

    developer_name = get_developer(repo_root) or None
    if not developer_file.is_file() or developer_name is None:
        needs_first_reply_aside = True
        hints.append(
            "- Developer identity is not initialized. After answering the user's first request, "
            "add one short aside asking what developer name to use and offer to run "
            "`python3 ./.trellis/scripts/init_developer.py <name>`."
        )
    else:
        expected_workspace = workspace_dir / developer_name
        if not expected_workspace.is_dir():
            needs_first_reply_aside = True
            hints.append(
                f"- Developer identity is `{developer_name}`, but "
                f"`{_repo_relative(repo_root, expected_workspace)}` is missing. "
                "After answering the user's first request, add one short aside offering to repair "
                "the local Trellis workspace."
            )

    hooks_path = _hooks_path(repo_root)
    if hooks_path != ".githooks":
        hooks_display = hooks_path or "(unset)"
        hints.append(
            f"- Git hooks path is `{hooks_display}`, not `.githooks`. Do not interrupt the "
            "first reply only for this; before committing or relying on local Git hooks, "
            "offer to run `git config core.hooksPath .githooks`, or the project's documented "
            "bootstrap command if it configures Git hooks."
        )

    if not hints:
        return ""

    lines = [
        "<trellis-local-setup-hints>",
        "Local Trellis setup is incomplete. This block is for AI behavior, not a setup banner.",
        "Normal priority: answer the user's request first; mention setup only as a short aside or when it blocks the requested action.",
    ]
    if needs_first_reply_aside:
        lines.append(
            "Because developer identity or workspace state is missing, the first turn must include one brief aside after the required SessionStart notice and the direct answer; do not turn it into onboarding."
        )
    lines.extend(
        [
            "Do not suggest or run `trellis init`; this repository already contains project Trellis files.",
            *hints,
            "</trellis-local-setup-hints>",
        ]
    )
    return "\n".join(lines)
