#!/usr/bin/env python3
"""Mechanical digest generator for agent session transcripts.

Supports two on-disk formats:
  * Claude Code:  ~/.claude/projects/<munged-cwd>/<session-id>.jsonl
                  (sibling dir <session-id>/subagents/*.jsonl if present)
  * Codex CLI:    ~/.codex/sessions/YYYY/MM/DD/rollout-*-<session-id>.jsonl
                  (spawned subagents are sibling rollout files keyed by agent id)

Usage:
  parse_transcript.py <path|session-id-or-prefix> [--max-asst N] [--full-asst] [--timeline]

Output: a markdown digest on stdout. The digest is the thing the auditing
agent reads; the raw transcript should only be consulted for spans the
digest flags. This keeps token cost bounded and avoids replaying large
verbatim transcript chunks (which can trip safety classifiers when the
audited session contained security-adjacent content).

Stdlib only. Exit 1 with a message on stderr if the transcript can't be
located or parsed.
"""

import argparse
import glob
import json
import os
import re
import sys
from collections import Counter
from datetime import datetime

MAX_USER_CHARS = 2000  # user messages are the highest-signal content; keep generous
MAX_SUBAGENT_CHARS = 1500


def find_transcript(token):
    """Resolve a path, session id, or id prefix to a transcript file."""
    if os.path.isfile(token):
        return token
    home = os.path.expanduser("~")
    hits = glob.glob(os.path.join(home, ".claude", "projects", "*", f"{token}*.jsonl"))
    hits += glob.glob(
        os.path.join(home, ".codex", "sessions", "*", "*", "*", f"*{token}*.jsonl")
    )
    hits = [h for h in hits if os.path.isfile(h)]
    if not hits:
        sys.exit(f"error: no transcript found for {token!r}")
    if len(hits) > 1:
        sys.stderr.write("warning: multiple matches, using newest:\n")
        for h in hits:
            sys.stderr.write(f"  {h}\n")
    return max(hits, key=os.path.getmtime)


def text_of(content):
    """Flatten a CC/Codex message content field into plain text."""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = []
        for block in content:
            if isinstance(block, dict) and block.get("type") in (
                "text",
                "input_text",
                "output_text",
            ):
                parts.append(block.get("text", ""))
        return "\n".join(parts)
    return ""


def clip(text, limit):
    text = text.strip()
    if limit and len(text) > limit:
        return text[:limit] + f" …[+{len(text) - limit} chars]"
    return text


def new_digest(fmt):
    return {
        "format": fmt,
        "users": [],           # (ts, text, flags)
        "assistants": [],      # (ts, text)
        "tools": Counter(),
        "notable": [],         # (ts, label)
        "errors": [],
        "models": Counter(),
        "meta": {},
        "compacts": 0,
        "compact_ts": [],
        "interrupts": 0,
        "subagent_notes": [],  # (ts, agent_id, text) — subagent result payloads
        "subagents": [],       # {id, type, nickname, ts, file} — spawned agents
    }


