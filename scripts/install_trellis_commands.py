#!/usr/bin/env python3
"""Install project-local Trellis command adapters.

Canonical command text lives under `.trellis/commands/`. Reviewed platform
adapters can be committed; this script keeps them generated from the same
source instead of hand-maintained per platform.
"""

from __future__ import annotations

import argparse
import sys
from dataclasses import dataclass
from pathlib import Path


SUPPORTED_PLATFORMS = ("claude", "codex")


@dataclass(frozen=True)
class RenderedCommand:
    path: Path
    content: str


def render_command(command_name: str, source: str, platform: str) -> RenderedCommand:
    if platform == "claude":
        return RenderedCommand(
            Path(".claude") / "commands" / "trellis" / f"{command_name}.md",
            source,
        )
    if platform == "codex":
        skill_name = f"trellis-{command_name}"
        content = "\n".join(
            [
                "---",
                f"name: {skill_name}",
                "description: \"Use when the user explicitly invokes "
                f"/trellis:{command_name} or asks to ship the current branch "
                "through push, PR, CI, self-review, and the squash merge gate.\"",
                "---",
                "",
                source,
            ]
        )
        return RenderedCommand(
            Path(".agents") / "skills" / skill_name / "SKILL.md",
            content,
        )
    raise ValueError(f"unsupported platform: {platform}")


def command_source_path(repo_root: Path, command_name: str) -> Path:
    return repo_root / ".trellis" / "commands" / f"{command_name}.md"


def install_command(
    repo_root: Path,
    command_name: str,
    platforms: list[str],
    *,
    dry_run: bool,
) -> list[Path]:
    source_path = command_source_path(repo_root, command_name)
    if not source_path.is_file():
        raise FileNotFoundError(f"command source not found: {source_path}")

    source = source_path.read_text(encoding="utf-8")
    written: list[Path] = []
    for platform in platforms:
        rendered = render_command(command_name, source, platform)
        target = repo_root / rendered.path
        if dry_run:
            print(f"would write {rendered.path}")
            written.append(target)
            continue
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(rendered.content, encoding="utf-8")
        print(f"wrote {rendered.path}")
        written.append(target)
    return written


def parse_platforms(value: str) -> list[str]:
    if value == "all":
        return list(SUPPORTED_PLATFORMS)
    platforms = [part.strip() for part in value.split(",") if part.strip()]
    unknown = [platform for platform in platforms if platform not in SUPPORTED_PLATFORMS]
    if unknown:
        raise ValueError(
            "unsupported platform(s): "
            + ", ".join(unknown)
            + f"; supported: {', '.join(SUPPORTED_PLATFORMS)}, all"
        )
    return platforms


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Install local Trellis command adapters")
    parser.add_argument("command", help="Command name, e.g. ship")
    parser.add_argument(
        "--platform",
        default="all",
        help="Platform list: claude,codex or all",
    )
    parser.add_argument("--repo-root", default=".", help="Repository root")
    parser.add_argument("--dry-run", action="store_true", help="Print paths without writing")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        platforms = parse_platforms(args.platform)
        install_command(
            Path(args.repo_root).resolve(),
            args.command,
            platforms,
            dry_run=args.dry_run,
        )
    except Exception as exc:
        print(f"install_trellis_commands failed: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
