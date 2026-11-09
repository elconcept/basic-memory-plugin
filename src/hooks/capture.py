"""Stdlib-only, offline transcript-to-material extraction (F1b).

Never copies tool outputs, model reasoning, secrets from unapproved tool args.
No Basic Memory CLI, network, external dependencies or upstream AGPL code.
"""
from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
import re

DECISION = re.compile(
    r"decyzj|zdecydow|ustal|postanow|wybier|przyjmuj|rekomend|"
    r"\bdecision\b|\bdecided\b|\bwe will\b|\bchose\b|\bagreed\b|\bD\d+\b", re.I
)
SAFE_ARGS = ("file_path", "path", "title", "project")


@dataclass(frozen=True)
class Transcript:
    turns: tuple[tuple[str, str], ...]
    calls: tuple[str, ...]
    invalid_lines: int
    recognized: int
    next_offset: int
    boundary: bool
    failure: str | None = None


@dataclass(frozen=True)
class Material:
    parts: tuple[str, ...]
    complete: bool
    omitted: dict[str, int]


def _text(content: object) -> str:
    if isinstance(content, str):
        return content
    if not isinstance(content, list):
        return ""
    return "\n".join(b["text"] for b in content if isinstance(b, dict)
                     and b.get("type") in {"text", "input_text", "output_text"}
                     and isinstance(b.get("text"), str))


def _interpret(row: object) -> tuple[str, str, list[str]] | None:
    if not isinstance(row, dict) or row.get("isMeta") or row.get("is_sidechain") or row.get("toolUseResult") is not None:
        return None
    kind = row.get("type")
    if kind in ("user", "assistant"):
        message = row.get("message")
        if not isinstance(message, dict):
            return None
        role = message.get("role", kind)
    elif kind == "response_item":
        message = row.get("payload")
        if not isinstance(message, dict) or message.get("type") != "message":
            return None
        role = message.get("role")
    elif kind == "event_msg":
        payload = row.get("payload")
        if isinstance(payload, dict) and payload.get("type") == "user_message":
            txt = payload.get("message")
            return ("user", txt, []) if isinstance(txt, str) and txt.strip() else None
        return None
    elif kind == "message":
        message, role = row, row.get("role")
    else:
        return None
    if role not in {"user", "assistant"}:
        return None
    content = message.get("content")
    calls = []
    if role == "assistant" and isinstance(content, list):
        for b in content:
            if not isinstance(b, dict) or b.get("type") not in {"tool_use", "function_call"}:
                continue
            name = b.get("name")
            if not isinstance(name, str) or not name:
                continue
            args = b.get("input", b.get("arguments"))
            if isinstance(args, str):
                try:
                    args = json.loads(args)
                except (ValueError, TypeError):
                    args = {}
            if not isinstance(args, dict):
                args = {}
            safe = ", ".join(f"{k}={str(args[k])[:200]!r}" for k in SAFE_ARGS if isinstance(args.get(k), str))
            calls.append(f"{name} ({safe})" if safe else name)
    text = _text(content).strip()
    return (role, text, calls) if text or calls else None


