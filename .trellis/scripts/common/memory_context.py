#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Shared cross-platform project memory for SessionStart injection.

Why: agent-private memories are platform-locked (Claude Code auto-memory,
Codex memories) and Claude's is additionally keyed by project directory —
neither side can see the other's notes. Facts that any future session (on
either platform) needs belong in a git-tracked file instead:

    .trellis/workspace/<developer>/memory.md

This module renders that file as a <project-memory> block for both the
Claude and Codex session-start hooks (same builder, no per-platform fork).
Keep the file entry-style and small; it is injected into every session.
"""
from __future__ import annotations

from pathlib import Path

_MAX_CHARS = 4000


def build_memory_block(project_dir: Path) -> str:
    """Return a <project-memory> block, or '' when no memory file exists.

    Fail-open: any error yields '' so session start never breaks on memory.
    """
    try:
        dev_file = project_dir / ".trellis" / ".developer"
        if not dev_file.is_file():
            return ""
        developer = ""
        for line in dev_file.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            # .developer is key=value (name=<dev>, initialized_at=...); also
            # accept a bare first-line name for older layouts.
            if line.startswith("name="):
                developer = line.split("=", 1)[1].strip()
                break
            if "=" not in line:
                developer = line
                break
        if not developer:
            return ""
        memory = project_dir / ".trellis" / "workspace" / developer / "memory.md"
        if not memory.is_file():
            return ""
        text = memory.read_text(encoding="utf-8").strip()
        if not text:
            return ""
        truncated = False
        if len(text) > _MAX_CHARS:
            text = text[:_MAX_CHARS]
            truncated = True
        lines = ["<project-memory>", text]
        if truncated:
            lines.append(
                f"[truncated at {_MAX_CHARS} chars — read {memory.as_posix()} for the rest]"
            )
        lines.append("</project-memory>")
        return "\n".join(lines)
    except Exception:
        return ""
