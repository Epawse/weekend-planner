#!/usr/bin/env python3
"""Mechanical hygiene scan for the trellis-review-sweep skill (segment 3).

Run from a Trellis project root. Reports, never edits — fixes are the
sweep orchestrator's call. Stdlib only.

Checks:
  * placeholder text left in task artifacts / spec / workspace
    ("(Add details)"-family, "（由团队填写）", jsonl manifests that still
    contain only the seed `_example` row on non-planning tasks)
  * development-strategy metadata gaps on non-planning tasks
  * dead repo-relative markdown links in spec / workspace memory /
    governance docs
  * deep_review ledger inventory (pending / done / waived / absent)

Output: markdown report on stdout. Exit 0 always (report, not a gate).
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

PLACEHOLDER_PATTERNS = (
    "(Add details)",
    "(Add summary)",
    "(Add test results)",
    "（由团队填写）",
)

LINK_RE = re.compile(r"\]\(([^)#\s]+)\)")

GOVERNANCE_DOC_CANDIDATES = (
    "docs/PROJECT-MEMORY.md",
    "BACKLOG.md",
    "docs/BACKLOG.md",
)


def repo_root() -> Path:
    root = Path.cwd()
    if not (root / ".trellis").is_dir():
        sys.exit("error: run from a Trellis project root (.trellis/ not found)")
    return root


def iter_task_dirs(root: Path):
    tasks = root / ".trellis" / "tasks"
    if not tasks.is_dir():
        return
    for d in sorted(tasks.iterdir()):
        if d.is_dir() and d.name != "archive" and (d / "task.json").is_file():
            yield d
    archive = tasks / "archive"
    if archive.is_dir():
        for month in sorted(archive.iterdir()):
            if not month.is_dir():
                continue
            for d in sorted(month.iterdir()):
                if d.is_dir() and (d / "task.json").is_file():
                    yield d


def load_json(path: Path) -> dict:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}


def scan_placeholders(root: Path, task_dirs: list[Path]) -> list[str]:
    warns: list[str] = []
    scopes = [root / ".trellis" / "spec", root / ".trellis" / "workspace"]
    scopes += task_dirs
    seen: set[Path] = set()
    for scope in scopes:
        if not scope.exists():
            continue
        files = [scope] if scope.is_file() else sorted(scope.rglob("*.md"))
        for f in files:
            if f in seen or not f.is_file():
                continue
            seen.add(f)
            try:
                text = f.read_text(encoding="utf-8")
            except OSError:
                continue
            hits = [p for p in PLACEHOLDER_PATTERNS if p in text]
            if hits:
                warns.append(
                    f"placeholder text in `{f.relative_to(root)}`: "
                    + ", ".join(hits)
                )
    return warns


def scan_seed_manifests(root: Path, task_dirs: list[Path]) -> list[str]:
    """Flag jsonl manifests still seed-only on tasks past planning."""
    warns: list[str] = []
    for d in task_dirs:
        data = load_json(d / "task.json")
        if data.get("status") in (None, "planning"):
            continue  # seed rows are legitimate during planning
        for name in ("implement.jsonl", "check.jsonl"):
            f = d / name
            if not f.is_file():
                continue
            real = seed = 0
            for line in f.read_text(encoding="utf-8").splitlines():
                line = line.strip()
                if not line:
                    continue
                try:
                    row = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if isinstance(row, dict) and row.get("file"):
                    real += 1
                else:
                    seed += 1
            if seed and not real:
                warns.append(
                    f"seed-only manifest on {data.get('status')} task: "
                    f"`{f.relative_to(root)}` (no real entries)"
                )
    return warns


def scan_strategy_gaps(root: Path, task_dirs: list[Path]) -> list[str]:
    warns: list[str] = []
    for d in task_dirs:
        data = load_json(d / "task.json")
        status = data.get("status")
        if status in (None, "planning"):
            continue
        strategy = (data.get("meta") or {}).get("development_strategy") or {}
        missing = [k for k in ("execution", "git_mode") if not strategy.get(k)]
        gates = strategy.get("review_gates") or {}
        missing += [f"review_gates.{k}" for k, v in gates.items() if v is None]
        if missing:
            warns.append(
                f"strategy gaps on {status} task `{d.relative_to(root)}`: "
                + ", ".join(missing)
            )
    return warns


def scan_dead_links(root: Path) -> list[str]:
    warns: list[str] = []
    targets: list[Path] = []
    spec = root / ".trellis" / "spec"
    if spec.is_dir():
        targets += sorted(spec.rglob("*.md"))
    workspace = root / ".trellis" / "workspace"
    if workspace.is_dir():
        targets += sorted(workspace.rglob("memory.md"))
    for rel in GOVERNANCE_DOC_CANDIDATES:
        f = root / rel
        if f.is_file():
            targets.append(f)
    for f in targets:
        try:
            text = f.read_text(encoding="utf-8")
        except OSError:
            continue
        for target in LINK_RE.findall(text):
            if "://" in target or target.startswith("mailto:"):
                continue
            resolved = (f.parent / target) if not target.startswith("/") else (
                root / target.lstrip("/")
            )
            if not resolved.exists():
                warns.append(
                    f"dead link in `{f.relative_to(root)}` -> `{target}`"
                )
    return warns


def ledger_inventory(task_dirs: list[Path]) -> dict:
    counts = {"pending": 0, "done": 0, "waived": 0, "absent": 0}
    for d in task_dirs:
        data = load_json(d / "task.json")
        state = ((data.get("meta") or {}).get("verification") or {}).get(
            "deep_review"
        )
        if not state:
            counts["absent"] += 1
        elif state.startswith("done"):
            counts["done"] += 1
        elif state in counts:
            counts[state] += 1
        else:
            counts["absent"] += 1
    return counts


def main() -> int:
    root = repo_root()
    task_dirs = list(iter_task_dirs(root))

    sections = [
        ("Placeholder text", scan_placeholders(root, task_dirs)),
        ("Seed-only manifests", scan_seed_manifests(root, task_dirs)),
        ("Strategy metadata gaps", scan_strategy_gaps(root, task_dirs)),
        ("Dead repo links", scan_dead_links(root)),
    ]

    total = sum(len(w) for _, w in sections)
    print("# Sweep hygiene report")
    print()
    print(f"- tasks scanned: {len(task_dirs)}")
    counts = ledger_inventory(task_dirs)
    print(
        "- deep_review ledger: "
        + ", ".join(f"{k} {v}" for k, v in counts.items())
    )
    print(f"- WARN total: {total}")
    for title, warns in sections:
        print()
        print(f"## {title} ({len(warns)})")
        for w in warns:
            print(f"- [WARN] {w}")
        if not warns:
            print("- (clean)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
