#!/usr/bin/env python3
"""Payload-level tests for inject-git-sop-reminder.py (two-tier deny + advisory hook).

Covers:
  - Deny tier: commit-on-protected, push-to-main, force-push, commit-bypass
  - Advisory tier: add-all, reset-hard, branch-name-invalid, etc.
  - Escape hatches: TRELLIS_HOOKS=0, TRELLIS_DISABLE_HOOKS=1, [break-glass]:
  - Fail-open: malformed stdin, rev-parse failure
  - Parsing fixes: -m stripping, -C dir, branch-name extraction with quotes/flags

Run: python3 -m unittest discover -s .claude/hooks -p 'test_*.py' -v
"""
from __future__ import annotations

import importlib.util
import json
import os
import sys
import tempfile
import unittest
from io import StringIO
from pathlib import Path
from unittest.mock import patch

# Import the hook module (filename has hyphens, so use importlib).
_HOOK_PATH = Path(__file__).parent / "inject-git-sop-reminder.py"
_spec = importlib.util.spec_from_file_location("hook", _HOOK_PATH)
hook = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(hook)


def _make_payload(command: str, cwd: str = "/fake/project") -> str:
    """Build a minimal PreToolUse Bash payload JSON string."""
    return json.dumps(
        {
            "session_id": "test-session",
            "hook_event_name": "PreToolUse",
            "tool_name": "Bash",
            "tool_input": {"command": command},
            "cwd": cwd,
        }
    )


def _run_hook(
    command: str,
    branch: str | None = "feat/test-branch",
    cwd: str = "/fake/project",
    env_overrides: dict | None = None,
) -> dict | None:
    """Run the hook's main() with mocked stdin/stdout and branch resolution.

    Returns the parsed JSON output dict, or None if no output.
    """
    payload = _make_payload(command, cwd)
    stdin_mock = StringIO(payload)
    stdout_mock = StringIO()

    env = os.environ.copy()
    # Clear kill-switches by default.
    env.pop("TRELLIS_HOOKS", None)
    env.pop("TRELLIS_DISABLE_HOOKS", None)
    if env_overrides:
        env.update(env_overrides)

    with (
        patch.object(sys, "stdin", stdin_mock),
        patch.object(sys, "stdout", stdout_mock),
        patch.dict(os.environ, env, clear=True),
        patch.object(hook, "_resolve_branch", return_value=branch),
    ):
        ret = hook.main()

    assert ret == 0, f"Hook returned non-zero: {ret}"

    output = stdout_mock.getvalue().strip()
    if not output:
        return None
    return json.loads(output)