def parse_claude_code(path, events):
    d = new_digest("claude-code")
    first_ts = last_ts = None
    for ev in events:
        ts = ev.get("timestamp")
        if ts:
            first_ts = first_ts or ts
            last_ts = ts
        etype = ev.get("type")
        if etype == "permission-mode":
            d["meta"].setdefault("permission_modes", set()).add(
                ev.get("permissionMode", "?")
            )
        elif etype == "summary" and ev.get("summary"):
            d["meta"]["ai_title"] = ev["summary"]
        elif etype in ("compact-boundary", "compact"):
            d["compacts"] += 1
            d["compact_ts"].append(ts)
        elif etype == "pr-link" and ev.get("url"):
            d["notable"].append((ts, f"PR link: {ev['url']}"))
        elif etype == "user" and not ev.get("isMeta"):
            msg = ev.get("message", {})
            content = msg.get("content")
            if isinstance(content, list) and any(
                isinstance(b, dict) and b.get("type") == "tool_result" for b in content
            ):
                continue  # tool results are not user speech
            text = text_of(content)
            if not text.strip():
                continue
            if text.startswith("<task-notification>"):
                # route BEFORE interrupt detection: notification bodies may
                # quote "[Request interrupted…]" from other audited sessions
                m = re.search(r"<summary>([^<]*)</summary>", text)
                d["subagent_notes"].append((ts, "", m.group(1) if m else text))
                continue  # background-task results are not user speech
            flags = []
            if text.lstrip().startswith("[Request interrupted"):
                d["interrupts"] += 1
                flags.append("INTERRUPT")
            if text.startswith("<command-name>"):
                m = re.search(r"<command-name>([^<]+)</command-name>", text)
                text = f"(slash) {m.group(1) if m else '?'}"
                flags.append("SLASH")
            if "<local-command-stdout>" in text:
                flags.append("STDOUT")
            d["users"].append((ts, text, flags))
        elif etype == "assistant":
            msg = ev.get("message", {})
            model = msg.get("model")
            if model:
                d["models"][model] += 1
            for block in msg.get("content") or []:
                if not isinstance(block, dict):
                    continue
                if block.get("type") == "text" and block.get("text", "").strip():
                    d["assistants"].append((ts, block["text"]))
                elif block.get("type") == "tool_use":
                    name = block.get("name", "?")
                    d["tools"][name] += 1
                    inp = block.get("input") or {}
                    if name == "Bash":
                        cmd = str(inp.get("command", ""))
                        if re.search(r"git (commit|push|merge)|gh pr|gh api", cmd):
                            d["notable"].append((ts, f"Bash: {clip(cmd, 160)}"))
                    elif name in ("Write", "Edit"):
                        d["notable"].append(
                            (ts, f"{name}: {inp.get('file_path', '?')}")
                        )
                    elif name in ("Agent", "Task"):
                        d["notable"].append(
                            (ts, f"{name}: {clip(str(inp.get('description', '')), 80)}")
                        )
                    elif name == "Skill":
                        # rare, high-signal: skill invocations anchor phases
                        d["notable"].append(
                            (ts, f"Skill: {inp.get('skill', '?')}")
                        )
        # API errors / refusals surface as system or assistant-adjacent events
        raw = json.dumps(ev, ensure_ascii=False) if etype == "system" else ""
        if etype == "system" and re.search(
            r"refusal|API Error|model_refusal|apiRefusalCategory", raw
        ):
            d["errors"].append((ts, clip(re.sub(r"\s+", " ", raw), 200)))
    d["meta"]["first_ts"] = first_ts
    d["meta"]["last_ts"] = last_ts
    sub = os.path.join(os.path.dirname(path), os.path.basename(path)[:-6], "subagents")
    if os.path.isdir(sub):
        d["meta"]["subagents"] = len(glob.glob(os.path.join(sub, "*.jsonl")))
    return d


def parse_subagent_notification(text):
    """Extract (agent_id, result_text) from a <subagent_notification> body."""
    body = re.sub(r"^\s*<subagent_notification>\s*", "", text)
    body = re.sub(r"\s*</subagent_notification>\s*$", "", body)
    try:
        obj = json.loads(body)
        agent_id = obj.get("agent_path", "")
        status = obj.get("status")
        if isinstance(status, dict) and status:
            result = next(iter(status.values()))
        else:
            result = str(status or "")
        return agent_id, str(result)
    except (json.JSONDecodeError, StopIteration):
        m = re.search(r'"agent_path"\s*:\s*"([^"]+)"', body)
        return (m.group(1) if m else ""), body


def find_sibling_rollouts(path, agent_ids):
    """Map codex agent ids to their sibling rollout files (spawned subagents
    get their own rollout under the same sessions tree, usually same day)."""
    root = os.path.dirname(path)
    for _ in range(3):  # walk up to the sessions root (YYYY/MM/DD layout)
        if os.path.basename(root) == "sessions" or not os.path.dirname(root):
            break
        root = os.path.dirname(root)
    files = {}
    for aid in agent_ids:
        hits = glob.glob(os.path.join(root, "**", f"*{aid}*.jsonl"), recursive=True)
        hits = [h for h in hits if os.path.abspath(h) != os.path.abspath(path)]
        if hits:
            files[aid] = max(hits, key=os.path.getmtime)
    return files


