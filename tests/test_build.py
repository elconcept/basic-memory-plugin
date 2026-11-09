"""Generator safety, upstream parity and determinism — no network calls."""
import hashlib
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from scripts.build import build

EXCLUDED = ["memory-ci-capture", "memory-agents", "memory-quest", "memory-literary-analysis"]


class BuildTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        root = Path(self.temp.name)
        self.source = root / "source"
        self.out = root / "out"
        self.overrides = root / "overrides" / "skills"
        self.config = root / "config.json"
        self.config.write_text(json.dumps({
            "plugin_name": "basic-memory-nas", "mcp_server_key": "basic-memory",
            "mcp_url": "https://bm.xlap.pl/mcp", "upstream_sha": "a" * 40,
            "version": "2.0.0", "exclude_skills": EXCLUDED
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
        for rel in ["plugins/claude-code/schemas/decision.md", "plugins/claude-code/output-styles/basic-memory.md",
                    "plugins/codex/schemas/decision.md"]:
            p = self.source / rel
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text("---\ntitle: x\n---\nSee /basic-memory:bm-setup.\n")

    def skills(self, pkg):
        return sorted(p.name for p in (self.out / pkg / "skills").iterdir())

    def test_core_mirrors_upstream_native_plugin(self):
        r = build(self.source, self.out, self.overrides, self.config, "claude", False, None)
        self.assertEqual(r["packages"], ["claude", "claude-extras"])
        self.assertEqual(self.skills("claude"), [f"bm-test{n}" for n in range(8)])
        self.assertTrue((self.out / "claude/schemas/decision.md").is_file())
        self.assertTrue((self.out / "claude/output-styles/basic-memory.md").is_file())
        self.assertIn("/basic-memory-nas:bm-setup", (self.out / "claude/schemas/decision.md").read_text())
        self.assertTrue((self.out / "claude/.mcp.json").exists())
        self.assertFalse((self.out / "claude/src").exists())
        self.assertFalse((self.out / "openai").exists())
        manifest = json.loads((self.out / "claude/hooks/hooks.json").read_text())
        self.assertEqual(set(manifest["hooks"]), {"SessionStart"})
        self.assertEqual(build(self.source, self.out, self.overrides, self.config, "claude", True, None)["content_sha256"],
                         r["content_sha256"])

    def test_extras_are_separate_and_mcp_free(self):
        build(self.source, self.out, self.overrides, self.config, "claude", False, None)
        self.assertEqual(len(self.skills("claude-extras")), 16)
        self.assertFalse(any(s.startswith("bm-") for s in self.skills("claude-extras")))
        self.assertFalse((self.out / "claude-extras/.mcp.json").exists())
        self.assertFalse((self.out / "claude-extras/hooks").exists())
        meta = json.loads((self.out / "claude-extras/.claude-plugin/plugin.json").read_text())
        self.assertEqual(meta["name"], "basic-memory-nas-extras")

    def test_missing_schemas_stop_build(self):
        (self.source / "plugins/claude-code/schemas/decision.md").unlink()
        (self.source / "plugins/claude-code/schemas").rmdir()
        with self.assertRaisesRegex(ValueError, "schemas"):
            build(self.source, self.out, self.overrides, self.config, "claude", False, None)

    def test_skill_count_drift_stops(self):
        p = self.source / "plugins/claude-code/skills/bm-new/SKILL.md"
        p.parent.mkdir(parents=True)
        p.write_text("---\nname: bm-new\ndescription: x\n---\n")
        with self.assertRaisesRegex(ValueError, "core skill count"):
            build(self.source, self.out, self.overrides, self.config, "claude", False, None)

    def test_check_detects_drift(self):
        build(self.source, self.out, self.overrides, self.config, "claude", False, None)
        (self.out / "claude-extras/skills/memory-test0/SKILL.md").write_text("corrupted")
        with self.assertRaisesRegex(ValueError, "differ"):
            build(self.source, self.out, self.overrides, self.config, "claude", True, None)

    def test_openai_core_and_oauth(self):
        file = self.source / "plugins/codex/skills/bm-test0/SKILL.md"
        file.write_text(file.read_text() + "\nCodex native only.")
        r = build(self.source, self.out, self.overrides, self.config, "openai", False, "M")
        self.assertEqual(r["packages"], ["openai", "openai-extras"])
        self.assertIn("Codex native only", (self.out / "openai/skills/bm-test0/SKILL.md").read_text())
        self.assertTrue((self.out / "openai/schemas/decision.md").is_file())
        self.assertEqual(json.loads((self.out / "openai/mcp.json").read_text())["mcpServers"]["basic-memory"]["type"],
                         "streamable-http")
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

    def test_patches_preserve_upstream_and_fail_on_anchor_drift(self):
        p = self.source / "plugins/claude-code/skills/bm-test0/SKILL.md"
        p.write_text(p.read_text() + "\nRemote context should not use LOCAL_SETUP.")
        patch = self.overrides.parent.parent / "patches" / "skills" / "bm-test0" / "claude.json"
        patch.parent.mkdir(parents=True)
        original = p.read_bytes()
        sha = hashlib.sha1(b"blob " + str(len(original)).encode() + b"\0" + original).hexdigest()
        patch.write_text(json.dumps({"source_blob_sha": sha, "replacements": [{"old": "LOCAL_SETUP", "new": "REMOTE_MCP_ONLY"}]}))
        build(self.source, self.out, self.overrides, self.config, "claude", False, None)
        self.assertIn("REMOTE_MCP_ONLY", (self.out / "claude/skills/bm-test0/SKILL.md").read_text())
        p.write_text(p.read_text().replace("LOCAL_SETUP", "something else"))
        with self.assertRaisesRegex(ValueError, "SKILL.md changed"):
            build(self.source, self.out, self.overrides, self.config, "claude", False, None)

    def test_schema_name_drift_stops(self):
        file = self.source / "skills/memory-test0/SKILL.md"
        file.write_text(file.read_text().replace("memory-test0", "memory-someother"))
        with self.assertRaisesRegex(ValueError, "skill name"):
            build(self.source, self.out, self.overrides, self.config, "claude", False, None)

    def test_all_requires_verified_openai(self):
        with self.assertRaises(ValueError):
            build(self.source, self.out, self.overrides, self.config, "all", False, None)


class SessionStartHookTests(unittest.TestCase):
    HOOK = Path(__file__).resolve().parents[1] / "src/hooks/session_start.py"

    def run_hook(self, cwd: Path, home: Path, event=None):
        env = {k: v for k, v in os.environ.items() if k != "CLAUDE_CONFIG_DIR"}
        env["HOME"] = str(home)
        stdin = json.dumps(event if event is not None else {"cwd": str(cwd)})
        r = subprocess.run([sys.executable, str(self.HOOK)], input=stdin, capture_output=True,
                           text=True, env=env, timeout=10)
        self.assertEqual(r.returncode, 0, r.stderr)
        return json.loads(r.stdout)["hookSpecificOutput"]["additionalContext"]

    def test_unconfigured_nudges_setup_without_default_project(self):
        with tempfile.TemporaryDirectory() as d:
            text = self.run_hook(Path(d), Path(d))
            self.assertIn("bm-setup", text)
            self.assertNotIn("main", text)

    def test_project_settings_override_user_settings(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            (root / ".claude").mkdir()
            (root / ".claude/settings.json").write_text(json.dumps(
                {"basicMemory": {"primaryProject": "user-level", "captureFolder": "cp"}}))
            proj = root / "repo"
            (proj / ".claude").mkdir(parents=True)
            (proj / ".claude/settings.local.json").write_text(json.dumps(
                {"basicMemory": {"primaryProject": "work", "placementConventions": "decisions/ for decisions"}}))
            text = self.run_hook(proj, root)
            self.assertIn("**Project:** work", text)
            self.assertIn("`cp/`", text)
            self.assertIn("decisions/ for decisions", text)

    def test_garbage_input_never_breaks_session(self):
        with tempfile.TemporaryDirectory() as d:
            r = subprocess.run([sys.executable, str(self.HOOK)], input="not json", capture_output=True,
                               text=True, env={"HOME": d}, timeout=10, cwd=d)
            self.assertEqual(r.returncode, 0)


if __name__ == "__main__":
    unittest.main()
