"""Regression tests for task.py create branch metadata.

Covers the fix where `base_branch` must be the repository default branch (PR
target), not whichever branch happens to be checked out at create time, and the
current work branch is recorded in `branch`.
"""

import argparse
import io
import json
import os
import subprocess
import sys
import tempfile
import unittest
from contextlib import contextmanager, redirect_stderr, redirect_stdout
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
TRELLIS_SCRIPTS = REPO_ROOT / ".trellis" / "scripts"
sys.path.insert(0, str(TRELLIS_SCRIPTS))

from common.task_store import _resolve_default_branch, cmd_create, cmd_set_strategy  # noqa: E402


@contextmanager
def chdir(path):
    previous = Path.cwd()
    os.chdir(path)
    try:
        yield
    finally:
        os.chdir(previous)


def _git(repo, *args):
    subprocess.run(["git", "-C", str(repo), *args], check=True, capture_output=True)


def _create_args(slug):
    return argparse.Namespace(
        title="metadata task",
        slug=slug,
        assignee="tester",
        priority="P2",
        description="",
        parent=None,
        package=None,
    )


def _created_task_json(repo, slug):
    matches = list((repo / ".trellis" / "tasks").glob(f"*-{slug}/task.json"))
    assert len(matches) == 1, matches
    return json.loads(matches[0].read_text(encoding="utf-8"))


def _created_task_dir(repo, slug):
    matches = list((repo / ".trellis" / "tasks").glob(f"*-{slug}"))
    assert len(matches) == 1, matches
    return matches[0]


class TaskCreateMetadataTest(unittest.TestCase):
    def _init_repo(self):
        tmp = tempfile.TemporaryDirectory()
        repo = Path(tmp.name)
        (repo / ".trellis").mkdir()
        (repo / ".trellis" / ".developer").write_text("name=tester\n", encoding="utf-8")
        _git(repo, "init")
        # Normalize the default branch to "main" regardless of the host's
        # init.defaultBranch setting.
        _git(repo, "symbolic-ref", "HEAD", "refs/heads/main")
        _git(repo, "config", "user.email", "tester@example.com")
        _git(repo, "config", "user.name", "tester")
        (repo / "README.md").write_text("x\n", encoding="utf-8")
        _git(repo, "add", "-A")
        _git(repo, "commit", "-m", "init")
        return tmp, repo

    def _run_create(self, repo, slug):
        with chdir(repo):
            with redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
                return cmd_create(_create_args(slug))

    def test_create_on_feature_branch_records_default_as_base(self):
        tmp, repo = self._init_repo()
        self.addCleanup(tmp.cleanup)
        _git(repo, "checkout", "-b", "fix/feature")

        rc = self._run_create(repo, "ac1-task")

        self.assertEqual(rc, 0)
        data = _created_task_json(repo, "ac1-task")
        self.assertEqual(data["base_branch"], "main")
        self.assertEqual(data["branch"], "fix/feature")

    def test_create_detached_head_falls_back_to_main(self):
        tmp, repo = self._init_repo()
        self.addCleanup(tmp.cleanup)
        _git(repo, "checkout", "--detach")

        rc = self._run_create(repo, "ac2-task")

        self.assertEqual(rc, 0)
        data = _created_task_json(repo, "ac2-task")
        self.assertEqual(data["base_branch"], "main")
        self.assertIsNone(data["branch"])

    def test_create_seeds_development_strategy_contract(self):
        tmp, repo = self._init_repo()
        self.addCleanup(tmp.cleanup)

        rc = self._run_create(repo, "ac3-task")

        self.assertEqual(rc, 0)
        data = _created_task_json(repo, "ac3-task")
        strategy = data["meta"]["development_strategy"]
        self.assertEqual(strategy["contract"], "explicit-selection-v1")
        self.assertIsNone(strategy["execution"])
        self.assertIsNone(strategy["git_mode"])
        self.assertEqual(strategy["development_mode"], "default")
        self.assertEqual(
            set(strategy["review_gates"]),
            {"spec_review", "code_review", "architecture_review", "merge_review"},
        )
        self.assertTrue(all(value is None for value in strategy["review_gates"].values()))
        self.assertEqual(strategy["optional_enhancements"]["grill_me"], "disabled")
        prd = (_created_task_dir(repo, "ac3-task") / "prd.md").read_text(encoding="utf-8")
        self.assertIn("## Development Strategy", prd)
        self.assertIn("Optional grill-me: `disabled`", prd)

    def test_set_strategy_updates_structured_metadata(self):
        tmp, repo = self._init_repo()
        self.addCleanup(tmp.cleanup)
        self._run_create(repo, "ac4-task")
        task_dir = _created_task_dir(repo, "ac4-task")
        args = argparse.Namespace(
            dir=str(task_dir),
            execution="subagent",
            git_mode="worktree",
            development_mode="tdd",
            spec_review="enabled",
            code_review="enabled",
            architecture_review="disabled",
            merge_review="enabled",
            grill_me="enabled",
        )

        with chdir(repo):
            with redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
                rc = cmd_set_strategy(args)

        self.assertEqual(rc, 0)
        data = _created_task_json(repo, "ac4-task")
        strategy = data["meta"]["development_strategy"]
        self.assertEqual(strategy["execution"], "subagent")
        self.assertEqual(strategy["git_mode"], "worktree")
        self.assertEqual(strategy["development_mode"], "tdd")
        self.assertEqual(strategy["review_gates"]["spec_review"], "enabled")
        self.assertEqual(strategy["review_gates"]["code_review"], "enabled")
        self.assertEqual(strategy["review_gates"]["architecture_review"], "disabled")
        self.assertEqual(strategy["review_gates"]["merge_review"], "enabled")
        self.assertEqual(strategy["optional_enhancements"]["grill_me"], "enabled")

    def test_resolve_default_branch_prefers_origin_head(self):
        tmp, repo = self._init_repo()
        self.addCleanup(tmp.cleanup)
        _git(repo, "checkout", "-b", "fix/feature")
        _git(repo, "symbolic-ref", "refs/remotes/origin/HEAD", "refs/remotes/origin/develop")

        self.assertEqual(_resolve_default_branch(repo), "develop")

    def test_resolve_default_branch_falls_back_without_origin(self):
        tmp, repo = self._init_repo()
        self.addCleanup(tmp.cleanup)

        self.assertEqual(_resolve_default_branch(repo), "main")


if __name__ == "__main__":
    unittest.main()
