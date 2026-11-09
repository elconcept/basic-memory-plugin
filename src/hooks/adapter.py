"""Local hook event adapter for Basic Memory NAS.

Stdlib-only, fail-open for agent lifecycle except explicit Stop/guard controls.
No MCP request, network, credentials, upstream Basic Memory imports, or daemon.
The local checkpoint state is not evidence of remote persistence unless a
readback event matches a previously written note reference and project.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import re
import sys
import tempfile
from typing import Any

from src.hooks.capture import materialize, parse_transcript
from src.hooks.state_store import CheckpointError, StateStore

CHECKPOINT = re.compile(r"\bck-[0-9a-f]{16}\b")
TOOLS = frozenset({"bm_write", "bm_edit", "bm_read"})
ALLOWED_SETTINGS = frozenset({
    "primaryProject", "allowedProjects", "captureFolder", "orientOnStart",
    "checkpointOnCompact", "checkpointOnSessionEnd", "sessionEndMinTurns",
    "materialMaxBytes", "materialMaxParts",
})
DEFAULTS = {
    "primaryProject": None, "allowedProjects": [], "captureFolder": "sessions",
    "orientOnStart": True, "checkpointOnCompact": True, "checkpointOnSessionEnd": True,
    "sessionEndMinTurns": 3, "materialMaxBytes": 49152, "materialMaxParts": 4,
}


def _json(path: Path) -> dict:
    if not path.is_file() or path.is_symlink():
        return {}
    try:
        value = json.loads(path.read_text("utf-8"))
    except (OSError, ValueError, UnicodeError):
        return {}
    data = value.get("basicMemory", {}) if isinstance(value, dict) else {}
    return {key: data[key] for key in ALLOWED_SETTINGS & data.keys()} if isinstance(data, dict) else {}


def settings(cwd: Path, harness: str, env: dict[str, str]) -> dict:
    home = Path(env.get("HOME", str(Path.home())))
    if harness == "claude":
        base = Path(env["CLAUDE_CONFIG_DIR"]) if env.get("CLAUDE_CONFIG_DIR") else home / ".claude"
        paths = [base / "settings.json", cwd / ".claude/settings.json", cwd / ".claude/settings.local.json"]
    else:
        paths = [home / ".codex/basic-memory.json", cwd / ".codex/basic-memory.json"]
    result = dict(DEFAULTS)
    for path in paths:
        result.update(_json(path))
    project = result.get("primaryProject")
    if project is not None and (not isinstance(project, str) or not project.strip()):
        result["primaryProject"] = None
    allowed = result.get("allowedProjects")
    if not isinstance(allowed, list) or not all(isinstance(p, str) and p.strip() for p in allowed):
        result["allowedProjects"] = []
    return result


def _session_id(event: dict) -> str | None:
    sid = event.get("session_id", event.get("sessionId"))
    return sid if isinstance(sid, str) and sid else None


def _source(event: dict) -> str:
    value = event.get("source", event.get("trigger", "startup"))
    return value if isinstance(value, str) else "startup"


def _tool(event: dict) -> str | None:
    name = event.get("tool_name", event.get("toolName"))
    if not isinstance(name, str):
        return None
    for item in TOOLS:
        if name == item or name.endswith("__" + item):
            return item
    return None


def _response_content(raw: object) -> str:
    if isinstance(raw, str):
        return raw
    if isinstance(raw, list):
        return "\n".join(item.get("text", "") for item in raw
                         if isinstance(item, dict) and isinstance(item.get("text"), str))
    if isinstance(raw, dict):
        if isinstance(raw.get("content"), (list, str)):
            return _response_content(raw["content"])
        return json.dumps(raw, ensure_ascii=False)
    return ""


def _response_error(raw: object) -> bool:
    if isinstance(raw, dict):
        return raw.get("isError") is True or raw.get("is_error") is True
    return False


def _ref(raw: object) -> str | None:
    if isinstance(raw, dict):
        for key in ("permalink", "identifier", "note_ref", "id", "uri"):
            value = raw.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()
        if isinstance(raw.get("structuredContent"), dict):
            return _ref(raw["structuredContent"])
        if isinstance(raw.get("content"), list):
            for item in raw["content"]:
                if isinstance(item, dict) and isinstance(item.get("text"), str):
                    try:
                        found = _ref(json.loads(item["text"]))
                    except ValueError:
                        continue
                    if found:
                        return found
    return None


def _checkpoint_key(event: dict) -> str | None:
    inputs = event.get("tool_input", event.get("toolInput", {}))
    found = CHECKPOINT.findall(json.dumps(inputs, ensure_ascii=False))
    return found[0] if len(set(found)) == 1 and found else None


def _tool_input(event: dict) -> dict:
    obj = event.get("tool_input", event.get("toolInput"))
    return obj if isinstance(obj, dict) else {}


def _context(content: str) -> dict:
    return {"hookSpecificOutput": {"hookEventName": "SessionStart", "additionalContext": content[:6000]}}


class Adapter:
    def __init__(self, store: StateStore, harness: str, config: dict):
        self.store, self.harness, self.config = store, harness, config
        self.project: str | None = config.get("primaryProject")

    def _register(self, event: dict) -> dict | None:
        sid = _session_id(event)
        if not sid:
            return None
        cwd = event.get("cwd")
        if not isinstance(cwd, str) or not cwd:
            cwd = os.getcwd()
        path = event.get("transcript_path", event.get("transcriptPath"))
        return self.store.register_session(sid, cwd, path if isinstance(path, str) else None, self.project)

    def _capture(self, event: dict, trigger: str, offset: int = 0,
                 use_last_boundary: bool = False) -> dict | None:
        session = self._register(event)
        if session is None:
            return None
        t = parse_transcript(
            Path(session["transcript_path"]) if session.get("transcript_path") else None,
            after_offset=offset, use_last_boundary=use_last_boundary,
        )
        if trigger == "session_end" and t.failure is None:
            if sum(role == "user" for role, _ in t.turns) < int(self.config["sessionEndMinTurns"]):
                return None
        entry = self.store.create(session["session_id"], trigger, self.harness, self.project,
                                  "failed:" + t.failure if t.failure else "partial", [])
        if t.failure:
            self.store.set_capture(entry["ck"], "failed:" + t.failure, False, [])
            return entry
        complete_segment = not use_last_boundary or t.boundary
        material = materialize(
            t, {"ck": entry["ck"], "session_id": entry["session_id"], "seq": entry["seq"],
                "trigger": trigger, "project": self.project or "UNASSIGNED"},
            max_bytes=int(self.config["materialMaxBytes"]),
            max_parts=int(self.config["materialMaxParts"]),
        )
        folder = self.store.directory / "material"
        folder.mkdir(mode=0o700, parents=True, exist_ok=True)
        os.chmod(folder, 0o700)
        created: list[str] = []
        try:
            for idx, part in enumerate(material.parts, start=1):
                dest = folder / f"{entry['ck']}.{idx}.md"
                fd = os.open(dest, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
                with os.fdopen(fd, "w", encoding="utf-8") as stream:
                    stream.write(part)
                    stream.flush()
                    os.fsync(stream.fileno())
                created.append(str(dest))
            self.store.set_capture(
                entry["ck"], "ok" if material.complete and complete_segment else "partial",
                material.complete and complete_segment, created, next_offset=t.next_offset,
            )
        except (OSError, ValueError):
            for p in created:
                Path(p).unlink(missing_ok=True)
            self.store.set_capture(entry["ck"], "failed:local_write_error", False, [])
        return self.store.get(entry["ck"])

    def pre_compact(self, event: dict) -> dict | None:
        if not self.config["checkpointOnCompact"]:
            return None
        return self._capture(event, "auto", use_last_boundary=True)

    def session_end(self, event: dict) -> dict | None:
        session = self._register(event)
        if session is None:
            return None
        try:
            return (self._capture(event, "session_end", offset=session["last_capture_offset"])
                    if self.config["checkpointOnSessionEnd"] else None)
        finally:
            self.store.end_session(session["session_id"])

    def session_start(self, event: dict) -> dict | None:
        session = self._register(event)
        if session is None:
            return None
        sid = session["session_id"]
        source = _source(event)
        pieces: list[str] = []
        if source == "compact":
            mine = self.store.pending_for_session(sid)
            if not mine:
                self.store.create(sid, "recovered", self.harness, self.project,
                                  "failed:missing_precompact")
                mine = self.store.pending_for_session(sid)
            for checkpoint in mine[:5]:
                pieces.append(
                    f"REQUIRED checkpoint {checkpoint['ck']} capture={checkpoint['capture']} "
                    f"project={checkpoint['project'] or 'UNASSIGNED'}. "
                    "Use basic-memory-nas:bm-checkpoint to write and read back the same note. "
                    "Do not claim saved before verified readback."
                )
        retries = self.store.retries(self.project, sid, limit=5)
        if retries:
            pieces.append("Unfinished checkpoints for project " + str(self.project) + ": " +
                          ", ".join(e["ck"] for e in retries) + ". Retry through bm-checkpoint.")
        unassigned = self.store.unassigned(limit=5)
        if unassigned:
            pieces.append("Unassigned checkpoints: " + ", ".join(e["ck"] for e in unassigned) +
                          ". Ask the user for each project; do not write without an explicit assignment.")
        if source in {"startup", "resume", "clear"} and self.config["orientOnStart"]:
            if self.project:
                pieces.append(
                    "Before substantive work use basic-memory-nas:bm-orient for project " +
                    self.project + ". Capture durable decisions with bm-decide and facts with bm-remember."
                )
            else:
                pieces.append("No Basic Memory primaryProject is configured. Ask before writing. Never assume main or legal.")
        if self.store.last_corrupt_backup:
            pieces.append("WARNING: previous local state was corrupt and preserved for inspection.")
        return _context("\n\n".join(pieces)) if pieces else None

    def post_tool(self, event: dict, failure: bool = False) -> dict | None:
        tool = _tool(event)
        if tool is None:
            return None
        inp = _tool_input(event)
        key = _checkpoint_key(event)
        if tool == "bm_read" and not key:
            identifier = inp.get("identifier", inp.get("id"))
            for e in self.store.snapshot()["checkpoints"].values():
                if e["status"] == "written" and e["note_ref"] == identifier:
                    key = e["ck"]
                    break
        if not key:
            return None
        try:
            entry = self.store.get(key)
            if failure:
                if tool in {"bm_write", "bm_edit"}:
                    return self.store.failed(key, "tool_failure", by="post-tool-failure")
                return None
            raw = event.get("tool_response", event.get("toolResponse"))
            if _response_error(raw) or not _response_content(raw):
                if tool in {"bm_write", "bm_edit"}:
                    return self.store.failed(key, "tool_error_or_empty")
                return None
            if tool in {"bm_write", "bm_edit"}:
                ref = _ref(raw)
                if not ref:
                    return self.store.failed(key, "no_ref")
                return self.store.written(key, inp.get("project"), ref)
            identifier = inp.get("identifier", inp.get("id"))
            return self.store.readback(
                key, inp.get("project"), identifier, _response_content(raw),
            )
        except CheckpointError:
            # Incorrect project/ref/key must never be treated as a successful write.
            return None

    def stop(self, event: dict) -> dict | None:
        if event.get("stop_hook_active") is True:
            return None
        sid = _session_id(event)
        entry = self.store.should_block_stop(sid) if sid else None
        if entry is None:
            return None
        return {
            "decision": "block",
            "reason": f"Basic Memory checkpoint {entry['ck']} remains {entry['status']}. "
                      "Write it and read back the same note via MCP or explicitly report failure.",
        }

    def status(self) -> dict:
        return self.store.status()


def _data_dir(harness: str, env: dict[str, str]) -> Path:
    name = "CLAUDE_PLUGIN_DATA" if harness == "claude" else "PLUGIN_DATA"
    return Path(env.get(name) or (Path(env.get("HOME", str(Path.home()))) / ".bm-hook-data"))


def _confirm_terminal(key: str) -> bool:
    try:
        with open("/dev/tty", "r+", encoding="utf-8") as tty:
            tty.write(f"Type the checkpoint key to confirm this action: {key}\n> ")
            tty.flush()
            return tty.readline().strip() == key
    except OSError:
        return False


def main(argv: list[str] | None = None, stdin: Any = None, env: dict[str, str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=(
        "session-start", "pre-compact", "post-tool", "post-tool-failure",
        "session-end", "stop", "status", "assign", "report", "confirm", "dismiss",
    ))
    parser.add_argument("--harness", choices=("claude", "codex"), default="claude")
    parser.add_argument("--key")
    parser.add_argument("--project")
    parser.add_argument("--ref")
    parser.add_argument("--error")
    args = parser.parse_args(argv)
    env = os.environ if env is None else env
    source = sys.stdin if stdin is None else stdin
    event = {}
    if args.command not in {"status", "assign", "report", "confirm", "dismiss"}:
        try:
            event = json.load(source)
        except (ValueError, TypeError):
            event = {}
    cwd = event.get("cwd") if isinstance(event.get("cwd"), str) else os.getcwd()
    runner = Adapter(StateStore(_data_dir(args.harness, env)), args.harness,
                     settings(Path(cwd), args.harness, env))
    try:
        if args.command == "status":
            output = runner.status()
        elif args.command == "assign":
            output = runner.store.assign(args.key, args.project, runner.config["allowedProjects"])
        elif args.command == "report":
            output = runner.store.failed(args.key, args.error) if args.error else runner.store.reported_by_model(args.key, args.ref)
        elif args.command in {"confirm", "dismiss"}:
            if not _confirm_terminal(args.key):
                print("Terminal confirmation denied or unavailable", file=sys.stderr)
                return 2
            output = runner.store.terminal_by_user(args.key, "saved" if args.command == "confirm" else "dismissed")
        else:
            method = {
                "session-start": runner.session_start, "pre-compact": runner.pre_compact,
                "session-end": runner.session_end, "stop": runner.stop,
                "post-tool": runner.post_tool,
                "post-tool-failure": lambda e: runner.post_tool(e, failure=True),
            }[args.command]
            output = method(event)
        if output is not None:
            print(json.dumps(output, ensure_ascii=False))
        return 0
    except (CheckpointError, OSError, ValueError, TypeError) as exc:
        print(f"Basic Memory hook: {type(exc).__name__} (checkpoint not confirmed)", file=sys.stderr)
        return 2 if args.command in {"assign", "report", "confirm", "dismiss"} else 0


if __name__ == "__main__":
    sys.exit(main())
