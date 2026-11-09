"""Offline safety and determinism tests for upstream sync."""
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from scripts.sync_upstream import collect, synchronize

SHA1 = "a" * 40
SHA2 = "b" * 40


class SyncUpstreamTests(unittest.TestCase):
    def setUp(self):
        self.ctx = TemporaryDirectory()
        self.addCleanup(self.ctx.cleanup)
        self.root = Path(self.ctx.name)
        self.source = self.root / "upstream"
        self.dest = self.root / "snapshot"
        self.lock = self.root / "config" / "upstream.lock.json"
        self.report = self.root / "report.md"
        for p in (
            "skills/memory-foo/SKILL.md",
            "plugins/claude-code/skills/bm-foo/SKILL.md",
            "plugins/codex/skills/bm-foo/SKILL.md",
        ):
            dest = self.source / p
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_text(f"# {p}\n", encoding="utf-8")

    def test_initial_and_idempotent_sync(self):
        first = synchronize(self.source, self.dest, self.lock, SHA1, self.report)
        self.assertEqual(first["manifest"]["file_count"], 3)
        self.assertEqual(len(first["changes"]), 3)
        digest = first["manifest"]["snapshot_digest"]
        second = synchronize(self.source, self.dest, self.lock, SHA1, self.report)
        self.assertFalse(second["changes"])
        self.assertEqual(digest, second["manifest"]["snapshot_digest"])
        self.assertEqual(json.loads(self.lock.read_text())["upstream_sha"], SHA1)

    def test_updates_and_removes_stale_upstream_assets(self):
        synchronize(self.source, self.dest, self.lock, SHA1, self.report)
        p = self.source / "skills/memory-foo/reference.md"
        p.write_text("# New reference\n", encoding="utf-8")
        updated = synchronize(self.source, self.dest, self.lock, SHA2, self.report)
        self.assertTrue(any("reference.md" in s for s in updated["changes"]))
        p.unlink()
        synchronize(self.source, self.dest, self.lock, SHA2, self.report)
        self.assertFalse((self.dest / "skills/memory-foo/reference.md").exists())

    def test_evals_not_copied(self):
        p = self.source / "skills/memory-foo/evals/test.md"
        p.parent.mkdir(parents=True)
        p.write_text("Sensitive fixture", encoding="utf-8")
        self.assertFalse(any("/evals/" in p for p in collect(self.source)))

    def test_symlink_rejected(self):
        link = self.source / "skills/memory-foo/secret.md"
        link.symlink_to(self.source / "skills/memory-foo/SKILL.md")
        with self.assertRaises(ValueError):
            collect(self.source)


    def test_build_config_version_bumps_once_per_new_upstream(self):
        config = self.root / "config" / "build.json"
        config.parent.mkdir(parents=True, exist_ok=True)
        config.write_text(json.dumps({"upstream_sha": SHA1, "version": "2.0.0", "plugin_name": "basic-memory-nas"}))
        synchronize(self.source, self.dest, self.lock, SHA1, self.report, config)
        self.assertEqual(json.loads(config.read_text())["version"], "2.0.0")
        synchronize(self.source, self.dest, self.lock, SHA2, self.report, config)
        self.assertEqual(json.loads(config.read_text())["version"], "2.0.1")
        self.assertEqual(json.loads(config.read_text())["upstream_sha"], SHA2)
        synchronize(self.source, self.dest, self.lock, SHA2, self.report, config)
        self.assertEqual(json.loads(config.read_text())["version"], "2.0.1")

    def test_invalid_version_rejected_before_writes(self):
        config = self.root / "build.json"
        config.write_text(json.dumps({"upstream_sha": SHA1, "version": "foo"}))
        with self.assertRaisesRegex(ValueError, "Unsupported version"):
            synchronize(self.source, self.dest, self.lock, SHA2, self.report, config)
        self.assertFalse(self.dest.exists())

    def test_invalid_sha_rejected(self):
        with self.assertRaises(ValueError):
            synchronize(self.source, self.dest, self.lock, "not-a-sha", self.report)


if __name__ == "__main__":
    unittest.main()