def parse_codex(path, events):
    d = new_digest("codex")
    first_ts = last_ts = None
    spawn_calls = {}  # call_id -> agent_type (from spawn_agent arguments)
    for ev in events:
        ts = ev.get("timestamp")
        if ts:
            first_ts = first_ts or ts
            last_ts = ts
        payload = ev.get("payload") or {}
        etype = ev.get("type")
        ptype = payload.get("type")
        if etype == "session_meta":
            if d["meta"].get("session_id"):
                # extra session_meta lines mean the session was reopened/resumed
                d["meta"]["resumes"] = d["meta"].get("resumes", 0) + 1
            d["meta"]["session_id"] = payload.get("id")
            d["meta"]["cwd"] = payload.get("cwd")
        elif etype == "compacted":
            # replacement_history replays prior messages verbatim — never mine
            # it for user/assistant text, only count the compaction itself
            d["compacts"] += 1
            d["compact_ts"].append(ts)
        elif etype == "turn_context":
            model = payload.get("model")
            if isinstance(model, str) and model:
                d["models"][model] += 1
            effort = payload.get("effort") or payload.get("reasoning_effort")
            if effort:
                d["meta"]["effort"] = effort
        elif etype == "response_item":
            if ptype == "message":
                role = payload.get("role")
                text = text_of(payload.get("content"))
                if not text.strip():
                    continue
                if role == "user":
                    # skip harness-injected context blocks, keep real user speech
                    if re.match(
                        r"\s*<(environment_context|permissions instructions|"
                        r"user_instructions|turn_context)", text
                    ):
                        continue
                    if re.match(r"\s*#\s*AGENTS\.md instructions", text):
                        continue  # harness-injected repo guide, not user speech
                    if text.lstrip().startswith("<subagent_notification>"):
                        agent_id, result = parse_subagent_notification(text)
                        d["subagent_notes"].append((ts, agent_id, result))
                        continue
                    d["users"].append((ts, text, []))
                elif role == "assistant":
                    d["assistants"].append((ts, text))
            elif ptype in ("function_call", "custom_tool_call"):
                name = payload.get("name", ptype)
                d["tools"][name] += 1
                if name == "spawn_agent":
                    agent_type = ""
                    try:
                        agent_type = json.loads(
                            payload.get("arguments") or "{}"
                        ).get("agent_type", "")
                    except json.JSONDecodeError:
                        pass
                    spawn_calls[payload.get("call_id")] = agent_type
                    d["notable"].append(
                        (ts, f"spawn_agent: {agent_type or '(fork)'}")
                    )
                elif name in ("shell_command", "shell", "exec_command"):
                    try:
                        cmd = str(json.loads(
                            payload.get("arguments") or "{}"
                        ).get("command", ""))
                    except json.JSONDecodeError:
                        cmd = ""
                    if re.search(r"git (commit|push|merge)|gh pr|gh api", cmd):
                        d["notable"].append((ts, f"shell: {clip(cmd, 160)}"))
            elif ptype == "function_call_output":
                call_id = payload.get("call_id")
                if call_id in spawn_calls:
                    try:
                        out = json.loads(str(payload.get("output") or ""))
                        if isinstance(out, dict) and out.get("agent_id"):
                            d["subagents"].append({
                                "id": out["agent_id"],
                                "type": spawn_calls[call_id],
                                "nickname": out.get("nickname", ""),
                                "ts": ts,
                            })
                    except json.JSONDecodeError:
                        pass  # rejected spawn — output is an error string
            elif ptype in ("local_shell_call", "shell_call"):
                d["tools"]["shell"] += 1
                cmd = str(payload.get("action", {}).get("command", ""))
                if re.search(r"git (commit|push|merge)|gh pr|gh api", cmd):
                    d["notable"].append((ts, f"shell: {clip(cmd, 160)}"))
        elif etype == "event_msg":
            if ptype in ("error", "stream_error", "turn_aborted"):
                d["errors"].append(
                    (ts, clip(json.dumps(payload, ensure_ascii=False), 200))
                )
            elif ptype == "task_started":
                d["tools"]["(turns)"] += 1
    d["meta"]["first_ts"] = first_ts
    d["meta"]["last_ts"] = last_ts
    if d["subagents"]:
        d["meta"]["subagents"] = len({a["id"] for a in d["subagents"]})
        rollouts = find_sibling_rollouts(path, [a["id"] for a in d["subagents"]])
        for a in d["subagents"]:
            a["file"] = rollouts.get(a["id"], "")
    return d


def parse_ts(ts):
    if not ts:
        return None
    try:
        return datetime.fromisoformat(str(ts).replace("Z", "+00:00"))
    except ValueError:
        return None


def fmt_delta(seconds):
    m, s = divmod(int(seconds), 60)
    return f"+{m:02d}:{s:02d}"


def render_timeline(d):
    """Chronological anchor list with time deltas — reconstructs phase
    durations (gate wait times, work stretches) without hand-diffing stamps."""
    anchors = []
    for ts, text, flags in d["users"]:
        tag = f"[{','.join(flags)}] " if flags else ""
        anchors.append((ts, f"USER {tag}{clip(re.sub(chr(10), ' ', text), 100)}"))
    for ts, agent_id, text in d["subagent_notes"]:
        who = f" {agent_id[:8]}" if agent_id else ""
        anchors.append(
            (ts, f"SUBAGENT{who}: {clip(re.sub(chr(10), ' ', text), 100)}")
        )
    for a in d["subagents"]:
        anchors.append((a["ts"], f"SPAWN {a['id'][:8]} ({a['type'] or 'fork'})"))
    for ts, label in d["notable"]:
        if not label.startswith("spawn_agent"):  # spawns rendered via SPAWN
            anchors.append((ts, label))
    for ts in d["compact_ts"]:
        anchors.append((ts, "COMPACTED"))
    for ts, label in d["errors"]:
        anchors.append((ts, f"ERROR: {label}"))
    anchors = [(ts, lbl) for ts, lbl in anchors if ts]
    anchors.sort(key=lambda a: str(a[0]))
    out = ["", f"## Timeline ({len(anchors)} anchors, delta = since previous)"]
    prev = None
    for ts, label in anchors:
        t = parse_ts(ts)
        delta = fmt_delta((t - prev).total_seconds()) if t and prev else "      "
        clock = t.strftime("%H:%M:%S") if t else str(ts)
        out.append(f"- {clock} {delta}  {label}")
        prev = t or prev
    return out


