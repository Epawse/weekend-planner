import json
import tempfile
import unittest
from pathlib import Path

from scripts import install_trellis_commands
from scripts import trellis_ship


ROLLUP_SUCCESS = [
    {"__typename": "CheckRun", "status": "COMPLETED", "conclusion": "SUCCESS"},
    {"__typename": "StatusContext", "state": "SUCCESS"},
]

ROLLUP_PENDING = [
    {"__typename": "CheckRun", "status": "IN_PROGRESS", "conclusion": ""},
    {"__typename": "CheckRun", "status": "COMPLETED", "conclusion": "SUCCESS"},
]

ROLLUP_FAILURE = [
    {
        "__typename": "CheckRun",
        "name": "Fast Test Suite",
        "status": "COMPLETED",
        "conclusion": "FAILURE",
    },
    {
        "__typename": "CheckRun",
        "name": "Lint",
        "status": "IN_PROGRESS",
        "conclusion": "",
    },
]

PULL_READY = json.dumps(
    {
        "number": 169,
        "state": "OPEN",
        "title": "chore(ai-platform): adopt trellis adapters",
        "baseRefName": "main",
        "headRefName": "feat/prelaunch2-split-work",
        "headRefOid": "42835bdc01c8cc51e1d5a9db4c57c0620828b4dc",
        "isDraft": False,
        "mergeable": "MERGEABLE",
        "mergeStateStatus": "CLEAN",
    }
)


