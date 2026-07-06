"""Integration tests for the base-layer context-injection hooks, both platforms.

Covers the three auto-firing prompt surfaces shipped by the base layer:
  * session-start.py         (Claude Code + Codex variants — deliberately
                              platform-specific envelopes, tested separately)
  * inject-workflow-state.py (byte-identical mirror on both platforms —
                              tested once + parity-pinned)
  * inject-subagent-context.py (platform-specific; the no-active-task gating
                              must stay silent on both)

These are the surfaces that inject into every session / every turn / every
dispatch, so a regression here is a per-turn tax or a silent loss of spec
context. Run from a rendered repo root: python3 -m unittest scripts.tests.test_base_hooks
"""

import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
TRELLIS_SCRIPTS = REPO_ROOT / ".trellis" / "scripts"


def run_hook(script, cwd, payload):
    env = {**os.environ, "PYTHONPATH": str(TRELLIS_SCRIPTS)}
    return subprocess.run(
        [sys.executable, "-X", "utf8", str(script)],
        cwd=str(cwd),
        input=json.dumps(payload),
        text=True,
        capture_output=True,
        timeout=40,
        env=env,
    )


def additional_context(stdout_text):
    if not stdout_text.strip():
        return ""
    return (
        json.loads(stdout_text)
        .get("hookSpecificOutput", {})
        .get("additionalContext", "")
    )


def make_min_repo(tmp):
    """Minimal rendered-repo fixture: workflow.md + git init, no tasks."""
    repo = Path(tmp)
    trellis = repo / ".trellis"
    trellis.mkdir()
    shutil.copy(REPO_ROOT / ".trellis" / "workflow.md", trellis / "workflow.md")
    subprocess.run(["git", "init"], cwd=repo, check=True, capture_output=True)
    return repo


class SessionStartBothPlatformsTest(unittest.TestCase):
    def test_codex_session_start_runs_from_root_and_subdir(self):
        hook = REPO_ROOT / ".codex" / "hooks" / "session-start.py"
        for cwd in (REPO_ROOT, REPO_ROOT / "scripts"):
            result = run_hook(hook, cwd, {"cwd": str(cwd)})
            self.assertEqual(result.returncode, 0, msg=result.stderr[:500])
            out = json.loads(result.stdout)
            self.assertEqual(
                out["hookSpecificOutput"]["hookEventName"], "SessionStart"
            )
            self.assertTrue(
                out["hookSpecificOutput"]["additionalContext"].strip(),
                f"empty context from {cwd}",
            )

    def test_registered_commands_noop_cleanly_outside_git_worktree(self):
        # hooks.json wraps every codex hook in a `git rev-parse || exit 0`
        # guard; the guard (not the python) is what protects non-repo cwds.
        hooks_json = json.loads((REPO_ROOT / ".codex" / "hooks.json").read_text())
        commands = [
            h["command"]
            for group in hooks_json["hooks"].values()
            for entry in group
            for h in entry["hooks"]
        ]
        self.assertTrue(commands)
        with tempfile.TemporaryDirectory() as tmp:
            for cmd in commands:
                result = subprocess.run(
                    ["bash", "-c", cmd],
                    cwd=tmp,
                    input="{}",
                    text=True,
                    capture_output=True,
                    timeout=40,
                )
                self.assertEqual(
                    result.returncode, 0, msg=f"{cmd!r} rc={result.returncode}"
                )
                self.assertFalse(
                    result.stdout.strip(),
                    f"{cmd!r} injected output outside a git worktree",
                )


class WorkflowStateBreadcrumbTest(unittest.TestCase):
    CC_HOOK = REPO_ROOT / ".claude" / "hooks" / "inject-workflow-state.py"
    CODEX_HOOK = REPO_ROOT / ".codex" / "hooks" / "inject-workflow-state.py"

    def test_mirrors_are_byte_identical(self):
        self.assertEqual(
            self.CC_HOOK.read_bytes(),
            self.CODEX_HOOK.read_bytes(),
            ".codex/hooks/inject-workflow-state.py drifted from the .claude copy",
        )

    def test_no_task_state_emits_the_no_task_breadcrumb(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo = make_min_repo(tmp)
            result = run_hook(self.CC_HOOK, repo, {"prompt": "hi", "cwd": str(repo)})
        self.assertEqual(result.returncode, 0, msg=result.stderr[:500])
        ctx = additional_context(result.stdout)
        self.assertIn("No active Trellis task", ctx)
        # per-turn tax stays bounded: the breadcrumb is a pointer, not a manual
        self.assertLess(len(ctx), 4000, "breadcrumb bloated beyond pointer size")


class SubagentContextGatingTest(unittest.TestCase):
    def test_no_active_task_stays_silent_on_both_platforms(self):
        cases = [
            (
                REPO_ROOT / ".claude" / "hooks" / "inject-subagent-context.py",
                {"tool_name": "Agent", "tool_input": {"prompt": "do a thing"}},
            ),
            (
                REPO_ROOT / ".codex" / "hooks" / "inject-subagent-context.py",
                {"tool_name": "spawn_agent", "tool_input": {"message": "do a thing"}},
            ),
        ]
        with tempfile.TemporaryDirectory() as tmp:
            repo = make_min_repo(tmp)
            for hook, payload in cases:
                payload = {**payload, "cwd": str(repo)}
                result = run_hook(hook, repo, payload)
                self.assertEqual(
                    result.returncode, 0, msg=f"{hook.name}: {result.stderr[:300]}"
                )
                self.assertFalse(
                    additional_context(result.stdout).strip(),
                    f"{hook} injected context with no active task",
                )


if __name__ == "__main__":
    unittest.main()