def render(path, d, max_asst, show_all_asst, timeline):
    out = []
    meta = d["meta"]
    out.append(f"# Transcript digest: {os.path.basename(path)}")
    out.append("")
    size = os.path.getsize(path)
    out.append(f"- format: {d['format']}  |  file size: {size/1e6:.1f} MB")
    out.append(f"- span: {meta.get('first_ts')} → {meta.get('last_ts')}")
    for key in ("ai_title", "session_id", "cwd", "effort"):
        if meta.get(key):
            out.append(f"- {key}: {meta[key]}")
    if meta.get("permission_modes"):
        out.append(f"- permission modes: {', '.join(sorted(meta['permission_modes']))}")
    if d["models"]:
        out.append(
            "- models: "
            + ", ".join(f"{m} ×{c}" for m, c in d["models"].most_common())
        )
    out.append(
        f"- user msgs: {len(d['users'])}  |  assistant texts: {len(d['assistants'])}"
        f"  |  interrupts: {d['interrupts']}  |  compacts: {d['compacts']}"
        f"  |  resumes: {meta.get('resumes', 0)}"
        f"  |  subagents: {meta.get('subagents', 0)}"
    )
    if d["subagents"]:
        out.append("")
        out.append(f"## Subagents spawned ({len(d['subagents'])})")
        for a in d["subagents"]:
            loc = f"  →  {a['file']}" if a.get("file") else "  (no rollout file found)"
            nick = f" “{a['nickname']}”" if a.get("nickname") else ""
            out.append(f"- [{a['ts']}] {a['id']} ({a['type'] or 'fork'}{nick}){loc}")
    if timeline:
        out.extend(render_timeline(d))
    out.append("")
    out.append("## Tool usage")
    if d["tools"]:
        out.append(
            ", ".join(f"{name} ×{n}" for name, n in d["tools"].most_common(20))
        )
    else:
        out.append("(none)")
    out.append("")
    out.append(f"## User messages ({len(d['users'])}, verbatim up to {MAX_USER_CHARS} chars)")
    for ts, text, flags in d["users"]:
        tag = f" [{','.join(flags)}]" if flags else ""
        out.append(f"\n### [{ts}]{tag}\n{clip(text, MAX_USER_CHARS)}")
    if d["subagent_notes"]:
        out.append("")
        out.append(f"## Subagent results ({len(d['subagent_notes'])})")
        for ts, agent_id, text in d["subagent_notes"]:
            who = f" {agent_id}" if agent_id else ""
            out.append(f"\n### [{ts}]{who}\n{clip(text, MAX_SUBAGENT_CHARS)}")
    out.append("")
    limit = None if show_all_asst else max_asst
    out.append(f"## Assistant texts ({len(d['assistants'])})")
    for ts, text in d["assistants"]:
        out.append(f"\n### [{ts}]\n{clip(text, limit)}")
    if d["notable"]:
        out.append("")
        out.append(f"## Notable calls ({len(d['notable'])})")
        for ts, label in d["notable"]:
            out.append(f"- [{ts}] {label}")
    if d["errors"]:
        out.append("")
        out.append(f"## Errors / refusals ({len(d['errors'])})")
        for ts, label in d["errors"]:
            out.append(f"- [{ts}] {label}")
    return "\n".join(out) + "\n"


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("token", help="transcript path, session id, or id prefix")
    ap.add_argument("--max-asst", type=int, default=500,
                    help="truncate each assistant text to N chars (default 500)")
    ap.add_argument("--full-asst", action="store_true",
                    help="do not truncate assistant texts")
    ap.add_argument("--timeline", action="store_true",
                    help="emit a chronological anchor timeline with time deltas")
    args = ap.parse_args()

    path = find_transcript(args.token)
    events = []
    with open(path, encoding="utf-8") as fh:
        for line in fh:
            try:
                events.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    is_codex = os.path.basename(path).startswith("rollout-") or any(
        e.get("type") == "session_meta" for e in events[:5]
    )
    d = parse_codex(path, events) if is_codex else parse_claude_code(path, events)
    sys.stdout.write(render(path, d, args.max_asst, args.full_asst, args.timeline))


if __name__ == "__main__":
    main()
