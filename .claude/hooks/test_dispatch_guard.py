#!/usr/bin/env python3
"""Payload-level tests for dispatch-guard.py (advisory + batch-deny hook).

Covers:
  - Exempt: typed dispatch (subagent_type), explicit model, non-dispatch tools
  - Advisory tier: unrouted dispatch below the batch threshold
  - Deny tier: Nth unrouted dispatch within the rolling window
  - Escape hatches: TRELLIS_HOOKS=0, TRELLIS_DISABLE_HOOKS=1, [break-glass]:
  - Fail-open: malformed stdin, no repo root
  - Window expiry: old timestamps do not count toward the batch

Run: python3 -m unittest discover -s .claude/hooks -p 'test_*.py' -v
"""
from __future__ import annotations

import importlib.util
import json
import os
import subprocess
import sys
import tempfile
import unittest
from io import StringIO
from pathlib import Path
from unittest.mock import patch

# Import the hook module (filename has hyphens, so use importlib).
_HOOK_PATH = Path(__file__).parent / "dispatch-guard.py"
_spec = importlib.util.spec_from_file_location("dispatch_guard", _HOOK_PATH)
guard = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(guard)


def _make_payload(
    tool_input: dict,
    tool_name: str = "Agent",
    cwd: str = "/fake/project",
    session_id: str = "test-session",
) -> str:
    return json.dumps(
        {
            "session_id": session_id,
            "hook_event_name": "PreToolUse",
            "tool_name": tool_name,
            "tool_input": tool_input,
            "cwd": cwd,
        }
    )


class DispatchGuardBase(unittest.TestCase):
    """Runs the hook main() against a temp repo with a .trellis dir."""

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.repo = Path(self._tmp.name)
        (self.repo / ".git").mkdir()
        (self.repo / ".trellis").mkdir()
        self._clean_env = {
            k: v
            for k, v in os.environ.items()
            if not k.startswith("TRELLIS_")
        }

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def run_hook(self, payload: str, env_extra: dict | None = None) -> dict | None:
        """Run main() with payload on stdin; return parsed JSON output or None."""
        env = dict(self._clean_env)
        if env_extra:
            env.update(env_extra)
        stdout = StringIO()
        with patch.dict(os.environ, env, clear=True), patch.object(
            sys, "stdin", StringIO(payload)
        ), patch.object(sys, "stdout", stdout):
            rc = guard.main()
        self.assertEqual(rc, 0)
        raw = stdout.getvalue().strip()
        return json.loads(raw) if raw else None

    def dispatch(self, tool_input: dict, **kwargs) -> dict | None:
        return self.run_hook(_make_payload(tool_input, cwd=str(self.repo), **kwargs))


class TestExemptions(DispatchGuardBase):
    def test_typed_dispatch_is_silent(self) -> None:
        out = self.dispatch({"prompt": "scan repo", "subagent_type": "trellis-research"})
        self.assertIsNone(out)

    def test_model_pinned_dispatch_is_silent(self) -> None:
        out = self.dispatch({"prompt": "scan repo", "model": "sonnet"})
        self.assertIsNone(out)

    def test_non_dispatch_tool_is_silent(self) -> None:
        out = self.run_hook(
            _make_payload({"command": "ls"}, tool_name="Bash", cwd=str(self.repo))
        )
        self.assertIsNone(out)

    def test_camel_case_type_key_is_exempt(self) -> None:
        out = self.dispatch({"prompt": "x", "subagentType": "Explore"})
        self.assertIsNone(out)

    def test_pinless_type_without_model_is_unrouted(self) -> None:
        out = self.dispatch({"prompt": "x", "subagent_type": "claude"})
        self.assertIsNotNone(out)
        self.assertIn("dispatch-routing-reminder", out["hookSpecificOutput"]["additionalContext"])

    def test_pinless_type_with_model_is_exempt(self) -> None:
        out = self.dispatch({"prompt": "x", "subagent_type": "general-purpose", "model": "sonnet"})
        self.assertIsNone(out)


