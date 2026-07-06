"""Wires the git-SOP reminder hook's own test suite into the scripts test run.

The suite lives next to the hook (.claude/hooks/test_inject_git_sop_reminder.py)
and was previously never executed by CI. Discovery runs it against the .claude
copy; a parity test pins the .codex copy byte-identical so one run covers both
platforms. Run from the repo root: python3 -m unittest scripts.tests.test_git_sop_hooks
"""

import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
CLAUDE_HOOKS = REPO_ROOT / ".claude" / "hooks"
CODEX_HOOKS = REPO_ROOT / ".codex" / "hooks"


def load_tests(loader, tests, pattern):
    tests.addTests(
        loader.discover(
            str(CLAUDE_HOOKS),
            pattern="test_inject_git_sop_reminder.py",
            top_level_dir=str(CLAUDE_HOOKS),
        )
    )
    return tests


class CodexMirrorParityTest(unittest.TestCase):
    def test_codex_git_sop_files_are_byte_identical(self):
        for name in (
            "inject-git-sop-reminder.py",
            "test_inject_git_sop_reminder.py",
        ):
            self.assertEqual(
                (CLAUDE_HOOKS / name).read_bytes(),
                (CODEX_HOOKS / name).read_bytes(),
                f"{name}: .codex mirror drifted from .claude — the discovery run "
                "above only covers the .claude copy",
            )


if __name__ == "__main__":
    unittest.main()
