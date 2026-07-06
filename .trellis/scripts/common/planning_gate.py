#!/usr/bin/env python3
"""Planning artifact gate for Trellis task activation.

The gate is intentionally small and deterministic: it checks whether required
planning files exist before high-priority tasks move from planning to
implementation. It does not judge artifact quality; humans and the workflow do
that during planning review.
"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass
from pathlib import Path

from .io import read_json
from .paths import FILE_TASK_JSON
from .tasks import iter_active_tasks


HIGH_PRIORITY = {"P0", "P1"}
REQUIRED_HIGH_PRIORITY_ARTIFACTS = ("prd.md", "design.md", "implement.md")
STRATEGY_CONTRACT = "explicit-selection-v1"
EXECUTION_VALUES = {"current-session", "subagent"}
GIT_MODE_VALUES = {"branch", "worktree"}
DEVELOPMENT_MODE_VALUES = {"default", "tdd"}
REVIEW_GATE_VALUES = {"enabled", "disabled"}
REVIEW_GATE_KEYS = ("spec_review", "code_review", "architecture_review", "merge_review")
RESEARCH_EXEMPT_MARKERS = (
    "research-exempt",
    "research exemption",
    "research not required",
    "no research required",
    "无需 research",
    "无需研究",
    "不需要 research",
    "不需要研究",
)
PLATFORM_RESEARCH_KEYWORDS = (
    "ai adapter",
    "adapter",
    "agent",
    "agents",
    "baseline",
    "ci",
    "cnb",
    "codex",
    "command",
    "commands",
    "hook",
    "hooks",
    "platform",
    "ship",
    "skill",
    "skills",
    "trellis",
    "workflow",
    ".agents",
    ".claude",
    ".cnb",
    ".codex",
    ".cursor",
    ".trellis",
    ".trellis/scripts",
)
PLATFORM_PATH_MARKERS = tuple(
    keyword for keyword in PLATFORM_RESEARCH_KEYWORDS if keyword.startswith(".")
)
PLATFORM_WORD_MARKERS = tuple(
    keyword for keyword in PLATFORM_RESEARCH_KEYWORDS if not keyword.startswith(".")
)

# WIP rail: big upfront plans route around the per-task gate — tasks 2..N live
# only in the plan's head until each is started, and their artifacts degrade.
# Enforce lazy materialization mechanically: one in_progress task at a time,
# at most WIP_PLANNING_LIMIT parked planning siblings. Coordination parents
# (tasks holding children) are exempt from the planning count — the parent's
# task map is exactly where future work is supposed to wait.
WIP_IN_PROGRESS_LIMIT = 1
WIP_PLANNING_LIMIT = 2
WIP_BREAK_GLASS_ENV = "TRELLIS_ALLOW_PARALLEL"


@dataclass(frozen=True)
class PlanningGateResult:
    ok: bool
    missing: tuple[str, ...]
    warnings: tuple[str, ...]
    priority: str
    requires_research: bool
    task_status: str | None
    wip_blocked: tuple[str, ...] = ()


def evaluate_planning_gate(task_dir: Path, repo_root: Path | None = None) -> PlanningGateResult:
    """Return planning gate status for a task directory."""
    task_dir = task_dir.resolve()
    task_json_path = task_dir / FILE_TASK_JSON
    raw = read_json(task_json_path) if task_json_path.is_file() else {}
    # read_json returns None when task.json exists but is unreadable / invalid
    # JSON. Treat that as an explicit gate failure: degrade to empty data so the
    # .get() calls below never raise AttributeError, and flag it in `missing` so
    # a corrupt task.json blocks the gate instead of silently passing as P2.
    task_json_unreadable = task_json_path.is_file() and not isinstance(raw, dict)
    data = raw if isinstance(raw, dict) else {}
    priority = str(data.get("priority") or "P2").upper()
    status = data.get("status") if isinstance(data.get("status"), str) else None

    missing: list[str] = []
    warnings: list[str] = []

    if task_json_unreadable:
        missing.append("task.json (unreadable / invalid JSON)")

    if not task_json_unreadable and _development_strategy_missing(data):
        missing.append("Development Strategy choices")

    if priority in HIGH_PRIORITY:
        for artifact in REQUIRED_HIGH_PRIORITY_ARTIFACTS:
            if not (task_dir / artifact).is_file():
                missing.append(artifact)

    requires_research = priority in HIGH_PRIORITY and _is_platform_workflow_task(
        task_dir,
        data,
    )
    if requires_research and not _has_research_artifact(task_dir):
        if _has_research_exemption(task_dir):
            warnings.append("P0/P1 平台任务已声明 research 豁免。")
        else:
            missing.append("research/*.md")

    wip_blocked: list[str] = []
    if repo_root is not None:
        wip_blocked, wip_warnings = _wip_state(task_dir, Path(repo_root))
        warnings.extend(wip_warnings)

    return PlanningGateResult(
        ok=not missing and not wip_blocked,
        missing=tuple(missing),
        warnings=tuple(warnings),
        priority=priority,
        requires_research=requires_research,
        task_status=status,
        wip_blocked=tuple(wip_blocked),
    )


def format_planning_gate_result(result: PlanningGateResult) -> str:
    """Format a short Chinese diagnostic for CLI output."""
    if result.ok:
        if result.warnings:
            return "Planning gate: 通过（" + "；".join(result.warnings) + "）"
        return "Planning gate: 通过"

    parts: list[str] = []
    if result.missing:
        parts.append("缺少：" + "、".join(result.missing))
    if result.wip_blocked:
        parts.append("WIP：" + "；".join(result.wip_blocked))
    return "Planning gate: 未通过，" + "；".join(parts)


def _wip_state(task_dir: Path, repo_root: Path) -> tuple[list[str], list[str]]:
    """Anti-bulk-planning rail. Returns (blockers, warnings).

    Break-glass: set TRELLIS_ALLOW_PARALLEL=1 to downgrade blockers to a
    recorded warning for a deliberate parallel run.
    """
    tasks_dir = repo_root / ".trellis" / "tasks"
    if not tasks_dir.is_dir():
        return [], []

    self_name = task_dir.resolve().name
    in_progress: list[str] = []
    parked_planning: list[str] = []
    for info in iter_active_tasks(tasks_dir):
        if info.dir_name == self_name:
            continue
        raw = info.raw if isinstance(info.raw, dict) else {}
        has_children = bool(info.children or raw.get("subtasks"))
        if info.status == "in_progress":
            in_progress.append(info.dir_name)
        elif info.status == "planning" and not has_children:
            parked_planning.append(info.dir_name)

    blockers: list[str] = []
    if len(in_progress) >= WIP_IN_PROGRESS_LIMIT:
        blockers.append(
            f"{len(in_progress)} 个任务仍 in_progress（{'、'.join(in_progress[:3])}）"
            "——先 task.py finish/archive 收尾当前任务再 start 新任务"
        )
    if len(parked_planning) > WIP_PLANNING_LIMIT:
        blockers.append(
            f"planning 积压 {len(parked_planning)} 个（上限 {WIP_PLANNING_LIMIT}）"
            "——未拾取的收回 parent 任务地图（prd/implement.md 一行一个 stub）或归档，不预支任务目录"
        )

    if blockers and os.environ.get(WIP_BREAK_GLASS_ENV, "").strip() not in ("", "0"):
        return [], [
            f"并行豁免生效（{WIP_BREAK_GLASS_ENV}=1），跳过 WIP 拦截：" + "；".join(blockers)
        ]
    return blockers, []


def _task_text(task_dir: Path, data: dict) -> str:
    parts: list[str] = []
    for key in ("id", "name", "title", "description", "dev_type", "scope", "package"):
        value = data.get(key)
        if isinstance(value, str):
            parts.append(value)
    for artifact in ("prd.md", "design.md", "implement.md"):
        path = task_dir / artifact
        if path.is_file():
            parts.append(path.read_text(encoding="utf-8", errors="replace"))
    return "\n".join(parts).lower()


def _development_strategy_missing(data: dict) -> bool:
    meta = data.get("meta")
    if not isinstance(meta, dict):
        return True
    strategy = meta.get("development_strategy")
    if not isinstance(strategy, dict):
        return True
    if strategy.get("contract") != STRATEGY_CONTRACT:
        return True
    if strategy.get("execution") not in EXECUTION_VALUES:
        return True
    if strategy.get("git_mode") not in GIT_MODE_VALUES:
        return True
    if strategy.get("development_mode") not in DEVELOPMENT_MODE_VALUES:
        return True
    gates = strategy.get("review_gates")
    if not isinstance(gates, dict):
        return True
    return any(gates.get(key) not in REVIEW_GATE_VALUES for key in REVIEW_GATE_KEYS)


def _is_platform_workflow_task(task_dir: Path, data: dict) -> bool:
    text = _task_text(task_dir, data)
    if any(marker in text for marker in PLATFORM_PATH_MARKERS):
        return True
    return any(_contains_word_marker(text, marker) for marker in PLATFORM_WORD_MARKERS)


def _contains_word_marker(text: str, marker: str) -> bool:
    escaped_parts = [re.escape(part) for part in marker.split()]
    pattern = r"(?<![a-z0-9_-])" + r"\s+".join(escaped_parts) + r"(?![a-z0-9_-])"
    return re.search(pattern, text) is not None


def _has_research_artifact(task_dir: Path) -> bool:
    research_dir = task_dir / "research"
    if not research_dir.is_dir():
        return False
    return any(path.is_file() for path in research_dir.glob("*.md"))


def _has_research_exemption(task_dir: Path) -> bool:
    text = _task_text(task_dir, {})
    return any(marker in text for marker in RESEARCH_EXEMPT_MARKERS)