class TestAdvisoryTier(DispatchGuardBase):
    def test_first_unrouted_dispatch_gets_advisory(self) -> None:
        out = self.dispatch({"prompt": "analyze the repo"})
        self.assertIsNotNone(out)
        hso = out["hookSpecificOutput"]
        self.assertNotIn("permissionDecision", hso)
        self.assertIn("dispatch-routing-reminder", hso["additionalContext"])
        self.assertIn("unrouted dispatch 1", hso["additionalContext"])

    def test_second_unrouted_dispatch_still_advisory(self) -> None:
        self.dispatch({"prompt": "a"})
        out = self.dispatch({"prompt": "b"})
        hso = out["hookSpecificOutput"]
        self.assertNotIn("permissionDecision", hso)
        self.assertIn("unrouted dispatch 2", hso["additionalContext"])


class TestDenyTier(DispatchGuardBase):
    def test_third_unrouted_dispatch_denied(self) -> None:
        self.dispatch({"prompt": "a"})
        self.dispatch({"prompt": "b"})
        out = self.dispatch({"prompt": "c"})
        hso = out["hookSpecificOutput"]
        self.assertEqual(hso["permissionDecision"], "deny")
        self.assertIn("dispatch-guard", hso["permissionDecisionReason"])

    def test_denied_dispatch_not_recorded(self) -> None:
        self.dispatch({"prompt": "a"})
        self.dispatch({"prompt": "b"})
        self.dispatch({"prompt": "c"})  # denied
        out = self.dispatch({"prompt": "d"})  # still #3 in window -> denied again
        self.assertEqual(
            out["hookSpecificOutput"]["permissionDecision"], "deny"
        )

    def test_break_glass_downgrades_deny(self) -> None:
        self.dispatch({"prompt": "a"})
        self.dispatch({"prompt": "b"})
        out = self.dispatch({"prompt": "[break-glass]: deliberate parallel run"})
        hso = out["hookSpecificOutput"]
        self.assertNotIn("permissionDecision", hso)
        self.assertIn("additionalContext", hso)

    def test_window_expiry_resets_count(self) -> None:
        self.dispatch({"prompt": "a"})
        self.dispatch({"prompt": "b"})
        state_files = list((self.repo / ".trellis" / ".runtime").glob("dispatch-guard-*.json"))
        self.assertEqual(len(state_files), 1)
        stale = [guard.time.time() - 10_000, guard.time.time() - 9_000]
        state_files[0].write_text(json.dumps(stale), encoding="utf-8")
        out = self.dispatch({"prompt": "c"})
        hso = out["hookSpecificOutput"]
        self.assertNotIn("permissionDecision", hso)
        self.assertIn("unrouted dispatch 1", hso["additionalContext"])

    def test_max_override_env(self) -> None:
        out1 = self.run_hook(
            _make_payload({"prompt": "a"}, cwd=str(self.repo)),
            env_extra={"TRELLIS_DISPATCH_GUARD_MAX": "1"},
        )
        self.assertEqual(
            out1["hookSpecificOutput"]["permissionDecision"], "deny"
        )


class TestEscapeAndFailOpen(DispatchGuardBase):
    def test_kill_switch_trellis_hooks(self) -> None:
        out = self.run_hook(
            _make_payload({"prompt": "a"}, cwd=str(self.repo)),
            env_extra={"TRELLIS_HOOKS": "0"},
        )
        self.assertIsNone(out)

    def test_kill_switch_disable_hooks(self) -> None:
        out = self.run_hook(
            _make_payload({"prompt": "a"}, cwd=str(self.repo)),
            env_extra={"TRELLIS_DISABLE_HOOKS": "1"},
        )
        self.assertIsNone(out)

    def test_malformed_stdin_fails_open(self) -> None:
        out = self.run_hook("this is not json")
        self.assertIsNone(out)

    def test_no_repo_root_still_advises_statelessly(self) -> None:
        # cwd outside any git repo: advisory still fires, no state written.
        with tempfile.TemporaryDirectory() as plain_dir:
            out = self.run_hook(_make_payload({"prompt": "a"}, cwd=plain_dir))
        self.assertIsNotNone(out)
        self.assertIn(
            "additionalContext", out["hookSpecificOutput"]
        )


class TestCliSmoke(unittest.TestCase):
    def test_cli_typed_dispatch_exits_zero_silently(self) -> None:
        proc = subprocess.run(
            [sys.executable, str(_HOOK_PATH)],
            input=_make_payload({"prompt": "x", "subagent_type": "trellis-check"}),
            capture_output=True,
            text=True,
            timeout=10,
        )
        self.assertEqual(proc.returncode, 0)
        self.assertEqual(proc.stdout.strip(), "")


if __name__ == "__main__":
    unittest.main()
