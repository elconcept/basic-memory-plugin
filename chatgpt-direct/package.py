#!/usr/bin/env python3
"""Package eight ChatGPT web-compatible Basic Memory plugins without duplicate MCP servers."""
from pathlib import Path
from zipfile import ZipFile, ZIP_DEFLATED
import json

ROOT = Path(__file__).resolve().parent
DEST = ROOT / "dist"
DEST.mkdir(exist_ok=True)
APP_ID = "asdk_app_6afb2453a9748191a6865e06f09983f0"
NAMES = ("bm-orient", "bm-remember", "bm-decide", "bm-checkpoint",
         "bm-share", "bm-writing", "bm-status", "bm-setup")

for name in NAMES:
    source = ROOT / name
    manifest = json.loads((source / "plugin.json").read_text(encoding="utf-8"))
    app = json.loads((source / ".app.json").read_text(encoding="utf-8"))
    assert manifest["name"] == name, name
    assert manifest["extensions"]["com.openai"]["apps"] == "./.app.json", name
    assert any(v["id"] == APP_ID for v in app["apps"].values()), name
    assert (source / "skills" / name / "SKILL.md").is_file(), name
    assert (source / "skills" / name / "agents" / "openai.yaml").is_file(), name
    assert len(list(source.glob("skills/*/SKILL.md"))) == 1, name
    assert not (source / "mcp.json").exists(), name
    assert not (source / ".mcp.json").exists(), name
    legacy = json.loads((source / ".codex-plugin/plugin.json").read_text(encoding="utf-8"))
    assert legacy.get("apps") == "./.app.json", name
    assert "mcpServers" not in legacy, name

    archive = DEST / (name + ".zip")
    with ZipFile(archive, "w", ZIP_DEFLATED) as z:
        for path in sorted(source.rglob("*")):
            if path.is_file():
                z.write(path, name + "/" + path.relative_to(source).as_posix())
    with ZipFile(archive) as z:
        assert len([p for p in z.namelist() if p.endswith("/SKILL.md")]) == 1, name
        assert not any(p.endswith("mcp.json") for p in z.namelist()), name
    print(name, archive)