class TestDenyTier(unittest.TestCase):
    """Deny-tier surfaces must emit permissionDecision:'deny'."""

    def test_commit_on_main_denied(self):
        result = _run_hook("git commit -m 'fix stuff'", branch="main")
        self.assertIsNotNone(result)
        hso = result["hookSpecificOutput"]
        self.assertEqual(hso["permissionDecision"], "deny")
        self.assertIn("committing directly on `main`", hso["permissionDecisionReason"])

    def test_commit_on_master_denied(self):
        result = _run_hook("git commit --amend", branch="master")
        self.assertIsNotNone(result)
        hso = result["hookSpecificOutput"]
        self.assertEqual(hso["permissionDecision"], "deny")
        self.assertIn("master", hso["permissionDecisionReason"])

    def test_commit_on_feature_branch_no_deny(self):
        result = _run_hook("git commit -m 'add feature'", branch="feat/my-feature")
        # Should be None (no advisory surfaces matched either for plain commit).
        self.assertIsNone(result)

    def test_push_on_main_denied(self):
        result = _run_hook("git push origin", branch="main")
        self.assertIsNotNone(result)
        hso = result["hookSpecificOutput"]
        self.assertEqual(hso["permissionDecision"], "deny")
        self.assertIn("pushing directly to `main`", hso["permissionDecisionReason"])

    def test_push_explicit_refspec_main_denied(self):
        result = _run_hook("git push origin main", branch="feat/other")
        self.assertIsNotNone(result)
        hso = result["hookSpecificOutput"]
        self.assertEqual(hso["permissionDecision"], "deny")
        self.assertIn("pushing directly to", hso["permissionDecisionReason"])

    def test_push_explicit_refspec_head_main_denied(self):
        result = _run_hook("git push origin HEAD:main", branch="feat/other")
        self.assertIsNotNone(result)
        hso = result["hookSpecificOutput"]
        self.assertEqual(hso["permissionDecision"], "deny")

    def test_push_explicit_nonprotected_refspec_while_on_main_no_deny(self):
        # Regression (2e225f8b): hook runs while HEAD is still on main but the
        # command pushes an explicit non-protected refspec (release branch
        # after an in-command checkout). Must not be denied as push-to-main.
        result = _run_hook("git push origin changeset-release/main", branch="main")
        hso = (result or {}).get("hookSpecificOutput", {})
        self.assertNotIn("permissionDecision", hso)

    def test_push_new_feature_refspec_while_on_main_no_deny(self):
        # `git switch -c feat/x && git push -u origin feat/x` in one command:
        # the hook sees branch=main but the push targets the new branch.
        result = _run_hook("git push -u origin feat/my-feature", branch="main")
        hso = (result or {}).get("hookSpecificOutput", {})
        self.assertNotIn("permissionDecision", hso)

    def test_bare_push_on_main_still_denied(self):
        result = _run_hook("git push", branch="main")
        self.assertIsNotNone(result)
        self.assertEqual(
            result["hookSpecificOutput"]["permissionDecision"], "deny"
        )

    def test_push_feature_branch_no_deny(self):
        result = _run_hook("git push -u origin feat/my-feature", branch="feat/my-feature")
        self.assertIsNotNone(result)
        hso = result["hookSpecificOutput"]
        # Should be advisory only (push surface), no deny.
        self.assertNotIn("permissionDecision", hso)
        self.assertIn("additionalContext", hso)

    def test_force_push_denied(self):
        result = _run_hook("git push --force origin feat/x", branch="feat/x")
        self.assertIsNotNone(result)
        hso = result["hookSpecificOutput"]
        self.assertEqual(hso["permissionDecision"], "deny")
        self.assertIn("--force", hso["permissionDecisionReason"])

    def test_force_with_lease_not_denied(self):
        result = _run_hook(
            "git push --force-with-lease origin feat/x", branch="feat/x"
        )
        self.assertIsNotNone(result)
        hso = result["hookSpecificOutput"]
        # Advisory only, no deny.
        self.assertNotIn("permissionDecision", hso)
        self.assertIn("additionalContext", hso)
        self.assertIn("force-with-lease", hso["additionalContext"])

    def test_commit_no_verify_denied(self):
        result = _run_hook("git commit --no-verify -m 'skip hooks'", branch="feat/x")
        self.assertIsNotNone(result)
        hso = result["hookSpecificOutput"]
        self.assertEqual(hso["permissionDecision"], "deny")
        self.assertIn("--no-verify", hso["permissionDecisionReason"])

    def test_commit_no_gpg_sign_denied(self):
        result = _run_hook("git commit --no-gpg-sign -m 'unsigned'", branch="feat/x")
        self.assertIsNotNone(result)
        hso = result["hookSpecificOutput"]
        self.assertEqual(hso["permissionDecision"], "deny")
        self.assertIn("--no-gpg-sign", hso["permissionDecisionReason"])


class TestEscapeHatch(unittest.TestCase):
    """Escape hatches must downgrade deny to advisory or suppress entirely."""

    def test_trellis_hooks_zero_suppresses_all(self):
        result = _run_hook(
            "git commit -m 'on main'",
            branch="main",
            env_overrides={"TRELLIS_HOOKS": "0"},
        )
        # Kill-switch suppresses everything (early return).
        self.assertIsNone(result)

    def test_trellis_disable_hooks_suppresses_all(self):
        result = _run_hook(
            "git push --force origin feat/x",
            branch="feat/x",
            env_overrides={"TRELLIS_DISABLE_HOOKS": "1"},
        )
        self.assertIsNone(result)

    def test_break_glass_downgrades_deny_to_advisory(self):
        result = _run_hook(
            'git commit -m "[break-glass]: emergency hotfix"', branch="main"
        )
        # Should NOT deny (break-glass escape), but advisory may still fire.
        if result is not None:
            hso = result["hookSpecificOutput"]
            self.assertNotEqual(
                hso.get("permissionDecision"), "deny",
                "break-glass should prevent deny"
            )

    def test_break_glass_force_push_downgrades(self):
        result = _run_hook(
            'git push --force origin feat/x  # [break-glass]: rebase cleanup',
            branch="feat/x",
        )
        if result is not None:
            hso = result["hookSpecificOutput"]
            self.assertNotEqual(hso.get("permissionDecision"), "deny")


