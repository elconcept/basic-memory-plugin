"""Atomic local checkpoint ledger for the Basic Memory NAS bridge.

No MCP calls, network, source-code reuse, transcript capture, or token handling.
The lifecycle-event adapter (F1b) will be the only normal writer.
"""
from __future__ import annotations

from contextlib import contextmanager
from datetime import datetime, timezone
import fcntl
import hashlib
import json
import os
from pathlib import Path
import re
import tempfile
from typing import Callable, Iterator

VALID = frozenset({
    "pending", "written", "saved", "failed", "reported_by_model",
    "dismissed", "stale",
})
UNFINISHED = frozenset({"pending", "written", "failed"})
CK_PATTERN = re.compile(r"^ck-[a-f0-9]{16}$")
ISO = lambda: datetime.now(timezone.utc).isoformat(timespec="seconds")


class CheckpointError(Exception):
    """A rejected transition; never claim that a checkpoint was persisted."""


class StateStore:
    def __init__(self, directory: Path):
        self.directory = Path(directory).expanduser().resolve()
        self.directory.mkdir(mode=0o700, parents=True, exist_ok=True)
        os.chmod(self.directory, 0o700)
        self.state_path = self.directory / "state.json"
        self.lock_path = self.directory / "state.lock"
        self.last_corrupt_backup: str | None = None

    @staticmethod
    def _empty() -> dict:
        return {"version": 1, "checkpoints": {}, "open_sessions": {}}

    def _read(self) -> dict:
        if not self.state_path.exists():
            return self._empty()
        try:
            raw = json.loads(self.state_path.read_text(encoding="utf-8"))
            if not isinstance(raw, dict):
                raise ValueError("state is not an object")
            if not isinstance(raw.get("checkpoints"), dict) or not isinstance(raw.get("open_sessions"), dict):
                raise ValueError("missing collections")
            return raw
        except (OSError, ValueError, TypeError) as exc:
            # Preserve evidence rather than overwrite a corrupted JSON ledger.
            name = f"state.json.corrupt-{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}-{os.getpid()}"
            target = self.directory / name
            os.replace(self.state_path, target)
            self.last_corrupt_backup = str(target)
            return self._empty()

    def _write(self, state: dict) -> None:
        data = (json.dumps(state, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode()
        fd, name = tempfile.mkstemp(prefix=".state-", dir=self.directory)
        try:
            os.fchmod(fd, 0o600)
            with os.fdopen(fd, "wb", closefd=True) as stream:
                stream.write(data)
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(name, self.state_path)
            dirfd = os.open(self.directory, os.O_RDONLY)
            try:
                os.fsync(dirfd)
            finally:
                os.close(dirfd)
        finally:
            if os.path.exists(name):
                os.unlink(name)

    @contextmanager
    def transaction(self) -> Iterator[dict]:
        lockfd = os.open(self.lock_path, os.O_CREAT | os.O_RDWR, 0o600)
        os.fchmod(lockfd, 0o600)
        try:
            fcntl.flock(lockfd, fcntl.LOCK_EX)
            state = self._read()
            yield state
            self._write(state)
        finally:
            fcntl.flock(lockfd, fcntl.LOCK_UN)
            os.close(lockfd)

    def snapshot(self) -> dict:
        with self.transaction() as state:
            # Return a deep copy: callers may not mutate state after lock release.
            return json.loads(json.dumps(state))

    @staticmethod
    def _history(entry: dict, to: str, by: str, error: str | None = None) -> None:
        if to not in VALID:
            raise CheckpointError("Unknown state")
        prior = entry["status"]
        entry["status"] = to
        entry["updated"] = ISO()
        entry["error"] = error
        entry["history"].append({"at": entry["updated"], "from": prior, "to": to, "by": by})

    def create(self, session_id: str, trigger: str, harness: str, project: str | None,
               capture: str, material: list[str] | None = None, complete: bool = False,
               capture_folder: str = "sessions") -> dict:
        if not session_id or not isinstance(session_id, str):
            raise CheckpointError("Missing session ID")
        if trigger not in {"manual", "auto", "session_end", "recovered"}:
            raise CheckpointError("Invalid trigger")
        if project is not None and (not isinstance(project, str) or not project.strip()):
            raise CheckpointError("Project must be nonempty or null")
        with self.transaction() as state:
            entries = state["checkpoints"]
            seq = 1 + sum(v.get("session_id") == session_id for v in entries.values())
            key = "ck-" + hashlib.sha256(f"{session_id}:{seq}".encode()).hexdigest()[:16]
            if key in entries:
                raise CheckpointError("Checkpoint collision")
            now = ISO()
            entry = {
                "ck": key, "session_id": session_id, "seq": seq,
                "trigger": trigger, "harness": harness,
                "project": project, "assigned_via": None,
                "capture_folder": capture_folder,
                "status": "pending", "capture": capture,
                "complete": bool(complete), "material": list(material or []),
                "note_ref": None, "error": None,
                "created": now, "updated": now,
                "stop_blocked": False, "history": [],
            }
            entries[key] = entry
            return dict(entry)

    def assign(self, key: str, project: str, allowed: list[str]) -> dict:
        if not project or project not in allowed:
            raise CheckpointError("Project is not in allowedProjects")
        with self.transaction() as state:
            entry = state["checkpoints"].get(key)
            if entry is None:
                raise CheckpointError("Unknown checkpoint")
            if entry["project"] is not None:
                raise CheckpointError("Checkpoint already assigned")
            entry["project"] = project
            entry["assigned_via"] = "assign"
            entry["updated"] = ISO()
            return dict(entry)

    def written(self, key: str, project: str, ref: str) -> dict:
        with self.transaction() as state:
            entry = state["checkpoints"].get(key)
            if entry is None:
                raise CheckpointError("Unknown checkpoint")
            if not entry["project"] or project != entry["project"]:
                entry["error"] = "project_mismatch"
                raise CheckpointError("Project mismatch")
            if not ref or not isinstance(ref, str):
                raise CheckpointError("Missing note reference")
            if entry["status"] not in {"pending", "failed", "reported_by_model"}:
                raise CheckpointError("Unexpected write transition")
            entry["note_ref"] = ref
            self._history(entry, "written", "post-tool")
            return dict(entry)

    def readback(self, key: str, project: str, identifier: str, content: str,
                 is_error: bool = False) -> dict:
        with self.transaction() as state:
            entry = state["checkpoints"].get(key)
            if entry is None:
                raise CheckpointError("Unknown checkpoint")
            if entry["status"] != "written":
                raise CheckpointError("Checkpoint not written")
            if not entry["project"] or project != entry["project"]:
                raise CheckpointError("Readback project mismatch")
            if not identifier or identifier != entry["note_ref"]:
                raise CheckpointError("Readback identifier mismatch")
            if is_error or not isinstance(content, str):
                raise CheckpointError("Readback error")
            if not re.search(r"^checkpoint_key:\s*" + re.escape(key) + r"\s*$", content, re.MULTILINE):
                raise CheckpointError("Readback checkpoint key mismatch")
            self._history(entry, "saved", "post-tool")
            return dict(entry)

    def failed(self, key: str, reason: str, by: str = "post-tool-failure") -> dict:
        with self.transaction() as state:
            entry = state["checkpoints"].get(key)
            if entry is None:
                raise CheckpointError("Unknown checkpoint")
            if entry["status"] in {"saved", "dismissed"}:
                raise CheckpointError("Terminal checkpoint cannot fail again")
            self._history(entry, "failed", by, str(reason)[:300])
            return dict(entry)

    def reported_by_model(self, key: str, ref: str | None = None) -> dict:
        with self.transaction() as state:
            entry = state["checkpoints"].get(key)
            if entry is None or entry["status"] in {"saved", "dismissed"}:
                raise CheckpointError("Unknown or terminal checkpoint")
            if ref is not None:
                entry["note_ref"] = ref
            self._history(entry, "reported_by_model", "model-report")
            return dict(entry)

    def should_block_stop(self, session_id: str) -> dict | None:
        with self.transaction() as state:
            candidates = sorted(
                (x for x in state["checkpoints"].values()
                 if x["session_id"] == session_id and x["status"] in UNFINISHED
                 and not x["stop_blocked"]),
                key=lambda x: (x["created"], x["seq"]),
            )
            if not candidates:
                return None
            entry = candidates[0]
            entry["stop_blocked"] = True
            entry["updated"] = ISO()
            return dict(entry)

    def retries(self, project: str | None, current_session: str, limit: int = 5) -> list[dict]:
        if not project:
            return []
        state = self.snapshot()
        return [
            x for x in sorted(state["checkpoints"].values(), key=lambda x: (x["created"], x["seq"]))
            if x["project"] == project and x["session_id"] != current_session
            and x["status"] in UNFINISHED
        ][:limit]

    def register_session(self, session_id: str, cwd: str, transcript_path: str | None,
                         project: str | None) -> dict:
        if not session_id or not cwd:
            raise CheckpointError("Session ID and cwd are required")
        with self.transaction() as state:
            session = state["open_sessions"].get(session_id)
            if session is None:
                session = {
                    "session_id": session_id, "cwd": cwd,
                    "transcript_path": transcript_path, "project": project,
                    "started": ISO(), "last_seen": ISO(), "ended": False,
                    "last_capture_offset": 0,
                }
                state["open_sessions"][session_id] = session
            else:
                # Prevent a second agent from silently reassigning the session.
                if session["project"] != project and session["project"] is not None:
                    raise CheckpointError("Session project conflict")
                session["last_seen"] = ISO()
                if transcript_path:
                    session["transcript_path"] = transcript_path
            return dict(session)

    def get(self, key: str) -> dict:
        state = self.snapshot()
        entry = state["checkpoints"].get(key)
        if entry is None:
            raise CheckpointError("Unknown checkpoint")
        return dict(entry)

    def session(self, session_id: str) -> dict | None:
        entry = self.snapshot()["open_sessions"].get(session_id)
        return dict(entry) if entry else None

    def set_capture(self, key: str, capture: str, complete: bool,
                    material: list[str], next_offset: int | None = None) -> dict:
        if capture != "ok" and capture != "partial" and not capture.startswith("failed:"):
            raise CheckpointError("Invalid capture status")
        if not isinstance(material, list) or not all(isinstance(p, str) for p in material):
            raise CheckpointError("Invalid material paths")
        with self.transaction() as state:
            entry = state["checkpoints"].get(key)
            if entry is None or entry["status"] != "pending":
                raise CheckpointError("Checkpoint not pending")
            entry["capture"] = capture
            entry["complete"] = bool(complete)
            entry["material"] = material
            entry["updated"] = ISO()
            session = state["open_sessions"].get(entry["session_id"])
            if session is not None and next_offset is not None and capture in {"ok", "partial"}:
                session["last_capture_offset"] = max(session.get("last_capture_offset", 0), next_offset)
                session["last_seen"] = ISO()
            return dict(entry)

    def end_session(self, session_id: str) -> None:
        with self.transaction() as state:
            session = state["open_sessions"].get(session_id)
            if session is not None:
                session["ended"] = True
                session["last_seen"] = ISO()

    def pending_for_session(self, session_id: str) -> list[dict]:
        entries = self.snapshot()["checkpoints"].values()
        return sorted([dict(e) for e in entries if e["session_id"] == session_id
                       and e["status"] in UNFINISHED],
                      key=lambda e: (e["created"], e["seq"]))

    def unassigned(self, limit: int = 5) -> list[dict]:
        entries = self.snapshot()["checkpoints"].values()
        return sorted([dict(e) for e in entries if e.get("project") is None
                       and e["status"] in UNFINISHED],
                      key=lambda e: (e["created"], e["seq"]))[:limit]

    def terminal_by_user(self, key: str, action: str) -> dict:
        if action not in {"saved", "dismissed"}:
            raise CheckpointError("Invalid user action")
        with self.transaction() as state:
            entry = state["checkpoints"].get(key)
            if entry is None or entry["status"] in {"saved", "dismissed"}:
                raise CheckpointError("Checkpoint already terminal or unknown")
            self._history(entry, action, "user-confirm")
            return dict(entry)

    def status(self) -> dict:
        state = self.snapshot()
        counts: dict[str, int] = {}
        for entry in state["checkpoints"].values():
            counts[entry["status"]] = counts.get(entry["status"], 0) + 1
        recent = sorted(state["checkpoints"].values(), key=lambda x: x["updated"], reverse=True)[:10]
        return {
            "counts": counts, "open_sessions": len(state["open_sessions"]),
            "latest": [{k: e.get(k) for k in ("ck", "session_id", "status", "project", "created", "updated")}
                       for e in recent],
            "corrupt_backup": self.last_corrupt_backup,
        }
