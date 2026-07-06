#!/usr/bin/env python3
"""Validate PR title/body against .github/pull_request_template.md.

The validate() contract mirrors the remote-delivery description checker used by
other profiles. Headings follow the generic bilingual GitHub PR template, and
the entry point speaks GitHub: pass --title/--body-file locally, or --number to
fetch via `gh pr view`.
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path


TITLE_PATTERN = re.compile(
    r"^(feat|fix|hotfix|docs|chore|test|refactor|ci|build|perf|style|revert)"
    r"(\([a-z0-9][a-z0-9-]*\))?: .{3,}$"
)

REQUIRED_HEADINGS = [
    "## Summary / 概述",
    "## Related Issues / 关联 Issue",
    "## What Changed / 变更内容",
    "## Reviewer Focus / 评审重点",
    "## Test Plan / 测试计划",
    "## Risk & Rollback / 风险与回滚",
    "## Checklist / 检查清单",
]

NON_EMPTY_SECTIONS = [
    "## Summary / 概述",
    "## What Changed / 变更内容",
    "## Test Plan / 测试计划",
    "## Risk & Rollback / 风险与回滚",
]

# Human-facing PR prose is Chinese-first (workflow Core Principle 6). The
# mechanical proxy: the Summary section must be written in Chinese — code
# identifiers/paths stay English, so only Summary is language-gated.
CHINESE_FIRST_SECTION = "## Summary / 概述"
CHINESE_MIN_CJK = 10
CJK_RE = re.compile(r"[㐀-鿿]")

PLACEHOLDER_TEXT = {
    "",
    "-",
    "- ",
    "Brief one-line description of this change. / 一句话描述本轮变更。",
    "Closes #<issue-number>",
    "N/A",
    "- Change A / 改动 A",
    "- Change B / 改动 B",
    "- Change C / 改动 C",
    "- Focus point A / 关注点 A",
    "- Focus point B / 关注点 B",
    "- **Risk / 风险**: ...",
    "- **Rollback / 回滚**: `git revert <commit>` or close the PR without merging / 或关闭 PR 不合并",
}

CODE_FENCE_PATTERN = re.compile(r"^\s*`{3,}[^`]*$")


def _normalise_description(description: str) -> list[str]:
    return description.replace("\r\n", "\n").replace("\r", "\n").splitlines()


def _heading_positions(lines: list[str]) -> dict[str, int]:
    positions: dict[str, int] = {}
    for index, line in enumerate(lines):
        stripped = line.strip()
        if stripped in REQUIRED_HEADINGS and stripped not in positions:
            positions[stripped] = index
    return positions


def _section_lines(lines: list[str], positions: dict[str, int], heading: str) -> list[str]:
    start = positions[heading] + 1
    following = [
        position
        for section_heading, position in positions.items()
        if section_heading != heading and position > positions[heading]
    ]
    end = min(following) if following else len(lines)
    return lines[start:end]


def _is_meaningful_plain_line(line: str) -> bool:
    if line in PLACEHOLDER_TEXT:
        return False
    if line.startswith("- [ ]"):
        return False
    if line.startswith("<!--"):
        return False
    return bool(line)


def _has_meaningful_content(section_lines: list[str]) -> bool:
    in_code_fence = False
    code_fence_has_content = False
    for raw_line in section_lines:
        line = raw_line.strip()
        if CODE_FENCE_PATTERN.match(line):
            if in_code_fence:
                if code_fence_has_content:
                    return True
                in_code_fence = False
                code_fence_has_content = False
            else:
                in_code_fence = True
                code_fence_has_content = False
            continue
        if in_code_fence:
            if line:
                code_fence_has_content = True
            continue
        if _is_meaningful_plain_line(line):
            return True
    return False


def validate(title: str, description: str) -> list[str]:
    errors: list[str] = []
    title = title.strip()
    if not TITLE_PATTERN.match(title):
        errors.append(
            "PR 标题必须使用 Conventional Commits："
            "<type>(<scope>): <summary>"
        )

    lines = _normalise_description(description)
    positions = _heading_positions(lines)
    missing = [heading for heading in REQUIRED_HEADINGS if heading not in positions]
    if missing:
        errors.append("PR 描述缺少章节：" + ", ".join(missing))
        return errors

    ordered_positions = [positions[heading] for heading in REQUIRED_HEADINGS]
    if ordered_positions != sorted(ordered_positions):
        errors.append("PR 描述章节顺序必须与 .github/pull_request_template.md 保持一致")

    for heading in NON_EMPTY_SECTIONS:
        if not _has_meaningful_content(_section_lines(lines, positions, heading)):
            errors.append(f"{heading} 章节不能留空或只保留模板占位文本")

    summary_text = "\n".join(_section_lines(lines, positions, CHINESE_FIRST_SECTION))
    if len(CJK_RE.findall(summary_text)) < CHINESE_MIN_CJK:
        errors.append(
            f"{CHINESE_FIRST_SECTION} 必须以中文书写（至少 {CHINESE_MIN_CJK} 个汉字）"
            "——给人看的 PR 描述中文优先，代码/标识符保持英文即可"
        )

    return errors


def _fetch_pull(number: str, repo: str | None) -> tuple[str, str]:
    command = ["gh", "pr", "view", number, "--json", "title,body"]
    if repo:
        command.extend(["--repo", repo])
    result = subprocess.run(command, capture_output=True, text=True, encoding="utf-8")
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or "gh pr view failed")
    data = json.loads(result.stdout)
    return data.get("title", ""), data.get("body", "")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Validate PR title/body against the PR template")
    parser.add_argument("--title", help="PR title to validate")
    parser.add_argument("--body-file", help="File containing the PR body")
    parser.add_argument("--number", help="Fetch title/body from an existing PR via gh")
    parser.add_argument("--repo", help="GitHub repo (owner/name) for --number lookups")
    args = parser.parse_args(argv)

    if args.number:
        try:
            title, description = _fetch_pull(args.number, args.repo)
        except Exception as exc:
            print(f"无法读取 PR #{args.number}：{exc}", file=sys.stderr)
            return 1
    elif args.title is not None:
        title = args.title
        description = Path(args.body_file).read_text(encoding="utf-8") if args.body_file else ""
    else:
        parser.print_usage(sys.stderr)
        print("需要 --title [--body-file] 或 --number", file=sys.stderr)
        return 2

    errors = validate(title, description)
    if errors:
        print("PR description check failed:")
        for error in errors:
            print(f"- {error}")
        return 1

    print("PR description check passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
