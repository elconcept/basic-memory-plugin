#!/usr/bin/env python3
"""Build a deterministic, MCP-free ChatGPT plugin archive from generated OpenAI assets.

This is an export artifact for a publisher. It does not register a plugin in ChatGPT.
Never execute upstream code or include local MCP bindings.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import re
import zipfile

SCHEMA = "https://agent-plugins.org/schemas/1.0.0/plugin.schema.json"
ALLOWED_EXTENSIONS = {".md", ".json", ".yaml", ".yml", ".svg", ".txt", ".png", ".jpg", ".jpeg", ".webp"}
BLOCKED_NAMES = {"mcp.json", ".mcp.json", ".app.json"}
MIN_SKILLS = 8


def package(source: Path, destination: Path, metadata: Path | None, source_sha: str) -> dict:
    source = source.resolve()
    portable = json.loads((source / "plugin.json").read_text("utf-8"))
    legacy = json.loads((source / ".codex-plugin/plugin.json").read_text("utf-8"))
    assert portable["$schema"] == SCHEMA, "Unsupported portable plugin manifest"
    assert portable["name"] == legacy["name"] == "basic-memory-nas", "Plugin identity mismatch"
    assert portable["version"] == legacy["version"], "Plugin version mismatch"
    assert legacy["skills"] == "./skills", "Skill root changed"
    assert not any("mcp" in k.lower() or "apps" in k.lower() for k in portable), "MCP/app binding found"
    assert not any("mcp" in k.lower() or "apps" in k.lower() for k in legacy), "MCP/app binding found"

    all_files = []
    for path in sorted(source.rglob("*")):
        if path.is_symlink():
            raise ValueError(f"Symlink forbidden: {path}")
        if not path.is_file():
            continue
        rel = path.relative_to(source)
        if any(part.startswith(".") for part in rel.parts[:-1] if part != ".codex-plugin"):
            raise ValueError(f"Unexpected hidden directory: {rel}")
        if path.name.lower() in BLOCKED_NAMES:
            raise ValueError(f"Bundled MCP or App binding forbidden: {rel}")
        if path.name != "LICENSE" and path.suffix.lower() not in ALLOWED_EXTENSIONS:
            raise ValueError(f"Unexpected file: {rel}")
        if path.stat().st_size > 1024 * 1024:
            raise ValueError(f"Oversized file: {rel}")
        all_files.append((rel.as_posix(), path.read_bytes()))

    skills = [name for name, _ in all_files if re.fullmatch(r"skills/bm-[^/]+/SKILL\.md", name)]
    if len(skills) < MIN_SKILLS:
        raise ValueError(f"Expected >= {MIN_SKILLS} bm-* skills, found {len(skills)}")
    for filename, data in all_files:
        if filename in skills:
            content = data.decode("utf-8")
            expected_name = filename.split("/")[1]
            if not content.startswith("---\n") or not re.search(r"(?m)^name:\s*" + re.escape(expected_name) + r"\s*$", content) or not re.search(r"(?m)^description:\s*\S+", content):
                raise ValueError(f"Invalid SKILL.md frontmatter: {filename}")

    destination.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(destination, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for filename, data in all_files:
            info = zipfile.ZipInfo(filename, date_time=(1980, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o100644 << 16
            archive.writestr(info, data, compress_type=zipfile.ZIP_DEFLATED, compresslevel=9)
    with zipfile.ZipFile(destination) as archive:
        if archive.testzip() is not None:
            raise ValueError("ZIP checksum invalid")
        if set(archive.namelist()) != {name for name, _ in all_files}:
            raise ValueError("ZIP content drift")
    result = {
        "plugin": portable["name"],
        "version": portable["version"],
        "upstream_sha": source_sha,
        "skill_count": len(skills),
        "file_count": len(all_files),
        "zip_sha256": hashlib.sha256(destination.read_bytes()).hexdigest(),
        "mcp_bundled": False,
        "status": "export-only-not-cloud-published",
    }
    if metadata is not None:
        metadata.parent.mkdir(parents=True, exist_ok=True)
        metadata.write_text(json.dumps(result, ensure_ascii=False, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, default=Path("openai"))
    parser.add_argument("--zip", dest="destination", type=Path, required=True)
    parser.add_argument("--metadata", type=Path)
    parser.add_argument("--source-sha", default="")
    args = parser.parse_args()
    print(json.dumps(package(args.source, args.destination, args.metadata, args.source_sha)))