class TrellisShipTest(unittest.TestCase):
    def test_aggregate_ci_state_success(self):
        self.assertEqual(trellis_ship.aggregate_ci_state(ROLLUP_SUCCESS), "success")

    def test_aggregate_ci_state_pending(self):
        self.assertEqual(trellis_ship.aggregate_ci_state(ROLLUP_PENDING), "pending")

    def test_aggregate_ci_state_failure_wins_over_pending(self):
        self.assertEqual(trellis_ship.aggregate_ci_state(ROLLUP_FAILURE), "failure")

    def test_aggregate_ci_state_empty_rollup_is_success(self):
        self.assertEqual(trellis_ship.aggregate_ci_state([]), "success")

    def test_parse_ci_statuses_and_blockers(self):
        statuses = trellis_ship.parse_ci_statuses(ROLLUP_FAILURE)

        self.assertEqual([status.state for status in statuses], ["failure", "pending"])
        self.assertEqual(statuses[0].context, "Fast Test Suite")
        blockers = trellis_ship.format_ci_blockers(statuses)
        self.assertIn("failure:Fast Test Suite", blockers)
        self.assertIn("pending", blockers)

    def test_format_ci_blockers_all_green(self):
        statuses = trellis_ship.parse_ci_statuses(ROLLUP_SUCCESS)

        self.assertIn("all parsed contexts", trellis_ship.format_ci_blockers(statuses))

    def test_build_create_pull_command_uses_body_file(self):
        command = trellis_ship.build_create_pull_command(
            "owner/repo",
            base="main",
            head="feat/x",
            title="feat(x): add y",
            body_file="/tmp/pr-body.md",
        )

        self.assertIn("--draft", command)
        self.assertIn("--body-file", command)
        self.assertNotIn("@/tmp/pr-body.md", command)

    def test_build_edit_pull_command_optional_fields(self):
        command = trellis_ship.build_edit_pull_command(
            "owner/repo", number="169", body_file="/tmp/pr-body.md"
        )

        self.assertIn("edit", command)
        self.assertIn("--body-file", command)
        self.assertNotIn("--title", command)

    def test_build_ci_diagnostic_commands(self):
        checks = trellis_ship.build_ci_checks_command("169", "owner/repo")
        logs = trellis_ship.build_ci_logs_command("12345")

        self.assertEqual(checks[:3], ["gh", "pr", "checks"])
        self.assertIn("--repo", checks)
        self.assertEqual(logs, ["gh", "run", "view", "12345", "--log-failed"])

    def test_evaluate_preflight_accepts_clean_feature_branch(self):
        errors = trellis_ship.evaluate_preflight(
            branch="chore/ship-command",
            dirty_paths=[],
            ahead_count=1,
            task_branch="chore/ship-command",
            task_base_branch="main",
            expected_base="main",
        )

        self.assertEqual(errors, [])

    def test_evaluate_preflight_accepts_finalized_task_evidence(self):
        errors = trellis_ship.evaluate_preflight(
            branch="chore/codex-parity",
            dirty_paths=[],
            ahead_count=1,
            task_branch=None,
            task_base_branch=None,
            expected_base="main",
            finalized_task=trellis_ship.FinalizedTaskEvidence(
                task_path=Path(".trellis/tasks/archive/2026-06/06-11-example"),
                branch="chore/codex-parity",
                base_branch="main",
            ),
        )

        self.assertEqual(errors, [])

    def test_evaluate_preflight_does_not_fallback_when_active_task_is_malformed(self):
        errors = trellis_ship.evaluate_preflight(
            branch="chore/codex-parity",
            dirty_paths=[],
            ahead_count=1,
            task_branch=None,
            task_base_branch="main",
            expected_base="main",
            task_present=True,
            finalized_task=trellis_ship.FinalizedTaskEvidence(
                task_path=Path(".trellis/tasks/archive/2026-06/06-11-example"),
                branch="chore/codex-parity",
                base_branch="main",
            ),
        )

        self.assertTrue(any("活动任务未记录 branch" in error for error in errors))

    def test_evaluate_preflight_rejects_missing_task_context(self):
        errors = trellis_ship.evaluate_preflight(
            branch="chore/codex-parity",
            dirty_paths=[],
            ahead_count=1,
            task_branch=None,
            task_base_branch=None,
            expected_base="main",
        )

        self.assertTrue(any("没有活动 Trellis task" in error for error in errors))

    def test_evaluate_preflight_rejects_shared_branch(self):
        errors = trellis_ship.evaluate_preflight(
            branch="main",
            dirty_paths=[],
            ahead_count=1,
            task_branch="main",
            task_base_branch="main",
            expected_base="main",
        )

        self.assertTrue(any("共享基线" in error for error in errors))

    def test_evaluate_preflight_accepts_hotfix_branch_type(self):
        errors = trellis_ship.evaluate_preflight(
            branch="hotfix/login-redirect",
            dirty_paths=[],
            ahead_count=1,
            task_branch="hotfix/login-redirect",
            task_base_branch="main",
            expected_base="main",
        )

        self.assertEqual(errors, [])

    def test_evaluate_preflight_rejects_task_branch_mismatch(self):
        errors = trellis_ship.evaluate_preflight(
            branch="chore/ship-command",
            dirty_paths=[],
            ahead_count=1,
            task_branch="chore/other",
            task_base_branch="main",
            expected_base="main",
        )

        self.assertTrue(any("不一致" in error for error in errors))

    def test_load_finalized_task_evidence_uses_diffed_archive_task(self):
        original_git_stdout = trellis_ship.git_stdout

        with tempfile.TemporaryDirectory() as tmp_dir:
            repo_root = Path(tmp_dir)
            task_dir = repo_root / ".trellis/tasks/archive/2026-06/06-11-example"
            task_dir.mkdir(parents=True)
            (task_dir / "task.json").write_text(
                json.dumps(
                    {
                        "status": "completed",
                        "branch": "chore/codex-parity",
                        "base_branch": "main",
                    }
                ),
                encoding="utf-8",
            )

            def fake_git_stdout(_repo_root, args):
                if args == [
                    "diff",
                    "--name-only",
                    "origin/main...HEAD",
                    "--",
                    ".trellis/tasks/archive",
                ]:
                    return ".trellis/tasks/archive/2026-06/06-11-example/task.json\n"
                return ""

            try:
                trellis_ship.git_stdout = fake_git_stdout

                evidence = trellis_ship.load_finalized_task_evidence(
                    repo_root,
                    branch="chore/codex-parity",
                    expected_base="main",
                )
                missing = trellis_ship.load_finalized_task_evidence(
                    repo_root,
                    branch="chore/unrelated",
                    expected_base="main",
                )
            finally:
                trellis_ship.git_stdout = original_git_stdout

        self.assertIsNotNone(evidence)
        self.assertEqual(evidence.task_path, task_dir)
        self.assertIsNone(missing)

    def test_parse_pull_info(self):
        info = trellis_ship.parse_pull_info(PULL_READY)

        self.assertEqual(info.number, "169")
        self.assertEqual(info.state, "OPEN")
        self.assertEqual(info.base_ref, "main")
        self.assertEqual(info.head_ref, "feat/prelaunch2-split-work")
        self.assertEqual(info.head_sha, "42835bdc01c8cc51e1d5a9db4c57c0620828b4dc")
        self.assertEqual(info.mergeable, "MERGEABLE")
        self.assertFalse(info.is_draft)
        self.assertEqual(info.merge_state_status, "CLEAN")

    def test_validate_pull_ready_accepts_ready_pull(self):
        info = trellis_ship.parse_pull_info(PULL_READY)

        self.assertEqual(trellis_ship.validate_pull_ready(info, expected_base="main"), [])

    def test_validate_pull_ready_rejects_conflicting_pull(self):
        info = trellis_ship.parse_pull_info(
            PULL_READY.replace('"MERGEABLE"', '"CONFLICTING"')
        )

        errors = trellis_ship.validate_pull_ready(info, expected_base="main")

        self.assertTrue(any("不可合并" in error for error in errors))

    def test_validate_pull_ready_rejects_draft_pull(self):
        info = trellis_ship.parse_pull_info(PULL_READY.replace("false", "true"))

        errors = trellis_ship.validate_pull_ready(info, expected_base="main")

        self.assertTrue(any("Draft" in error for error in errors))

    def test_build_merge_command_forces_squash(self):
        command = trellis_ship.build_merge_command("owner/repo", "169", "chore: test")

        self.assertIn("--squash", command)
        self.assertIn("--subject", command)
        self.assertNotIn("--rebase", command)
        self.assertNotIn("--merge", command)
        self.assertNotIn("--delete-branch", command)

    def test_validate_local_merge_ready_blocks_active_task(self):
        original_run_command = trellis_ship.run_command
        original_git_stdout = trellis_ship.git_stdout

        def fake_git_stdout(_repo_root, args):
            if args == ["status", "--porcelain"]:
                return ""
            if args == ["rev-list", "--count", "@{u}..HEAD"]:
                return "0"
            return ""

        def fake_run_command(args, cwd=None):
            if args == ["python3", ".trellis/scripts/task.py", "current"]:
                return trellis_ship.CommandResult(0, ".trellis/tasks/06-11-ship-command\n", "")
            return trellis_ship.CommandResult(0, "", "")

        try:
            trellis_ship.git_stdout = fake_git_stdout
            trellis_ship.run_command = fake_run_command

            errors = trellis_ship.validate_local_merge_ready(Path("."))
        finally:
            trellis_ship.git_stdout = original_git_stdout
            trellis_ship.run_command = original_run_command

        self.assertTrue(any("活动 Trellis task" in error for error in errors))


