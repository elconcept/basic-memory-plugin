#!/usr/bin/env python3
"""Build the eight standalone ChatGPT Basic Memory plugins from their source files."""
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile
import json

root = Path(__file__).resolve().parent
dest = root / "dist"
dest.mkdir(exist_ok=True)
names = ("bm-orient", "bm-remember", "bm-decide", "bm-checkpoint",
         "bm-share", "bm-writing", "bm-status", "bm-setup")
for name in names:
    source = root / name
    manifest = json.loads((source / "plugin.json").read_text(encoding="utf-8"))
    mcp = json.loads((source / "mcp.json").read_text(encoding="utf-8"))
    assert manifest["name"] == name
    assert mcp["mcpServers"]["basic-memory"]["url"] == "https://bm.xlap.pl/mcp"
    assert (source / "skills" / name / "SKILL.md").is_file()
    archive = dest / (name + ".zip")
    with ZipFile(archive, "w", ZIP_DEFLATED) as z:
        for p in sorted(source.rglob("*")):
            if p.is_file():
                z.write(p, f"{name}/{p.relative_to(source)}")
    print(f"{name}: {archive}")
