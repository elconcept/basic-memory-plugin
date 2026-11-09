"""Generator safety, target separation and determinism — no network calls."""
import json
import tempfile
import unittest
from pathlib import Path

from scripts.build import build, select_skills

EXCLUDED = ["memory-ci-capture", "memory-agents", "memory-quest", "memory-literary-analysis"]


class BuildTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        root = Path(self.temp.name)
        self.source = root / "source"
        self.out = root / "out"
        self.overrides = root / "overrides"
        self.config = root / "config.json"
        self.config.write_text(json.dumps({
            "plugin_name": "basic-memory-nas", "mcp_server_key": "basic-memory",
            "mcp_url": "https://bm.xlap.pl/mcp", "upstream_sha": "a" * 40,
            "version": "1.0.0", "exclude_skills": EXCLUDED
        }))
        for base, prefix, count in [
            ("skills", "memory", 16),
            ("plugins/claude-code/skills", "bm", 8),
            ("plugins/codex/skills", "bm", 8),
        ]:
            for n in range(count):
                name = f"{prefix}-test{n}"
                p = self.source / base / name / "SKILL.md"
                p.parent.mkdir(parents=True, exist_ok=True)
                p.write_text("---\nname: " + name + "\ndescription: Test skill\n---\n\nUse bm_search.")

    def test_claude_only_no_local_daemon(self):
        r = build(self.source, self.out, self.overrides, self.config, "claude", False, None)
        self.assertEqual(r["targets"], ["claude"])
        self.assertTrue((self.out / "claude/.mcp.json").exists())
        self.assertFalse((self.out / "openai").exists())
        self.assertFalse((self.out / "claude/hooks").exists())
        self.assertEqual(build(self.source, self.out, self.overrides, self.config, "claude", True, None)["content_sha256"], r["content_sha256"])

    def test_check_detects_drift(self):
        build(self.source, self.out, self.overrides, self.config, "claude", False, None)
        (self.out / "claude/skills/memory-test0/SKILL.md").write_text("corrupted")
        with self.assertRaisesRegex(ValueError, "differ"):
            build(self.source, self.out, self.overrides, self.config, "claude", True, None)

    def test_distinct_codex_native_skills_and_oauth(self):
        file = self.source / "plugins/codex/skills/bm-test0/SKILL.md"
        file.write_text(file.read_text() + "\nCodex native only.")
        r = build(self.source, self.out, self.overrides, self.config, "openai", False, "M")
        self.assertEqual(r["targets"], ["openai"])
        self.assertIn("Codex native only", (self.out / "openai/skills/bm-test0/SKILL.md").read_text())
        self.assertEqual(json.loads((self.out / "openai/mcp.json").read_text())["mcpServers"]["basic-memory"]["type"], "streamable-http")
        self.assertFalse((self.out / "openai/.app.json").exists())

    def test_openai_approval_gates(self):
        with self.assertRaisesRegex(ValueError, "gated"):
            build(self.source, self.out, self.overrides, self.config, "openai", False, None)
        with self.assertRaisesRegex(ValueError, "verified"):
            build(self.source, self.out, self.overrides, self.config, "openai", False, "R")

    def test_forbidden_local_install(self):
        file = self.source / "plugins/claude-code/skills/bm-test0/SKILL.md"
        file.write_text(file.read_text() + "\nnpx skills add something")
        with self.assertRaisesRegex(ValueError, "Blocked"):
            build(self.source, self.out, self.overrides, self.config, "claude", False, None)

    def test_schema_name_drift_stops(self):
        file = self.source / "skills/memory-test0/SKILL.md"
        file.write_text(file.read_text().replace("memory-test0", "memory-someother"))
        with self.assertRaisesRegex(ValueError, "skill name"):
            build(self.source, self.out, self.overrides, self.config, "claude", False, None)

    def test_all_requires_verified_openai(self):
        with self.assertRaises(ValueError):
            build(self.source, self.out, self.overrides, self.config, "all", False, None)


if __name__ == "__main__":
    unittest.main()