class TestZshSafeBreakGlass(unittest.TestCase):
    """The documented zsh-safe no-op carrier must trip the escape hatch."""

    def test_noop_prefix_downgrades_deny(self):
        result = _run_hook(": '[break-glass]:'; git push origin main", branch="feat/x")
        hso = (result or {}).get("hookSpecificOutput", {})
        self.assertNotIn("permissionDecision", hso)


class TestFailOpen(unittest.TestCase):
    """Malformed input or rev-parse failure must never deny."""

    def test_malformed_stdin_silent_exit(self):
        stdin_mock = StringIO("not json at all {{{")
        stdout_mock = StringIO()

        with (
            patch.object(sys, "stdin", stdin_mock),
            patch.object(sys, "stdout", stdout_mock),
        ):
            ret = hook.main()

        self.assertEqual(ret, 0)
        self.assertEqual(stdout_mock.getvalue().strip(), "")

    def test_rev_parse_failure_no_deny(self):
        """When branch resolution fails (None), commit should not deny."""
        result = _run_hook("git commit -m 'detached head'", branch=None)
        # branch=None means we can't confirm it's protected -> fail-open.
        self.assertIsNone(result)

    def test_non_bash_tool_silent(self):
        payload = json.dumps(
            {
                "tool_name": "Read",
                "tool_input": {"file_path": "/some/file"},
                "cwd": "/fake",
            }
        )
        stdin_mock = StringIO(payload)
        stdout_mock = StringIO()

        with (
            patch.object(sys, "stdin", stdin_mock),
            patch.object(sys, "stdout", stdout_mock),
        ):
            ret = hook.main()

        self.assertEqual(ret, 0)
        self.assertEqual(stdout_mock.getvalue().strip(), "")


class TestAdvisoryTier(unittest.TestCase):
    """Advisory surfaces emit additionalContext without deny."""

    def test_git_add_dot_advisory(self):
        result = _run_hook("git add .", branch="feat/x")
        self.assertIsNotNone(result)
        hso = result["hookSpecificOutput"]
        self.assertNotIn("permissionDecision", hso)
        self.assertIn("add-all", hso["additionalContext"])

    def test_git_add_all_flag_advisory(self):
        result = _run_hook("git add -A", branch="feat/x")
        self.assertIsNotNone(result)
        hso = result["hookSpecificOutput"]
        self.assertNotIn("permissionDecision", hso)
        self.assertIn("add-all", hso["additionalContext"])

    def test_git_reset_hard_advisory(self):
        result = _run_hook("git reset --hard HEAD~1", branch="feat/x")
        self.assertIsNotNone(result)
        hso = result["hookSpecificOutput"]
        self.assertNotIn("permissionDecision", hso)
        self.assertIn("reset-hard", hso["additionalContext"])

    def test_git_branch_delete_advisory(self):
        result = _run_hook("git branch -D old-branch", branch="feat/x")
        self.assertIsNotNone(result)
        hso = result["hookSpecificOutput"]
        self.assertNotIn("permissionDecision", hso)
        self.assertIn("branch-delete", hso["additionalContext"])

    def test_gh_pr_merge_advisory(self):
        result = _run_hook("gh pr merge 42 --squash", branch="feat/x")
        self.assertIsNotNone(result)
        hso = result["hookSpecificOutput"]
        self.assertNotIn("permissionDecision", hso)
        self.assertIn("pr-merge", hso["additionalContext"])


class TestMessageStripping(unittest.TestCase):
    """Commit message bodies must not self-trigger advisory patterns."""

    def test_commit_message_with_git_add_dot_no_advisory(self):
        """A commit message containing 'git add .' should NOT trigger add-all."""
        result = _run_hook(
            'git commit -m "refactored git add . handling"', branch="feat/x"
        )
        # No advisory should fire (the only git-related text is inside -m).
        self.assertIsNone(result)

    def test_commit_message_with_force_push_no_advisory(self):
        result = _run_hook(
            "git commit -m 'discussed git push --force policy'", branch="feat/x"
        )
        self.assertIsNone(result)

    def test_commit_message_single_quotes_stripped(self):
        result = _run_hook(
            "git commit -m 'git reset --hard is dangerous'", branch="feat/x"
        )
        self.assertIsNone(result)

    def test_commit_F_file_stripped(self):
        result = _run_hook("git commit -F /tmp/msg.txt", branch="feat/x")
        # -F argument stripped; no advisory surfaces in the remaining command.
        self.assertIsNone(result)


