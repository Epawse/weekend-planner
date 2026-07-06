"""Integration tests for the Claude Code session-start hook.

Focus: the shared local-setup-hints block (extracted to common.setup_hints) is
wired into Claude Code's session-start output, matching Codex behavior. Claude
Code previously had no hook test coverage.
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
CC_HOOK = REPO_ROOT / ".claude" / "hooks" / "session-start.py"
TRELLIS_SCRIPTS = REPO_ROOT / ".trellis" / "scripts"


class ClaudeSessionStartHooksTest(unittest.TestCase):
    def run_hook(self, cwd):
        # Make `common` importable regardless of the hook's internal sys.path
        # timing, so a minimal temp repo can still load common.setup_hints.
        env = {**os.environ, "PYTHONPATH": str(TRELLIS_SCRIPTS)}
        result = subprocess.run(
            [sys.executable, str(CC_HOOK)],
            cwd=str(cwd),
            input=json.dumps({"cwd": str(cwd)}),
            text=True,
            capture_output=True,
            timeout=40,
            env=env,
        )
        self.assertEqual(
            result.returncode,
            0,
            msg=f"session-start failed from {cwd}\nSTDOUT:\n{result.stdout}\nSTDERR:\n{result.stderr}",
        )
        self.assertTrue(result.stdout.strip(), f"no stdout from {cwd}")
        return json.loads(result.stdout)

    def additional_context(self, hook_output):
        return hook_output.get("hookSpecificOutput", {}).get("additionalContext", "")

    def assert_routing_hints(self, context):
        self.assertIn("<routing-hints>", context)
        self.assertIn(".trellis/spec/guides/git-pr-sop.md", context)
        self.assertIn(".trellis/commands/ship.md", context)
        self.assertIn("git fetch --prune", context)
        self.assertIn("gh pr", context)
        self.assertIn("gh api", context)
        self.assertIn("command -v gh", context)
        self.assertIn("refs/pull/*", context)
        self.assertIn("webpage curl", context)

    def _make_repo(self, tmp):
        repo = Path(tmp)
        trellis = repo / ".trellis"
        trellis.mkdir()
        shutil.copy(REPO_ROOT / ".trellis" / "workflow.md", trellis / "workflow.md")
        subprocess.run(["git", "init"], cwd=repo, check=True, capture_output=True)
        return repo

    def test_real_repo_session_start_runs(self):
        # Smoke: the hook runs end-to-end against the real repo and emits valid
        # SessionStart JSON. (Hint presence depends on local env, so not asserted.)
        output = self.run_hook(REPO_ROOT)
        self.assertEqual(output["hookSpecificOutput"]["hookEventName"], "SessionStart")
        ctx = self.additional_context(output)
        self.assertTrue(ctx.strip())
        self.assert_routing_hints(ctx)

    def test_emits_setup_hints_when_developer_and_hooks_missing(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo = self._make_repo(tmp)  # no .developer, no core.hooksPath
            ctx = self.additional_context(self.run_hook(repo))

        self.assertIn("<trellis-local-setup-hints>", ctx)
        self.assertIn("Developer identity is not initialized", ctx)
        self.assertIn("init_developer.py <name>", ctx)
        self.assertIn("Do not suggest or run `trellis init`", ctx)
        self.assertIn("Git hooks path is `(unset)`, not `.githooks`", ctx)

    def test_omits_setup_hints_when_local_state_ready(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo = self._make_repo(tmp)
            (repo / ".trellis" / ".developer").write_text("name=alice\n", encoding="utf-8")
            (repo / ".trellis" / "workspace" / "alice").mkdir(parents=True)
            subprocess.run(
                ["git", "config", "core.hooksPath", ".githooks"],
                cwd=repo,
                check=True,
                capture_output=True,
            )
            ctx = self.additional_context(self.run_hook(repo))

        self.assertNotIn("<trellis-local-setup-hints>", ctx)


if __name__ == "__main__":
    unittest.main()