def parse_transcript(path: Path | None, after_offset: int = 0, use_last_boundary: bool = False) -> Transcript:
    if path is None:
        return Transcript((), (), 0, 0, 0, False, "no_transcript_path")
    try:
        path = Path(path).expanduser()
        if path.is_symlink() or not path.is_file():
            return Transcript((), (), 0, 0, 0, False, "unreadable")
        size = path.stat().st_size
        if after_offset < 0 or after_offset > size:
            after_offset = 0
        turns, calls = [], []
        invalid = found = 0
        boundary, boundary_offset = False, 0
        with path.open("rb") as stream:
            stream.seek(after_offset)
            while raw := stream.readline():
                start = stream.tell() - len(raw)
                try:
                    row = json.loads(raw)
                except (UnicodeDecodeError, ValueError):
                    invalid += 1
                    continue
                if isinstance(row, dict) and row.get("type") in {"system", "event_msg"}:
                    payload = row.get("payload")
                    subtype = payload.get("type") if isinstance(payload, dict) else row.get("subtype")
                    if subtype in {"compact_boundary", "compaction_boundary"}:
                        boundary_offset = stream.tell()
                        boundary = True
                parsed = _interpret(row)
                if parsed is None:
                    continue
                role, txt, tool_calls = parsed
                found += 1
                if txt:
                    turns.append((role, txt, start))
                calls.extend((call, start) for call in tool_calls)
            next_offset = stream.tell()
        if use_last_boundary and boundary:
            turns = [item for item in turns if item[2] >= boundary_offset]
            calls = [item for item in calls if item[1] >= boundary_offset]
        if size > after_offset and not found:
            return Transcript((), (), invalid, 0, next_offset, boundary, "unknown_format")
        return Transcript(tuple((r, t) for r, t, _ in turns), tuple(c for c, _ in calls),
                          invalid, found, next_offset, boundary)
    except (OSError, ValueError):
        return Transcript((), (), 0, 0, 0, False, "unreadable")


def materialize(t: Transcript, meta: dict, max_bytes: int = 49_152, max_parts: int = 4) -> Material:
    if max_bytes < 512 or not 1 <= max_parts <= 16:
        raise ValueError("Invalid material budget")
    decisions = []
    truncated = {"decision": 0, "user": 0, "assistant": 0}
    for role, text in t.turns:
        for para in re.split(r"\n\s*\n", text):
            if DECISION.search(para):
                if len(para) > 1500:
                    truncated["decision"] += 1
                decisions.append("- [" + role + "] " + para[:1500] + (" [TRUNCATED]" if len(para) > 1500 else "") + "\n")
    entries = [(kind, item) for kind, item in (
        ("decision", item) for item in dict.fromkeys(decisions))]
    for role, text in t.turns:
        limit = 2000 if role == "user" else 2500
        if len(text) > limit:
            truncated[role] += 1
        entries.append((role, "### " + role + "\n" + text[:limit] +
                        (" [TRUNCATED]" if len(text) > limit else "") + "\n"))
    for call in list(dict.fromkeys(t.calls))[:150]:
        entries.append(("tool", "- " + call + "\n"))
    omitted = dict.fromkeys(("decision", "user", "assistant", "tool"), 0)
    for kind, n in truncated.items():
        omitted[kind] += n
    omitted["tool"] += max(0, len(dict.fromkeys(t.calls)) - 150)
    head = "# Basic Memory checkpoint material\n" + "".join(
        f"{k}: {v}\n" for k, v in meta.items()
    ) + f"recognized: {t.recognized}\ninvalid_lines: {t.invalid_lines}\nerror: {t.failure or 'none'}\n\n"
    footer_reserve = 180
    capacity = max_bytes * max_parts - len(head.encode()) - footer_reserve
    if capacity <= 0:
        raise ValueError("Metadata exceeds material budget")
    included = []
    for kind, text in entries:
        byte_length = len(text.encode("utf-8"))
        if byte_length <= capacity:
            included.append(text)
            capacity -= byte_length
        else:
            omitted[kind] += 1
    complete = not t.failure and t.invalid_lines == 0 and not any(omitted.values())
    footer = "\ncomplete: " + str(bool(complete)).lower() + "\n" + "".join(
        f"omitted_{k}: {v}\n" for k, v in omitted.items()
    )
    result = head + "".join(included) + footer
    # Split at character boundaries so each part is valid UTF-8.
    chunks, current, current_bytes = [], [], 0
    for char in result:
        size = len(char.encode("utf-8"))
        if current_bytes + size > max_bytes:
            chunks.append("".join(current))
            current, current_bytes = [], 0
        current.append(char)
        current_bytes += size
    if current:
        chunks.append("".join(current))
    if len(chunks) > max_parts:
        raise ValueError("Budget underestimated: preserve data and stop")
    return Material(tuple(chunks), bool(complete), omitted)