class InstallTrellisCommandsTest(unittest.TestCase):
    def test_render_claude_command_path(self):
        rendered = install_trellis_commands.render_command("ship", "# Ship\n", "claude")

        self.assertEqual(str(rendered.path), ".claude/commands/trellis/ship.md")
        self.assertEqual(rendered.content, "# Ship\n")

    def test_render_codex_command_as_skill(self):
        rendered = install_trellis_commands.render_command("ship", "# Ship\n", "codex")

        self.assertEqual(str(rendered.path), ".agents/skills/trellis-ship/SKILL.md")
        self.assertIn("name: trellis-ship", rendered.content)
        self.assertIn("/trellis:ship", rendered.content)
        self.assertIn("# Ship", rendered.content)

    def test_parse_platforms(self):
        self.assertEqual(
            install_trellis_commands.parse_platforms("all"),
            ["claude", "codex"],
        )
        self.assertEqual(
            install_trellis_commands.parse_platforms("claude,codex"),
            ["claude", "codex"],
        )

    def test_committed_adapters_match_canonical_source(self):
        source = Path(".trellis/commands/ship.md").read_text(encoding="utf-8")

        for platform in install_trellis_commands.SUPPORTED_PLATFORMS:
            rendered = install_trellis_commands.render_command("ship", source, platform)
            actual = Path(rendered.path).read_text(encoding="utf-8")
            self.assertEqual(actual, rendered.content, f"{rendered.path} is out of sync")


if __name__ == "__main__":
    unittest.main()
