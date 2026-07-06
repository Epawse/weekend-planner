import json
import tempfile
import unittest
from pathlib import Path

from scripts import trellis_branch_report


class TrellisBranchReportTest(unittest.TestCase):
    def test_normalize_ref_skips_remote_head(self):
        self.assertEqual(
            trellis_branch_report.normalize_ref("refs/heads/chore/demo"),
            ("local", "chore/demo"),
        )
        self.assertEqual(
            trellis_branch_report.normalize_ref("refs/remotes/origin/chore/demo"),
            ("remote", "chore/demo"),
        )
        self.assertIsNone(trellis_branch_report.normalize_ref("refs/remotes/origin/HEAD"))

    def test_build_rows_links_tasks_and_classifies_cleanup(self):
        refs = trellis_branch_report.GitRefs(
            local={"main", "chore/done", "chore/current", "wip/local"},
            remote={"main", "chore/done", "chore/remote-only"},
        )
        tasks = [
            trellis_branch_report.TaskInfo(
                path=Path(".trellis/tasks/archive/2026-06/done"),
                branch="chore/done",
                base_branch="main",
                status="archived",
            ),
            trellis_branch_report.TaskInfo(
                path=Path(".trellis/tasks/06-12-current"),
                branch="chore/current",
                base_branch="main",
                status="in_progress",
            ),
        ]

        rows = {row.branch: row for row in trellis_branch_report.build_rows(refs, tasks)}

        self.assertEqual(rows["main"].cleanup, "protected")
        self.assertEqual(rows["chore/done"].cleanup, "candidate")
        self.assertEqual(rows["chore/current"].cleanup, "active-task")
        self.assertEqual(rows["chore/remote-only"].cleanup, "review")
        self.assertEqual(rows["wip/local"].cleanup, "review")
        self.assertEqual(rows["chore/done"].tasks[0].base_branch, "main")

    def test_load_tasks_marks_archive_paths_as_archived(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            repo_root = Path(tmp_dir)
            active = repo_root / ".trellis/tasks/06-12-active"
            archived = repo_root / ".trellis/tasks/archive/2026-06/done"
            active.mkdir(parents=True)
            archived.mkdir(parents=True)
            (active / "task.json").write_text(
                json.dumps({
                    "branch": "chore/current",
                    "base_branch": "main",
                    "status": "in_progress",
                }),
                encoding="utf-8",
            )
            (archived / "task.json").write_text(
                json.dumps({
                    "branch": "chore/done",
                    "base_branch": "main",
                    "status": "completed",
                }),
                encoding="utf-8",
            )

            tasks = {task.branch: task for task in trellis_branch_report.load_tasks(repo_root)}

        self.assertEqual(tasks["chore/current"].status, "in_progress")
        self.assertEqual(tasks["chore/done"].status, "archived")

    def test_render_table_contains_expected_columns(self):
        row = trellis_branch_report.BranchRow(
            branch="chore/done",
            local=True,
            remote=True,
            tasks=(
                trellis_branch_report.TaskInfo(
                    path=Path(".trellis/tasks/archive/2026-06/done"),
                    branch="chore/done",
                    base_branch="main",
                    status="archived",
                ),
            ),
            cleanup="candidate",
        )

        output = trellis_branch_report.render_table([row])

        self.assertIn("branch", output)
        self.assertIn("task_status", output)
        self.assertIn("chore/done", output)
        self.assertIn("candidate", output)


if __name__ == "__main__":
    unittest.main()
