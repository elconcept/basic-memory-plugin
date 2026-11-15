#!/usr/bin/env python3
"""Validate and package the account-published ChatGPT portable plugin. Export only."""
from pathlib import Path
import argparse
import hashlib
import json
import zipfile

def main():
    p = argparse.ArgumentParser()
    p.add_argument("--source", default="chatgpt")
    p.add_argument("--zip", required=True)
    p.add_argument("--metadata", required=True)
    args = p.parse_args()
    source = Path(args.source)
    manifest = json.loads((source / "plugin.json").read_text(encoding="utf-8"))
    mcp = json.loads((source / "mcp.json").read_text(encoding="utf-8"))
    assert manifest["$schema"] == "https://agent-plugins.org/schemas/1.0.0/plugin.schema.json"
    assert manifest["name"] == "basic-memory-nas"
    assert mcp["$schema"] == "https://agent-plugins.org/schemas/1.0.0/mcp.schema.json"
    server = mcp["mcpServers"]["basic-memory"]
    assert server["type"] == "streamable-http" and server["url"] == "https://bm.xlap.pl/mcp"
    assert server["extensions"]["com.openai"]["auth"]["type"] == "oauth"
    assert (source / "skills/basic-memory-nas/SKILL.md").read_text(encoding="utf-8").startswith("---\nname: basic-memory-nas\n")
    allowed = {".json", ".yaml", ".md", ".svg", ".png", ".jpg", ".webp"}
    files = [x for x in sorted(source.rglob("*")) if x.is_file()]
    assert len(files) >= 4
    for f in files:
        assert not f.is_symlink() and f.suffix in allowed and f.stat().st_size < 1024 * 1024
        assert ".env" not in f.name.lower() and "secret" not in f.name.lower()
    dest = Path(args.zip)
    dest.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(dest, "w", compression=zipfile.ZIP_DEFLATED) as z:
        for f in files:
            z.write(f, f.relative_to(source))
    with zipfile.ZipFile(dest) as z:
        assert z.testzip() is None
        assert set(z.namelist()) == {f.relative_to(source).as_posix() for f in files}
    meta = {
        "name": manifest["name"],
        "version": manifest["version"],
        "source_commit": "",
        "sha256": hashlib.sha256(dest.read_bytes()).hexdigest(),
        "file_count": len(files),
        "mcp_server": server["url"],
        "cloud_published": False,
        "reason": "GitHub Release is an export; ChatGPT Plugin Creator requires separate authenticated publication."
    }
    Path(args.metadata).write_text(json.dumps(meta, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(meta))

if __name__ == "__main__":
    main()
