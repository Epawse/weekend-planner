"""Shared SessionStart routing hints.

These hints are intentionally compact: SessionStart should route the AI to the
right source of truth, not duplicate the full project SOP.
"""

from __future__ import annotations


def build_routing_hints() -> str:
    """Return high-signal source-routing guidance for new sessions."""
    return "\n".join(
        [
            "<routing-hints>",
            "High-signal routing hints; load detailed files on demand.",
            "- GitHub PR/open PR/ship/CI review/AI Review/merge/remote delivery -> read `.trellis/spec/guides/git-pr-sop.md`; ship or merge also read `.trellis/commands/ship.md`.",
            "- Remote branch or PR status audit -> run read-only `git fetch --prune` first.",
            "- GitHub PR status -> use GitHub CLI/API from Git/PR SOP (`gh pr ...`, `gh api ...`); do not use `command -v gh`, `refs/pull/*`, or webpage curl as primary evidence.",
            "</routing-hints>",
        ]
    )
