#!/usr/bin/env python3
"""Build reviewable, credential-free Basic Memory plugin candidates.

This is a packaging tool, not a Basic Memory fork. It never executes imported
upstream source and never accesses the NAS. Host-specific hooks and OAuth are
intentionally separate, gated tasks.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
import tempfile
from pathlib import Path

EXCLUDED = frozenset({"memory-ci-capture", "memory-agents", "memory-quest", "memory-literary-analysis"})
DENY = ("npx skills add", "bm install claude-code", "claude plugin marketplace add basicmachines-co", "cloud.basicmemory.com")
META_KEY = "basic-memory-nas"
PLUGIN_REPO = "https://github.com/elconcept/basic-memory-plugin"
OPENAI_SCHEMA = "https://agent-plugins.org/schemas/1.0.0/plugin.schema.json"
OPENAI_MCP_SCHEMA = "https://agent-plugins.org/schemas/1.0.0/mcp.schema.json"


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def json_bytes(value: object) -> bytes:
    return (json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode("utf-8")


def load_config(path: Path) -> dict:
    cfg = json.loads(path.read_text(encoding="utf-8"))
    if cfg.get("plugin_name") != META_KEY or cfg.get("mcp_server_key") != "basic-memory":
        raise ValueError("Unsupported plugin or MCP server identity")
    url = cfg.get("mcp_url", "")
    if not (isinstance(url, str) and url == "https://bm.xlap.pl/mcp"):
        raise ValueError("Unexpected MCP URL; manual review required")
    if set(cfg.get("exclude_skills", [])) != EXCLUDED:
        raise ValueError("Skill exclusion drift; review required")
    return cfg


def frontmatter(text: str, name: str) -> None:
    # Minimal contract without requiring PyYAML on an offline builder.
    if not text.startswith("---\n"):
        raise ValueError(f"Missing SKILL.md frontmatter: {name}")
    head = text.split("\n---\n", 1)[0]
    if not re.search(r"(?m)^name:\s*" + re.escape(name) + r"\s*$", head):
        raise ValueError(f"Missing or mismatched skill name: {name}")
    if not re.search(r"(?m)^description:\s*\S", head):
        raise ValueError(f"Missing description: {name}")


def skill_dirs(root: Path, prefix: str) -> list[Path]:
    if not root.is_dir():
        raise ValueError(f"Missing upstream root: {root}")
    dirs = sorted(p for p in root.iterdir() if p.is_dir() and p.name.startswith(prefix))
    if not dirs:
        raise ValueError(f"No {prefix} skills: {root}")
    return dirs


def read_skill(source: Path, override: Path | None, patch_file: Path, name: str, namespace: str) -> dict[str, bytes]:
    source_dir = source
    files: dict[str, bytes] = {}
    for f in sorted(source_dir.rglob("*")):
        if "evals" in f.relative_to(source_dir).parts:
            continue
        if f.is_symlink():
            raise ValueError(f"Upstream symlink rejected: {f}")
        if not f.is_file():
            continue
        rel = f.relative_to(source_dir).as_posix()
        if f.name == "SKILL.md" and override is not None and override.is_file():
            data = override.read_bytes()
        else:
            data = f.read_bytes()
        if f.suffix == ".md":
            text = data.decode("utf-8")
            if f.name == "SKILL.md" and patch_file.is_file():
                if override is not None and override.is_file():
                    raise ValueError(f"Override and patch conflict: {name}")
                document = json.loads(patch_file.read_text(encoding="utf-8"))
                if not isinstance(document, dict) or not isinstance(document.get("replacements"), list):
                    raise ValueError(f"Invalid patch document: {patch_file}")
                expected_blob = document.get("source_blob_sha")
                if not isinstance(expected_blob, str) or not re.fullmatch(r"[0-9a-f]{40}", expected_blob):
                    raise ValueError(f"Patch missing pinned upstream source blob: {patch_file}")
                upstream_content = (source / "SKILL.md").read_bytes()
                current_blob = hashlib.sha1(
                    b"blob " + str(len(upstream_content)).encode() + b"\0" + upstream_content
                ).hexdigest()
                if current_blob != expected_blob:
                    raise ValueError(f"Patched upstream SKILL.md changed: {name}")
                for replacement in document["replacements"]:
                    old, new = replacement["old"], replacement["new"]
                    if not old or text.count(old) != 1:
                        raise ValueError(f"Upstream patch anchor changed: {name} / {old[:60]!r}")
                    text = text.replace(old, new, 1)
            text = text.replace("/basic-memory:", "/basic-memory-nas:")
            text = text.replace("basic-memory:bm-", "basic-memory-nas:bm-")
            text = text.replace("codex:bm-", "basic-memory-nas:bm-")
            data = text.encode("utf-8")
        files[rel] = data
    if "SKILL.md" not in files:
        raise ValueError(f"Missing SKILL.md: {source}")
    parsed = files["SKILL.md"].decode("utf-8")
    frontmatter(parsed, name)
    for fname, data in files.items():
        if fname.endswith(".md"):
            for forbidden in DENY:
                if forbidden in data.decode("utf-8"):
                    raise ValueError(f"Blocked local-install/cloud instruction in {name}/{fname}: {forbidden}")
    return files


def select_skills(upstream: Path, overrides: Path, target: str) -> dict[str, bytes]:
    if target not in {"claude", "openai"}:
        raise ValueError(f"Unknown target: {target}")
    native_root = upstream / ("plugins/claude-code/skills" if target == "claude" else "plugins/codex/skills")
    roots = [(upstream / "skills", "memory-"), (native_root, "bm-")]
    files: dict[str, bytes] = {}
    count = 0
    for root, prefix in roots:
        for skill in skill_dirs(root, prefix):
            if skill.name in EXCLUDED:
                continue
            name = skill.name
            override_path = overrides / name / (target + ".md")
            if not override_path.is_file():
                override_path = overrides / name / "SKILL.md"
            patch = overrides.parent.parent / "patches" / "skills" / name / (target + ".json")
            if not patch.is_file():
                patch = overrides.parent.parent / "patches" / "skills" / name / "all.json"
            result = read_skill(skill, override_path, patch, name, target)
            for rel, data in result.items():
                key = f"skills/{name}/{rel}"
                if key in files:
                    raise ValueError(f"Duplicate skill: {name}")
                files[key] = data
            count += 1
    if count != 24:
        raise ValueError(f"Upstream skill count changed ({count} != 24); review required")
    return files


def local_hook_assets() -> dict[str, bytes]:
    """Package independently authored local adapters only; no upstream CLI code."""
    root = Path(__file__).resolve().parents[1]
    result = {"src/__init__.py": b"", "src/hooks/__init__.py": b""}
    for name in ("adapter.py", "capture.py", "state_store.py"):
        target = root / "src/hooks" / name
        if not target.is_file():
            raise ValueError(f"Local hook module missing: {name}")
        result[f"src/hooks/{name}"] = target.read_bytes()
    wrapper = (
        "from pathlib import Path\n"
        "import sys\n"
        "sys.path.insert(0, str(Path(__file__).resolve().parents[1]))\n"
        "from src.hooks.adapter import main\n"
        "if __name__ == '__main__':\n"
        "    sys.exit(main())\n"
    )
    result["hooks/bm_hook.py"] = wrapper.encode("utf-8")
    def command(verb: str) -> dict:
        return {"type": "command",
                "command": f'python3 "{chr(36)}{{CLAUDE_PLUGIN_ROOT}}/hooks/bm_hook.py" {verb} --harness claude',
                "timeout": 15}
    hook_events = {
        "SessionStart": [{"hooks": [command("session-start")]}],
        "PreCompact": [{"hooks": [command("pre-compact")]}],
        "PostToolUse": [{"matcher": r"mcp__.*__bm_(write|edit|read)",
                         "hooks": [command("post-tool")]}],
        "PostToolUseFailure": [{"matcher": r"mcp__.*__bm_(write|edit|read)",
                                "hooks": [command("post-tool-failure")]}],
        "SessionEnd": [{"hooks": [command("session-end")]}],
        "Stop": [{"hooks": [command("stop")]}],
    }
    result["hooks/hooks.json"] = json_bytes({
        "description": "Offline-only Basic Memory checkpoint control; writes/reads use MCP from the agent",
        "hooks": hook_events,
    })
    return result


def render(upstream: Path, overrides: Path, cfg: dict, target: str, version: str, openai_variant: str | None, app_id: str | None) -> dict[str, bytes]:
    assets = select_skills(upstream, overrides, target)
    assets["UPSTREAM_ATTRIBUTION.md"] = (
        "# Basic Memory upstream attribution\n\n"
        f"Upstream repository: https://github.com/basicmachines-co/basic-memory\n"
        f"Source revision: {cfg['upstream_sha']}\n\n"
        "This plugin is licensed under AGPL-3.0-or-later (see LICENSE). It "
        "includes skill content and other selected assets copied from upstream "
        "Basic Memory, which is licensed under AGPL-3.0-or-later; some upstream "
        "subcomponents additionally declare MIT. Upstream copyright notices are "
        "preserved.\n"
    ).encode()
    assets["LICENSE"] = (Path(__file__).resolve().parent.parent / "LICENSE").read_bytes()
    if target == "claude":
        assets[".claude-plugin/plugin.json"] = json_bytes({
            "name": META_KEY, "version": version,
            "description": "Self-hosted Basic Memory knowledge graph on a remote NAS",
            "author": {"name": "elconcept"}, "repository": PLUGIN_REPO,
            "license": "AGPL-3.0-or-later",
        })
        assets[".mcp.json"] = json_bytes({
            "mcpServers": {cfg["mcp_server_key"]: {"type": "http", "url": cfg["mcp_url"]}}
        })
        # Candidate only. Lifecycle hook execution requires Claude G1 confirmation.
        assets.update(local_hook_assets())
    else:
        ext: dict = {"interface": {
            "displayName": "Basic Memory (NAS)",
            "shortDescription": "Memory and notes via a self-hosted Basic Memory server",
            "developerName": "elconcept", "category": "Productivity",
            "capabilities": ["Read", "Write"], "websiteURL": PLUGIN_REPO,
        }}
        if openai_variant == "M":
            assets["mcp.json"] = json_bytes({
                "$schema": OPENAI_MCP_SCHEMA, "mcpServers": {
                    cfg["mcp_server_key"]: {
                        "type": "streamable-http", "url": cfg["mcp_url"],
                        "extensions": {"com.openai": {"auth": {"type": "oauth", "client": {"mode": "dcr"}}}}
                    }
                }
            })
        elif openai_variant == "R":
            # Registered connection mapping must be tested with real plugin-creator.
            # Never fabricate a .app.json mapping from an ID.
            raise ValueError("OpenAI variant R requires a verified .app.json from G0-O")
        else:
            raise ValueError("OpenAI target gated: choose a verified --openai-variant M or R")
        assets["plugin.json"] = json_bytes({
            "$schema": OPENAI_SCHEMA, "name": META_KEY, "version": version,
            "description": "Self-hosted Basic Memory skills and remote MCP",
            "repository": PLUGIN_REPO, "license": "AGPL-3.0-or-later",
            "extensions": {"com.openai": ext},
        })
    return assets


def compare_tree(root: Path, assets: dict[str, bytes]) -> list[str]:
    actual = {
        p.relative_to(root).as_posix(): p.read_bytes()
        for p in root.rglob("*") if p.is_file()
    } if root.is_dir() else {}
    return [name for name in sorted(set(assets) | set(actual)) if actual.get(name) != assets.get(name)]


def build(upstream: Path, out: Path, overrides: Path, config_path: Path, target: str, check: bool, openai_variant: str | None) -> dict:
    cfg = load_config(config_path)
    manifest_lock = upstream.parent / "config/upstream.lock.json"
    # SHA is supplied explicitly in local config. A runner checkout is verified by CI.
    lock = json.loads(manifest_lock.read_text(encoding="utf-8")) if manifest_lock.exists() else None
    if lock is not None and lock.get("upstream_sha") != cfg["upstream_sha"]:
        raise ValueError("Upstream lock SHA disagrees with build config")
    targets = ("claude", "openai") if target == "all" else (target,)
    if target not in {"claude", "openai", "all"}:
        raise ValueError(f"Invalid build target: {target}")
    version = cfg["version"]
    outputs: dict[str, dict[str, bytes]] = {}
    for host in targets:
        outputs[host] = render(upstream, overrides, cfg, host, version, openai_variant, None)
    result = {
        "upstream_sha": cfg["upstream_sha"], "version": version,
        "targets": list(targets),
        "files": {host: len(files) for host, files in outputs.items()},
        "content_sha256": sha256(b"".join(
            name.encode() + b"\0" + data
            for host in targets for name, data in sorted(outputs[host].items())
        )),
        "status": "CANDIDATE_ONLY_NOT_INSTALLED",
    }
    if check:
        changed = [f"{host}/{name}" for host in targets for name in compare_tree(out / host, outputs[host])]
        if changed:
            raise ValueError("Generated artifacts differ: " + ", ".join(changed[:20]))
    else:
        out.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(prefix=".bm-build-", dir=out) as tmp:
            staging = Path(tmp)
            for host in targets:
                for name, data in outputs[host].items():
                    path = staging / host / name
                    path.parent.mkdir(parents=True, exist_ok=True)
                    path.write_bytes(data)
            for host in targets:
                dest = out / host
                if dest.exists():
                    shutil.rmtree(dest)
                shutil.move(str(staging / host), str(dest))
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--upstream", type=Path, required=True)
    parser.add_argument("--out", type=Path, default=Path("."))
    parser.add_argument("--overrides", type=Path, default=Path("overrides/skills"))
    parser.add_argument("--config", type=Path, default=Path("config/build.json"))
    parser.add_argument("--target", choices=("claude", "openai", "all"), default="claude")
    parser.add_argument("--openai-variant", choices=("R", "M"))
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    print(json.dumps(build(args.upstream, args.out, args.overrides, args.config, args.target, args.check, args.openai_variant), sort_keys=True))


if __name__ == "__main__":
    main()
