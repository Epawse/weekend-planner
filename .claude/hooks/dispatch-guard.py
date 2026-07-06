#!/usr/bin/env python3
"""Two-tier PreToolUse hook governing sub-agent dispatch routing.

Routing lives in typed agent definitions (.claude/agents/*.md pin their own
model), not in prose: an unrouted dispatch — no `subagent_type` AND no
explicit `model` — silently inherits the main session's full-tier model.
That is how the 2026-07-05 triple-agent quota crash happened (3 prototype
agents inherited the top-tier model concurrently and were all killed).

Tier 1 — ADVISORY (non-blocking reminder via additionalContext):
  - any unrouted Task/Agent dispatch: remind that routing is picked at
    dispatch time (typed subagent_type OR explicit model), not remembered.

Tier 2 — DENY (hard block via permissionDecision:"deny"):
  - the Nth (default 3rd) unrouted dispatch within a rolling window
    (default 120s) in the same session — the quota-crash batch pattern.

Escape hatches:
  - TRELLIS_HOOKS=0 or TRELLIS_DISABLE_HOOKS=1 (kill-switch)
  - "[break-glass]:" anywhere in the dispatch prompt (deny -> advisory)
  - TRELLIS_DISPATCH_GUARD_MAX / TRELLIS_DISPATCH_GUARD_WINDOW env overrides

Fail-open: malformed stdin, missing .trellis, any exception -> silent allow.
State: .trellis/.runtime/dispatch-guard-<session>.json (never committed).
Cross-platform: pure Python stdlib.
"""
from __future__ import annotations

import hashlib
import json
import os
import sys
import time
from pathlib import Path

# Force UTF-8 on Windows streams.
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

_DISPATCH_TOOL_NAMES = {"task", "agent", "subagent"}
# Agent types that carry NO model pin in their definition — dispatching them
# without an explicit `model` still inherits the main session's full-tier
# model (field evidence 2026-07-05: 7 `claude`-type dispatches all ran Fable).
_PINLESS_TYPES = {"claude", "general-purpose"}
_TYPE_KEYS = (
    "subagent_type",
    "subagentType",
    "subagent_type_name",
    "subagentTypeName",
    "agent_type",
    "agentType",
)

DEFAULT_WINDOW_SECONDS = 120
DEFAULT_MAX_UNROUTED = 3


def _env_int(name: str, default: int) -> int:
    try:
        value = int(os.environ.get(name, ""))
        return value if value > 0 else default
    except (TypeError, ValueError):
        return default


def _string_value(value) -> str:
    return value.strip() if isinstance(value, str) else ""


def _extract_subagent_type(tool_input: dict) -> str:
    """Best-effort typed-dispatch detection across platform encodings."""
    for key in _TYPE_KEYS:
        value = tool_input.get(key)
        direct = _string_value(value)
        if direct:
            return direct
        if isinstance(value, dict):
            for nested_key in ("name", "case"):
                nested = _string_value(value.get(nested_key))
                if nested:
                    return nested
    return ""


def _find_repo_root(start_path: str) -> Path | None:
    current = Path(start_path).resolve()
    while current != current.parent:
        if (current / ".git").exists():
            return current
        current = current.parent
    return None


def _state_path(repo_root: Path, session_id: str) -> Path | None:
    """State file under .trellis/.runtime; None when the repo has no .trellis."""
    if not (repo_root / ".trellis").is_dir():
        return None
    runtime = repo_root / ".trellis" / ".runtime"
    digest = hashlib.sha1(session_id.encode("utf-8")).hexdigest()[:12]
    return runtime / f"dispatch-guard-{digest}.json"


def _count_in_window(state_file: Path | None, window_seconds: int) -> int:
    """Prior unrouted dispatches still inside the rolling window."""
    if state_file is None or not state_file.exists():
        return 0
    try:
        stamps = json.loads(state_file.read_text(encoding="utf-8"))
        now = time.time()
        return len(
            [s for s in stamps if isinstance(s, (int, float)) and now - s < window_seconds]
        )
    except Exception:
        return 0


def _record_dispatch(state_file: Path | None, window_seconds: int) -> None:
    if state_file is None:
        return
    try:
        state_file.parent.mkdir(parents=True, exist_ok=True)
        now = time.time()
        stamps: list[float] = []
        if state_file.exists():
            try:
                stamps = [
                    s
                    for s in json.loads(state_file.read_text(encoding="utf-8"))
                    if isinstance(s, (int, float)) and now - s < window_seconds
                ]
            except Exception:
                stamps = []
        stamps.append(now)
        state_file.write_text(json.dumps(stamps), encoding="utf-8")
    except Exception:
        pass


def _record_metric(repo_root: Path | None, tier: str, labels: list[str]) -> None:
    """Append a hook-metrics record for constraint-pruning analytics. Fail-open."""
    try:
        if repo_root is None or not (repo_root / ".trellis").is_dir():
            return
        runtime = repo_root / ".trellis" / ".runtime"
        runtime.mkdir(parents=True, exist_ok=True)
        from datetime import datetime, timezone

        record = {
            "ts": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "hook": "dispatch-guard",
            "tier": tier,
            "labels": labels,
        }
        with open(runtime / "hook-metrics.jsonl", "a", encoding="utf-8") as fh:
            fh.write(json.dumps(record, ensure_ascii=False) + "\n")
    except Exception:
        pass