class TestGitCParsing(unittest.TestCase):
    """git -C <dir> must be used for branch resolution."""

    def test_git_c_dir_used_for_resolve(self):
        """When git -C /other/dir is present, _resolve_git_dir returns that dir."""
        cmd = "git -C /other/dir commit -m 'test'"
        git_dir = hook._resolve_git_dir(cmd, "/default/cwd")
        self.assertEqual(git_dir, "/other/dir")

    def test_git_c_quoted_dir(self):
        cmd = 'git -C "/path with spaces" status'
        git_dir = hook._resolve_git_dir(cmd, "/default")
        self.assertEqual(git_dir, "/path with spaces")

    def test_no_c_falls_back_to_payload_cwd(self):
        cmd = "git commit -m 'test'"
        git_dir = hook._resolve_git_dir(cmd, "/payload/cwd")
        self.assertEqual(git_dir, "/payload/cwd")

    def test_c_dir_commit_on_main_denied(self):
        """git -C /other commit on main should deny (branch resolved via /other)."""
        # We mock _resolve_branch to return "main" regardless, simulating
        # that /other/dir is on main.
        result = _run_hook("git -C /other/dir commit -m 'test'", branch="main")
        self.assertIsNotNone(result)
        hso = result["hookSpecificOutput"]
        self.assertEqual(hso["permissionDecision"], "deny")


class TestBranchNameValidation(unittest.TestCase):
    """Branch-name extraction and validation."""

    def test_valid_branch_name_no_warning(self):
        result = _run_hook("git checkout -b feat/good-name", branch="feat/x")
        self.assertIsNotNone(result)
        hso = result["hookSpecificOutput"]
        # Should have branch-create advisory but NOT branch-name-invalid.
        self.assertIn("branch-create", hso["additionalContext"])
        self.assertNotIn("branch-name-invalid", hso["additionalContext"])

    def test_invalid_branch_name_warning(self):
        result = _run_hook("git checkout -b badname", branch="feat/x")
        self.assertIsNotNone(result)
        hso = result["hookSpecificOutput"]
        self.assertIn("branch-name-invalid", hso["additionalContext"])

    def test_branch_name_with_quotes_stripped(self):
        result = _run_hook('git checkout -b "feat/quoted-name"', branch="feat/x")
        self.assertIsNotNone(result)
        hso = result["hookSpecificOutput"]
        # Valid name inside quotes should NOT trigger invalid warning.
        self.assertNotIn("branch-name-invalid", hso["additionalContext"])

    def test_branch_name_with_flag_before_name(self):
        """Flags like -f between -b and the name should be skipped."""
        result = _run_hook("git checkout -b -f feat/forced-name", branch="feat/x")
        self.assertIsNotNone(result)
        hso = result["hookSpecificOutput"]
        self.assertNotIn("branch-name-invalid", hso["additionalContext"])

    def test_switch_c_valid_name(self):
        result = _run_hook("git switch -c fix/some-bug", branch="feat/x")
        self.assertIsNotNone(result)
        hso = result["hookSpecificOutput"]
        self.assertNotIn("branch-name-invalid", hso["additionalContext"])


class TestDenyWithAdvisory(unittest.TestCase):
    """Deny output must also include additionalContext when advisory surfaces match."""

    def test_force_push_has_advisory_context(self):
        result = _run_hook("git push --force origin feat/x", branch="feat/x")
        self.assertIsNotNone(result)
        hso = result["hookSpecificOutput"]
        self.assertEqual(hso["permissionDecision"], "deny")
        # Advisory context should also be present.
        self.assertIn("additionalContext", hso)
        self.assertIn("<git-sop-reminder>", hso["additionalContext"])

    def test_commit_on_main_has_advisory_context(self):
        result = _run_hook("git commit -m 'oops'", branch="main")
        self.assertIsNotNone(result)
        hso = result["hookSpecificOutput"]
        self.assertEqual(hso["permissionDecision"], "deny")
        self.assertIn("additionalContext", hso)
        self.assertIn("commit-on-protected", hso["additionalContext"])


