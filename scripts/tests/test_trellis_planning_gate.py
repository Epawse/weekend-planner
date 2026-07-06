import argparse
import io
import json
import os
import sys
import tempfile
import unittest
from contextlib import contextmanager, redirect_stderr, redirect_stdout
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
TRELLIS_SCRIPTS = REPO_ROOT / ".trellis" / "scripts"
sys.path.insert(0, str(TRELLIS_SCRIPTS))

from common.planning_gate import evaluate_planning_gate, format_planning_gate_result  # noqa: E402
from common.task_context import cmd_validate  # noqa: E402
import task as trellis_task  # noqa: E402

DEFAULT_STRATEGY = {
    "contract": "explicit-selection-v1",
    "execution": "current-session",
    "git_mode": "branch",
    "development_mode": "default",
    "review_gates": {
        "spec_review": "disabled",
        "code_review": "enabled",
        "architecture_review": "disabled",
        "merge_review": "enabled",
    },
    "optional_enhancements": {"grill_me": "disabled"},
}


@contextmanager
def chdir(path):
    previous = Path.cwd()
    os.chdir(path)
    try:
        yield
    finally:
        os.chdir(previous)


class TrellisPlanningGateTest(unittest.TestCase):
    def make_task(self, priority="P1", title="CI workflow task", artifacts=(), research=False, strategy=True):
        tmp = tempfile.TemporaryDirectory()
        repo_root = Path(tmp.name)
        task_dir = repo_root / ".trellis" / "tasks" / "06-12-example"
        task_dir.mkdir(parents=True)
        (repo_root / ".trellis" / ".developer").write_text("name=tester\n", encoding="utf-8")
        task_data = {
            "id": "example",
            "name": "example",
            "title": title,
            "status": "planning",
            "priority": priority,
            "branch": "chore/example",
            "base_branch": "main",
        }
        if strategy:
            task_data["meta"] = {"development_strategy": DEFAULT_STRATEGY}
        (task_dir / "task.json").write_text(
            json.dumps(task_data),
            encoding="utf-8",
        )
        for artifact in artifacts:
            (task_dir / artifact).write_text(f"# {artifact}\n\nCI ship workflow.\n", encoding="utf-8")
        if research:
            research_dir = task_dir / "research"
            research_dir.mkdir()
            (research_dir / "evidence.md").write_text("# Evidence\n", encoding="utf-8")
        return tmp, repo_root, task_dir

    def test_p1_platform_task_requires_core_artifacts_and_research(self):
        tmp, _repo_root, task_dir = self.make_task(artifacts=("prd.md",))
        self.addCleanup(tmp.cleanup)

        result = evaluate_planning_gate(task_dir)

        self.assertFalse(result.ok)
        self.assertIn("design.md", result.missing)
        self.assertIn("implement.md", result.missing)
        self.assertIn("research/*.md", result.missing)

    def test_p1_platform_task_accepts_complete_planning_artifacts(self):
        tmp, _repo_root, task_dir = self.make_task(
            artifacts=("prd.md", "design.md", "implement.md"),
            research=True,
        )
        self.addCleanup(tmp.cleanup)

        result = evaluate_planning_gate(task_dir)

        self.assertTrue(result.ok)
        self.assertEqual(result.missing, ())

    def test_p1_non_platform_task_does_not_match_ci_inside_words(self):
        tmp, _repo_root, task_dir = self.make_task(
            title="product resizing task",
            artifacts=("prd.md", "design.md", "implement.md"),
        )
        self.addCleanup(tmp.cleanup)
        (task_dir / "prd.md").write_text(
            "# PRD\n\nAdd a specific resizing behavior with precise acceptance notes.\n",
            encoding="utf-8",
        )
        (task_dir / "design.md").write_text(
            "# Design\n\nThis is a product service behavior change.\n",
            encoding="utf-8",
        )
        (task_dir / "implement.md").write_text("# Implement\n\n- Code\n", encoding="utf-8")

        result = evaluate_planning_gate(task_dir)

        self.assertTrue(result.ok)
        self.assertFalse(result.requires_research)

    def test_p2_lightweight_task_allows_prd_only(self):
        tmp, _repo_root, task_dir = self.make_task(
            priority="P2",
            title="tiny docs task",
            artifacts=("prd.md",),
        )
        self.addCleanup(tmp.cleanup)

        result = evaluate_planning_gate(task_dir)

        self.assertTrue(result.ok)

    def test_missing_development_strategy_blocks_start_for_any_priority(self):
        tmp, _repo_root, task_dir = self.make_task(
            priority="P2",
            title="tiny docs task",
            artifacts=("prd.md",),
            strategy=False,
        )
        self.addCleanup(tmp.cleanup)

        result = evaluate_planning_gate(task_dir)

        self.assertFalse(result.ok)
        self.assertIn("Development Strategy choices", result.missing)

    def test_research_exemption_allows_explicitly_exempt_p1_task(self):
        tmp, _repo_root, task_dir = self.make_task(
            title="CI workflow task",
            artifacts=("prd.md", "design.md", "implement.md"),
        )
        self.addCleanup(tmp.cleanup)
        (task_dir / "prd.md").write_text(
            "# PRD\n\nresearch-exempt: no external research needed.\n",
            encoding="utf-8",
        )

        result = evaluate_planning_gate(task_dir)

        self.assertTrue(result.ok)
        self.assertTrue(result.warnings)

    def test_task_start_blocks_missing_planning_artifacts_without_status_change(self):
        tmp, repo_root, task_dir = self.make_task(artifacts=("prd.md",))
        self.addCleanup(tmp.cleanup)

        with chdir(repo_root):
            with redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
                result = trellis_task.cmd_start(argparse.Namespace(dir=str(task_dir)))

        data = json.loads((task_dir / "task.json").read_text(encoding="utf-8"))
        self.assertEqual(result, 1)
        self.assertEqual(data["status"], "planning")

    def test_validate_reports_planning_gate_failures(self):
        tmp, repo_root, task_dir = self.make_task(artifacts=("prd.md",))
        self.addCleanup(tmp.cleanup)

        with chdir(repo_root):
            with redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
                result = cmd_validate(argparse.Namespace(dir=str(task_dir)))

        self.assertEqual(result, 1)

    def test_malformed_task_json_fails_gate_without_raising(self):
        tmp, _repo_root, task_dir = self.make_task(artifacts=("prd.md",))
        self.addCleanup(tmp.cleanup)
        # task.json exists but is not valid JSON -> read_json returns None.
        (task_dir / "task.json").write_text("{ not valid json", encoding="utf-8")

        # Must return a structured failure, not raise AttributeError.
        result = evaluate_planning_gate(task_dir)

        self.assertFalse(result.ok)
        self.assertTrue(any("task.json" in item for item in result.missing))
        # Unreadable priority degrades to the P2 default rather than crashing.
        self.assertEqual(result.priority, "P2")

    # --- WIP rail (anti bulk-planning) ---

    def add_sibling(self, repo_root, name, status, children=()):
        sibling = repo_root / ".trellis" / "tasks" / name
        sibling.mkdir(parents=True)
        (sibling / "task.json").write_text(
            json.dumps({"name": name, "title": name, "status": status, "children": list(children)}),
            encoding="utf-8",
        )
        return sibling

    def make_ready_task(self):
        """A task that passes every non-WIP check (P2 + full strategy)."""
        return self.make_task(priority="P2", title="ordinary feature")

    def test_wip_blocks_start_while_another_task_in_progress(self):
        tmp, repo_root, task_dir = self.make_ready_task()
        self.addCleanup(tmp.cleanup)
        self.add_sibling(repo_root, "06-11-other", "in_progress")

        result = evaluate_planning_gate(task_dir, repo_root)

        self.assertFalse(result.ok)
        self.assertTrue(any("in_progress" in item for item in result.wip_blocked))
        # Diagnostics must not raise and must mention WIP.
        self.assertIn("WIP", format_planning_gate_result(result))

    def test_wip_blocks_when_planning_backlog_exceeds_limit(self):
        tmp, repo_root, task_dir = self.make_ready_task()
        self.addCleanup(tmp.cleanup)
        for i in range(3):
            self.add_sibling(repo_root, f"06-1{i}-parked", "planning")

        result = evaluate_planning_gate(task_dir, repo_root)

        self.assertFalse(result.ok)
        self.assertTrue(any("planning 积压" in item for item in result.wip_blocked))

    def test_wip_exempts_coordination_parent_from_planning_count(self):
        tmp, repo_root, task_dir = self.make_ready_task()
        self.addCleanup(tmp.cleanup)
        # Three planning siblings, but one is a parent holding children:
        # only two count toward the parked-planning limit.
        self.add_sibling(repo_root, "06-10-parent", "planning", children=["06-11-a"])
        self.add_sibling(repo_root, "06-11-a", "planning")
        self.add_sibling(repo_root, "06-12-b", "planning")

        result = evaluate_planning_gate(task_dir, repo_root)

        self.assertTrue(result.ok, msg=str(result))

    def test_wip_break_glass_env_downgrades_to_warning(self):
        tmp, repo_root, task_dir = self.make_ready_task()
        self.addCleanup(tmp.cleanup)
        self.add_sibling(repo_root, "06-11-other", "in_progress")

        os.environ["TRELLIS_ALLOW_PARALLEL"] = "1"
        self.addCleanup(os.environ.pop, "TRELLIS_ALLOW_PARALLEL", None)
        result = evaluate_planning_gate(task_dir, repo_root)

        self.assertTrue(result.ok)
        self.assertTrue(any("并行豁免" in item for item in result.warnings))

    def test_wip_skipped_without_repo_root(self):
        tmp, repo_root, task_dir = self.make_ready_task()
        self.addCleanup(tmp.cleanup)
        self.add_sibling(repo_root, "06-11-other", "in_progress")

        result = evaluate_planning_gate(task_dir)

        self.assertTrue(result.ok)


if __name__ == "__main__":
    unittest.main()
