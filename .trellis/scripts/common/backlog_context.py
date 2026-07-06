#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
BACKLOG「触发已满足」context line.

M6: surface the project's "armed" backlog (items whose trigger condition is
already met, i.e. ready to be picked up) into the SessionStart context so the
"必读 BACKLOG" discipline becomes a mechanical reminder instead of a habit.

Source of truth is ``docs/BACKLOG.md`` in the repo root. We parse the
``## 触发已满足`` section's markdown table and emit a single summary line:

    Backlog armed (N): <item-1>；<item-2>…

Degrades to ``None`` (zero injection, zero error) when the file is missing,
the section is absent, or the table is empty — colleagues who never touch the
backlog file see nothing.

Provides:
    get_backlog_armed_line - one-line summary or None
"""

from __future__ import annotations

import re
from pathlib import Path

# Heading that opens the "armed" (trigger-satisfied) section.
_ARMED_HEADING = "## 触发已满足"

# Cap the injected line so a long backlog can't blow up the SessionStart
# payload. Measured in characters; overflow is truncated with an ellipsis.
_MAX_LINE_CHARS = 200

# Strip leading list bullets / blockquote markers that can wrap a table cell.
_LEADING_MARK_RE = re.compile(r"^[>\-*\s]+")
# Markdown emphasis / inline-code markers to peel off item names.
_EMPHASIS_RE = re.compile(r"[*_`]+")


def _backlog_path(repo_root: Path) -> Path:
    return repo_root / "docs" / "BACKLOG.md"


def _is_separator_cell(text: str) -> bool:
    """True for a markdown table separator cell like ``---`` or ``:--:``."""
    return bool(text) and set(text) <= set("-: ")


def _clean_item_name(cell: str) -> str:
    """Reduce a table's first cell to a bare item name.

    Drops leading bullet/quote noise and markdown emphasis markers so a cell
    like ``**L1 本地真链路 dev 环境**`` becomes ``L1 本地真链路 dev 环境``.
    """
    text = _LEADING_MARK_RE.sub("", cell).strip()
    text = _EMPHASIS_RE.sub("", text).strip()
    return text


def _parse_armed_items(content: str) -> list[str]:
    """Extract item names from the ``## 触发已满足`` table.

    Skips the header row (``事项 | …``) and the ``---`` separator row; takes the
    first column of every remaining table row as the item name.
    """
    lines = content.splitlines()

    start: int | None = None
    end: int = len(lines)
    for i, line in enumerate(lines):
        stripped = line.strip()
        if start is None:
            if stripped.startswith(_ARMED_HEADING):
                start = i
            continue
        # Next section heading closes the armed section.
        if stripped.startswith("## "):
            end = i
            break

    if start is None:
        return []

    items: list[str] = []
    for line in lines[start + 1 : end]:
        stripped = line.strip()
        if not stripped.startswith("|"):
            continue
        cells = [c.strip() for c in stripped.strip("|").split("|")]
        if not cells:
            continue
        first = cells[0]
        if _is_separator_cell(first):
            continue
        name = _clean_item_name(first)
        if not name or name == "事项":
            continue
        items.append(name)

    return items


def get_backlog_armed_line(repo_root: Path) -> str | None:
    """Return a one-line summary of armed backlog items, or None.

    Format: ``Backlog armed (N): a；b；c`` (items joined with the full-width
    semicolon). Returns None when ``docs/BACKLOG.md`` is missing, has no
    ``## 触发已满足`` section, or that section's table is empty. Never raises.
    """
    path = _backlog_path(repo_root)
    try:
        content = path.read_text(encoding="utf-8")
    except (FileNotFoundError, OSError):
        return None

    items = _parse_armed_items(content)
    if not items:
        return None

    summary = "；".join(items)
    line = f"Backlog armed ({len(items)}): {summary}"
    if len(line) > _MAX_LINE_CHARS:
        line = line[: _MAX_LINE_CHARS - 1].rstrip() + "…"
    return line