class TestMergeUnfinalizedTaskGate(unittest.TestCase):
    """`gh pr merge` is denied on a branch with an unfinalized Trellis task."""

    def test_merge_denied_when_unfinalized(self):
        with patch.object(
            hook,
            "_unfinalized_task_for_branch",
            return_value="my-task (status=in_progress)",
        ):
            result = _run_hook("gh pr merge 1 --squash", branch="fix/my-task")
        self.assertIsNotNone(result)
        hso = result["hookSpecificOutput"]
        self.assertEqual(hso["permissionDecision"], "deny")
        self.assertIn("unfinalized Trellis task", hso["permissionDecisionReason"])
        self.assertIn("/trellis:ship", hso["permissionDecisionReason"])

    def test_merge_allowed_when_no_task(self):
        with patch.object(hook, "_unfinalized_task_for_branch", return_value=None):
            result = _run_hook("gh pr merge 1 --squash", branch="fix/my-task")
        # Advisory-only (pr-merge reminder) is fine; a deny is not.
        if result is not None:
            self.assertNotEqual(
                result["hookSpecificOutput"].get("permissionDecision"), "deny"
            )

    def test_merge_breakglass_downgrades(self):
        with patch.object(
            hook,
            "_unfinalized_task_for_branch",
            return_value="my-task (status=in_progress)",
        ):
            result = _run_hook(
                "[break-glass]: gh pr merge 1 --squash", branch="fix/my-task"
            )
        if result is not None:
            self.assertNotEqual(
                result["hookSpecificOutput"].get("permissionDecision"), "deny"
            )

    def test_trellis_ship_merge_not_denied(self):
        with patch.object(
            hook,
            "_unfinalized_task_for_branch",
            return_value="my-task (status=in_progress)",
        ):
            result = _run_hook(
                "python3 ./scripts/trellis_ship.py merge --number 1",
                branch="fix/my-task",
            )
        # trellis_ship.py merge is not `gh pr merge` -> never denied.
        if result is not None:
            self.assertNotEqual(
                result["hookSpecificOutput"].get("permissionDecision"), "deny"
            )


class TestUnfinalizedTaskScan(unittest.TestCase):
    """Branch-based scan of `.trellis/tasks` for an unfinalized task."""

    @staticmethod
    def _write_task(tmp: str, rel: str, data: dict) -> None:
        path = Path(tmp) / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(data), encoding="utf-8")

    def test_matches_unfinalized(self):
        with tempfile.TemporaryDirectory() as tmp:
            self._write_task(
                tmp,
                ".trellis/tasks/t1/task.json",
                {"name": "t1", "branch": "fix/x", "status": "in_progress"},
            )
            with patch.object(hook, "_repo_root", return_value=Path(tmp)):
                got = hook._unfinalized_task_for_branch(tmp, "fix/x")
        self.assertIsNotNone(got)
        self.assertIn("t1", got)
        self.assertIn("in_progress", got)

    def test_ignores_planning_coordination_parent(self):
        # Regression (2e225f8b): planning-state coordination parents live on
        # main for their whole multi-child lifetime and must not block
        # unrelated merges (e.g. release-bot PRs).
        with tempfile.TemporaryDirectory() as tmp:
            self._write_task(
                tmp,
                ".trellis/tasks/parent/task.json",
                {"name": "parent", "branch": "main", "status": "planning"},
            )
            with patch.object(hook, "_repo_root", return_value=Path(tmp)):
                self.assertIsNone(hook._unfinalized_task_for_branch(tmp, "main"))

    def test_ignores_completed(self):
        with tempfile.TemporaryDirectory() as tmp:
            self._write_task(
                tmp,
                ".trellis/tasks/t1/task.json",
                {"name": "t1", "branch": "fix/x", "status": "completed"},
            )
            with patch.object(hook, "_repo_root", return_value=Path(tmp)):
                self.assertIsNone(hook._unfinalized_task_for_branch(tmp, "fix/x"))

    def test_ignores_archived(self):
        with tempfile.TemporaryDirectory() as tmp:
            self._write_task(
                tmp,
                ".trellis/tasks/archive/2026-07/t1/task.json",
                {"name": "t1", "branch": "fix/x", "status": "in_progress"},
            )
            with patch.object(hook, "_repo_root", return_value=Path(tmp)):
                self.assertIsNone(hook._unfinalized_task_for_branch(tmp, "fix/x"))

    def test_ignores_other_branch(self):
        with tempfile.TemporaryDirectory() as tmp:
            self._write_task(
                tmp,
                ".trellis/tasks/t1/task.json",
                {"name": "t1", "branch": "fix/other", "status": "in_progress"},
            )
            with patch.object(hook, "_repo_root", return_value=Path(tmp)):
                self.assertIsNone(hook._unfinalized_task_for_branch(tmp, "fix/x"))

    def test_failopen_no_trellis(self):
        with tempfile.TemporaryDirectory() as tmp:
            with patch.object(hook, "_repo_root", return_value=Path(tmp)):
                self.assertIsNone(hook._unfinalized_task_for_branch(tmp, "fix/x"))

    def test_failopen_no_branch(self):
        self.assertIsNone(hook._unfinalized_task_for_branch("/x", None))


if __name__ == "__main__":
    unittest.main()
