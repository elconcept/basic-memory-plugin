"""F1b lifecycle contract tests. No external services or real user transcripts."""
import json
import os
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from src.hooks.adapter import Adapter, _ref, settings
from src.hooks.state_store import StateStore


class AdapterTests(unittest.TestCase):
    def setUp(self):
        self.temp = TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.store = StateStore(self.root / "state")
        self.config = dict(
            primaryProject="proj-a", allowedProjects=["proj-a", "main"],
            checkpointOnCompact=True, checkpointOnSessionEnd=True,
            sessionEndMinTurns=3, materialMaxBytes=4096, materialMaxParts=2,
            captureFolder="sessions", orientOnStart=True,
        )
        self.adapter = Adapter(self.store, "claude", self.config)
        self.transcript = self.root / "conversation.jsonl"
        self.transcript.write_text("\n".join(json.dumps({
            "type": "user", "message": {"role": "user", "content": f"Decyzja D{i}: ustalono krok {i}."}
        }) for i in range(4)) + "\n")
        self.event = {"session_id": "session-one", "cwd": str(self.root),
                      "transcript_path": str(self.transcript)}

    def test_full_precompact_readback_same_ref_and_project(self):
        ck = self.adapter.pre_compact(self.event)["ck"]
        entry = self.store.get(ck)
        self.assertEqual(entry["status"], "pending")
        self.assertEqual(entry["project"], "proj-a")
        self.assertTrue(entry["material"])
        self.assertEqual(os.stat(entry["material"][0]).st_mode & 0o777, 0o600)
        write = {
            "tool_name": "mcp__plugin_basic-memory-nas_basic-memory__bm_write",
            "tool_input": {"project": "proj-a", "content": f"checkpoint_key: {ck}"},
            "tool_response": {"id": "notes/verify-1", "content": [{"type": "text", "text": "ok"}]},
        }
        result = self.adapter.post_tool(write)
        self.assertEqual(result["status"], "written")
        read = {"tool_name": "bm_read", "tool_input": {"project": "proj-a", "identifier": "notes/verify-1"},
                "tool_response": {"content": [{"type": "text", "text": f"# Note\ncheckpoint_key: {ck}\n"}]}}
        self.assertEqual(self.adapter.post_tool(read)["status"], "saved")
        self.assertIsNone(self.adapter.stop(self.event))

    def test_wrong_project_and_fake_note_ref_do_not_save(self):
        ck = self.adapter.pre_compact(self.event)["ck"]
        self.adapter.post_tool({
            "tool_name": "bm_write",
            "tool_input": {"project": "main", "content": f"checkpoint_key: {ck}"},
            "tool_response": {"id": "notes/a", "content": "ok"},
        })
        self.assertEqual(self.store.get(ck)["status"], "pending")
        self.adapter.post_tool({
            "tool_name": "bm_write",
            "tool_input": {"project": "proj-a", "content": f"checkpoint_key: {ck}"},
            "tool_response": {"id": "notes/a", "content": "ok"},
        })
        self.adapter.post_tool({
            "tool_name": "bm_read",
            "tool_input": {"project": "proj-a", "identifier": "notes/a"},
            "tool_response": {"content": "checkpoint_key: ck-0000000000000000"},
        })
        self.assertEqual(self.store.get(ck)["status"], "written")
        one = self.adapter.stop(self.event)
        self.assertEqual(one["decision"], "block")
        self.assertIsNone(self.adapter.stop(self.event))

    def test_tool_failure_and_report_never_claim_saved(self):
        ck = self.adapter.pre_compact(self.event)["ck"]
        self.adapter.post_tool({"tool_name": "bm_write", "tool_input": {
            "project": "proj-a", "content": f"checkpoint_key: {ck}"}, "error": "blocked"}, failure=True)
        self.assertEqual(self.store.get(ck)["status"], "failed")
        self.store.reported_by_model(ck, "declared/ref")
        self.assertEqual(self.store.get(ck)["status"], "reported_by_model")

    def test_compact_fallback_and_unassigned_checkpoint(self):
        unassigned = Adapter(self.store, "claude", dict(self.config, primaryProject=None))
        obj = unassigned.session_start(dict(self.event, source="compact"))
        self.assertIn("UNASSIGNED", obj["hookSpecificOutput"]["additionalContext"])
        self.assertEqual(self.store.status()["counts"], {"pending": 1})
        self.assertEqual(self.store.retries("proj-a", "other"), [])
        self.assertEqual(self.store.get(self.store.unassigned()[0]["ck"])["capture"],
                         "failed:missing_precompact")

    def test_session_end_threshold_and_cursor(self):
        obj = self.adapter.session_end(self.event)
        self.assertIsNotNone(obj)
        self.assertEqual(obj["trigger"], "session_end")
        self.assertTrue(self.store.session("session-one")["ended"])
        second = self.adapter.session_end(self.event)
        self.assertIsNone(second)

    def test_settings_precedence_and_no_fallback_project(self):
        home = self.root / "home"
        (home / ".claude").mkdir(parents=True)
        (self.root / ".claude").mkdir()
        (home / ".claude/settings.json").write_text(json.dumps({"basicMemory": {"primaryProject": "main"}}))
        (self.root / ".claude/settings.json").write_text(json.dumps({"basicMemory": {"primaryProject": "proj-a"}}))
        self.assertEqual(settings(self.root, "claude", {"HOME": str(home)})["primaryProject"], "proj-a")
        self.assertEqual(settings(self.root / "unused", "codex", {"HOME": str(home)})["primaryProject"], "main")

    def test_only_structured_ref_is_accepted(self):
        self.assertIsNone(_ref({"content": [{"type": "text", "text": "Saved! id notes/abc"}]}))
        self.assertEqual(_ref({"content": [{"type": "text", "text": '{"permalink":"notes/abc"}'}]}), "notes/abc")


if __name__ == "__main__":
    unittest.main()
