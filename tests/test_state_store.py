"""Offline F1a checkpoint state transition regression tests."""
import json
import multiprocessing
import os
from pathlib import Path
import tempfile
import unittest

from src.hooks.state_store import StateStore, CheckpointError


class LedgerTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.path = Path(self.tmp.name) / "ledger"
        self.store = StateStore(self.path)

    def test_saved_needs_readback_same_ref_project_and_exact_line(self):
        entry = self.store.create("session-A", "auto", "claude", "legal", "ok", ["m.md"], True)
        ck = entry["ck"]
        self.store.written(ck, "legal", "notes/id-1")
        for args in [
            ("main", "notes/id-1", f"checkpoint_key: {ck}"),
            ("legal", "notes/id-2", f"checkpoint_key: {ck}"),
            ("legal", "notes/id-1", f"prefix checkpoint_key: {ck}"),
            ("legal", "notes/id-1", f"checkpoint_key: {ck}abc"),
        ]:
            with self.assertRaises(CheckpointError):
                self.store.readback(ck, *args)
        self.assertEqual(self.store.status()["counts"], {"written": 1})
        result = self.store.readback(ck, "legal", "notes/id-1", f"Title\ncheckpoint_key: {ck}\n")
        self.assertEqual(result["status"], "saved")
        self.assertEqual(result["history"][-1]["by"], "post-tool")

    def test_unassigned_never_enqueued_for_any_project(self):
        entry = self.store.create("s", "auto", "codex", None, "failed:missing_precompact")
        ck = entry["ck"]
        self.assertEqual(self.store.retries("legal", "another"), [])
        with self.assertRaises(CheckpointError):
            self.store.written(ck, "legal", "r")
        with self.assertRaises(CheckpointError):
            self.store.assign(ck, "legal", ["main"])
        self.store.assign(ck, "legal", ["legal", "main"])
        self.assertEqual([x["ck"] for x in self.store.retries("legal", "another")], [ck])
        self.assertEqual(self.store.retries("main", "another"), [])

    def test_report_model_never_saved(self):
        ck = self.store.create("s", "manual", "claude", "main", "ok")["ck"]
        self.store.reported_by_model(ck, "ref")
        self.assertEqual(self.store.status()["counts"], {"reported_by_model": 1})
        with self.assertRaises(CheckpointError):
            self.store.readback(ck, "main", "ref", f"checkpoint_key: {ck}")

    def test_stop_is_one_time_and_saved_excluded(self):
        a = self.store.create("s", "auto", "claude", "main", "ok")
        self.assertEqual(self.store.should_block_stop("s")["ck"], a["ck"])
        self.assertIsNone(self.store.should_block_stop("s"))
        self.store.written(a["ck"], "main", "ref")
        self.store.readback(a["ck"], "main", "ref", f"checkpoint_key: {a['ck']}")
        self.assertIsNone(self.store.should_block_stop("s"))

    def test_failed_then_retry_written(self):
        ck = self.store.create("session", "auto", "claude", "main", "partial")["ck"]
        self.store.failed(ck, "network unavailable")
        self.store.written(ck, "main", "new-id")
        self.assertEqual(self.store.status()["counts"], {"written": 1})

    def test_corrupt_state_kept_as_backup(self):
        self.store.state_path.write_bytes(b"{ incomplete")
        self.assertEqual(self.store.status()["counts"], {})
        self.assertTrue(list(self.path.glob("state.json.corrupt-*")))
        self.assertTrue((self.path / "state.json").is_file())

    def test_filesystem_modes(self):
        ck = self.store.create("a", "auto", "claude", "main", "ok")["ck"]
        self.assertEqual(os.stat(self.path).st_mode & 0o777, 0o700)
        self.assertEqual(os.stat(self.path / "state.json").st_mode & 0o777, 0o600)
        self.assertEqual(os.stat(self.path / "state.lock").st_mode & 0o777, 0o600)

    def test_multiple_checkpoints_distinct_and_ordered(self):
        a = self.store.create("s", "auto", "claude", "main", "ok")
        b = self.store.create("s", "session_end", "claude", "main", "ok")
        self.assertEqual([a["seq"], b["seq"]], [1, 2])
        self.assertNotEqual(a["ck"], b["ck"])
        self.assertEqual(self.store.retries("main", "other")[0]["ck"], a["ck"])


if __name__ == "__main__":
    unittest.main()