def _advisory_text(count: int, max_unrouted: int, window_seconds: int) -> str:
    return "\n".join(
        [
            "<dispatch-routing-reminder>",
            "This sub-agent dispatch is UNROUTED: no `subagent_type` and no explicit "
            "`model`, so it inherits the main session's full-tier model.",
            "Routing is decided at dispatch time, not remembered from prose:",
            "  - typed dispatch: pick an agent type — the model is pinned in its "
            "definition (e.g. trellis-research = low tier for bounded recon; "
            "trellis-implement / trellis-check / review gates pin their own).",
            "  - untyped or pinless-typed (claude/general-purpose) dispatch: set "
            "`model` explicitly — standard: `sonnet` + effort `xhigh` for bounded/"
            "mechanical work, `opus` + effort `xhigh` for heavier subagent work "
            "(2026-07-06 user ruling: below xhigh these models degrade).",
            f"Batch rule: {max_unrouted}+ unrouted full-tier dispatches within "
            f"{window_seconds}s are denied (2026-07-05 triple-agent quota crash "
            f"vaccine). This is unrouted dispatch {count} in the current window.",
            "</dispatch-routing-reminder>",
        ]
    )


def _deny_reason(count: int, max_unrouted: int, window_seconds: int) -> str:
    return (
        f"Blocked by dispatch-guard: this is unrouted full-tier sub-agent dispatch "
        f"#{count} within {window_seconds}s (limit {max_unrouted - 1} before deny) — "
        "the exact batch pattern that killed 3 concurrent prototype agents on the "
        "session quota (2026-07-05). Fix one of: (a) add `subagent_type` so the agent "
        "definition's pinned model applies, (b) set an explicit lower-tier `model` for "
        "bounded/mechanical work, (c) stagger the batch. Escape hatches: include "
        "'[break-glass]:' in the dispatch prompt, or set TRELLIS_HOOKS=0."
    )


def _emit(output: dict) -> None:
    print(json.dumps(output, ensure_ascii=False))


def main() -> int:
    if (
        os.environ.get("TRELLIS_HOOKS") == "0"
        or os.environ.get("TRELLIS_DISABLE_HOOKS") == "1"
    ):
        return 0

    try:
        data = json.load(sys.stdin)
    except (json.JSONDecodeError, ValueError):
        return 0

    tool_name = (data.get("tool_name") or data.get("toolName") or "").lower()
    if tool_name not in _DISPATCH_TOOL_NAMES:
        return 0

    tool_input = data.get("tool_input") or {}
    if not isinstance(tool_input, dict):
        return 0

    # Routed dispatches are exempt: a typed agent carries its own pinned model,
    # and an explicit model override is a deliberate routing choice. Pinless
    # generic types (claude / general-purpose) don't count as routed — their
    # type carries no model.
    subagent_type = _extract_subagent_type(tool_input)
    if _string_value(tool_input.get("model")):
        return 0
    if subagent_type and subagent_type.lower() not in _PINLESS_TYPES:
        return 0

    window_seconds = _env_int("TRELLIS_DISPATCH_GUARD_WINDOW", DEFAULT_WINDOW_SECONDS)
    max_unrouted = _env_int("TRELLIS_DISPATCH_GUARD_MAX", DEFAULT_MAX_UNROUTED)

    cwd = data.get("cwd")
    repo_root = _find_repo_root(cwd if isinstance(cwd, str) and cwd else os.getcwd())
    session_id = str(data.get("session_id") or "no-session")
    state_file = _state_path(repo_root, session_id) if repo_root else None

    count = _count_in_window(state_file, window_seconds) + 1

    prompt = tool_input.get("prompt")
    break_glass = isinstance(prompt, str) and "[break-glass]:" in prompt

    if count >= max_unrouted and not break_glass:
        # Denied dispatches are not recorded: they did not execute, and a
        # corrected retry (typed / model-pinned) is exempt anyway.
        _record_metric(repo_root, "deny", ["unrouted-batch"])
        _emit(
            {
                "hookSpecificOutput": {
                    "hookEventName": "PreToolUse",
                    "permissionDecision": "deny",
                    "permissionDecisionReason": _deny_reason(
                        count, max_unrouted, window_seconds
                    ),
                    "additionalContext": _advisory_text(
                        count, max_unrouted, window_seconds
                    ),
                }
            }
        )
        return 0

    _record_dispatch(state_file, window_seconds)
    tier = "break-glass" if (break_glass and count >= max_unrouted) else "advisory"
    _record_metric(repo_root, tier, ["unrouted-dispatch"])
    _emit(
        {
            "hookSpecificOutput": {
                "hookEventName": "PreToolUse",
                "additionalContext": _advisory_text(count, max_unrouted, window_seconds),
            }
        }
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
