"""All tests use synthetic fixture records, not private transcripts."""
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from src.hooks.capture import materialize, parse_transcript


class CaptureTests(unittest.TestCase):
    def setUp(self):
        self.dir = TemporaryDirectory()
        self.addCleanup(self.dir.cleanup)
        self.path = Path(self.dir.name) / "transcript.jsonl"

    def write(self, *items):
        self.path.write_text("".join(json.dumps(i, ensure_ascii=False) + "\n" for i in items))

    def test_claude_text_and_tool_output_exclusion(self):
        self.write(
            {"type": "user", "message": {"role": "user", "content": "Ustalono: repo bez sekretów"}},
            {"type": "assistant", "message": {"role": "assistant", "content": [
                {"type": "text", "text": "Decyzja D7: nie pobierać dużych plików."},
                {"type": "tool_use", "name": "Write", "input": {"file_path": "/repo/doc.md", "api_key": "TOKEN_NEVER_COPY"}},
                {"type": "thinking", "thinking": "PRIVATE_REASONING"}]}},
            {"type": "user", "message": {"role": "user", "content": [{"type": "tool_result", "content": "PRIVATE_TOOL_OUTPUT"}]}},
            {"type": "assistant", "isMeta": True, "message": {"role": "assistant", "content": "META_MESSAGE"}},
        )
        t = parse_transcript(self.path)
        self.assertEqual(t.recognized, 2)
        m = materialize(t, {"project": "main"}, max_bytes=800, max_parts=4)
        s = "".join(m.parts)
        self.assertIn("Decyzja D7", s)
        self.assertIn("Write", s)
        self.assertIn("/repo/doc.md", s)
        for disallowed in ("TOKEN_NEVER_COPY", "PRIVATE_REASONING", "PRIVATE_TOOL_OUTPUT", "META_MESSAGE"):
            self.assertNotIn(disallowed, s)

    def test_codex_synthetic_boundary(self):
        self.write(
            {"type": "response_item", "payload": {"type": "message", "role": "user", "content": [{"type": "input_text", "text": "Earlier"}]}},
            {"type": "event_msg", "payload": {"type": "compaction_boundary"}},
            {"type": "response_item", "payload": {"type": "message", "role": "assistant", "content": [{"type": "output_text", "text": "Decision agreed"}]}},
        )
        t = parse_transcript(self.path, use_last_boundary=True)
        self.assertTrue(t.boundary)
        self.assertEqual(t.turns, (("assistant", "Decision agreed"),))

    def test_truncation_never_claims_complete(self):
        self.write({"type": "assistant", "message": {"role": "assistant", "content": "Decyzja o projekcie łódź " * 200}})
        t = parse_transcript(self.path)
        m = materialize(t, {"project": "main"}, max_bytes=512, max_parts=1)
        self.assertFalse(m.complete)
        self.assertTrue(any(m.omitted.values()))
        self.assertLessEqual(len(m.parts[0].encode()), 512)

    def test_fail_closed_for_unknown_and_missing(self):
        self.path.write_text("not JSON\n{}\n")
        self.assertEqual(parse_transcript(self.path).failure, "unknown_format")
        self.assertEqual(parse_transcript(None).failure, "no_transcript_path")
        self.assertEqual(parse_transcript(self.path.parent / "missing").failure, "unreadable")

    def test_offset_and_symlink_guard(self):
        self.write({"type": "user", "message": {"role": "user", "content": "First"}})
        old = parse_transcript(self.path)
        with self.path.open("a") as fp:
            fp.write(json.dumps({"type": "assistant", "message": {"role": "assistant", "content": "Second"}}) + "\n")
        self.assertEqual(parse_transcript(self.path, old.next_offset).turns, (("assistant", "Second"),))
        link = self.path.parent / "link"
        link.symlink_to(self.path)
        self.assertEqual(parse_transcript(link).failure, "unreadable")


if __name__ == "__main__":
    unittest.main()
