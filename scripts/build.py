#!/usr/bin/env python3
"""Build reviewable, credential-free Basic Memory plugin candidates.

This is a packaging tool, not a Basic Memory fork. It never executes imported
upstream source and never accesses the NAS. Each host gets two packages:
<host> mirrors the upstream native plugin (bm-* skills, schemas, output style)
and connects to the separately registered NAS MCP; <host>-extras carries the optional memory-* library.
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


def normalize_namespace(text: str) -> str:
    """Point upstream plugin skill references at this plugin's namespace."""
    text = text.replace("/basic-memory:", "/basic-memory-nas:")
    text = text.replace("basic-memory:bm-", "basic-memory-nas:bm-")
    return text.replace("codex:bm-", "basic-memory-nas:bm-")


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
            text = normalize_namespace(text)
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


CORE_COUNT = 8
EXTRAS_COUNT = 16


def select_skills(upstream: Path, overrides: Path, target: str, kind: str = "core") -> dict[str, bytes]:
    """core = the host's native bm-* plugin skills (upstream parity);
    extras = the optional shared memory-* library, shipped as a separate plugin."""
    if target not in {"claude", "openai"}:
        raise ValueError(f"Unknown target: {target}")
    if kind == "core":
        root = upstream / ("plugins/claude-code/skills" if target == "claude" else "plugins/codex/skills")
        prefix, expected = "bm-", CORE_COUNT
    elif kind == "extras":
        root, prefix, expected = upstream / "skills", "memory-", EXTRAS_COUNT
    else:
        raise ValueError(f"Unknown package kind: {kind}")
    files: dict[str, bytes] = {}
    count = 0
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
    if count != expected:
        raise ValueError(f"Upstream {kind} skill count changed ({count} != {expected}); review required")
    return files


def native_assets(upstream: Path, target: str) -> dict[str, bytes]:
    """Non-skill assets the native bm-* skills reference (schemas, output style)."""
    base = upstream / ("plugins/claude-code" if target == "claude" else "plugins/codex")
    dirs = ("schemas", "output-styles") if target == "claude" else ("schemas",)
    result: dict[str, bytes] = {}
    for d in dirs:
        root = base / d
        if not root.is_dir():
            raise ValueError(f"Missing upstream {d}/ for {target}; review required")
        for f in sorted(root.rglob("*")):
            if f.is_symlink():
                raise ValueError(f"Upstream symlink rejected: {f}")
            if not f.is_file():
                continue
            data = f.read_bytes()
            if f.suffix == ".md":
                text = normalize_namespace(data.decode("utf-8"))
                for forbidden in DENY:
                    if forbidden in text:
                        raise ValueError(f"Blocked local-install/cloud instruction in {d}/{f.name}: {forbidden}")
                data = text.encode("utf-8")
            result[f"{d}/{f.relative_to(root).as_posix()}"] = data
    return result


def local_hook_assets() -> dict[str, bytes]:
    """One stateless SessionStart brief; upstream's hooks need a local CLI."""
    source = Path(__file__).resolve().parents[1] / "src/hooks/session_start.py"
    if not source.is_file():
        raise ValueError("Local hook missing: src/hooks/session_start.py")
    return {
        "hooks/session_start.py": source.read_bytes(),
        "hooks/hooks.json": json_bytes({
            "description": "Basic Memory (NAS) session brief from local settings; no network, no state",
            "hooks": {"SessionStart": [{"hooks": [{
                "type": "command",
                "command": 'python3 "${CLAUDE_PLUGIN_ROOT}/hooks/session_start.py"',
                "timeout": 10,
                "statusMessage": "Basic Memory session brief",
            }]}]},
        }),
    }


EXTRAS_KEY = META_KEY + "-extras"


def common_assets(cfg: dict) -> dict[str, bytes]:
    return {
        "UPSTREAM_ATTRIBUTION.md": (
            "# Basic Memory upstream attribution\n\n"
            f"Upstream repository: https://github.com/basicmachines-co/basic-memory\n"
            f"Source revision: {cfg['upstream_sha']}\n\n"
            "This plugin is licensed under AGPL-3.0-or-later (see LICENSE). It "
            "includes skill content and other selected assets copied from upstream "
            "Basic Memory, which is licensed under AGPL-3.0-or-later; some upstream "
            "subcomponents additionally declare MIT. Upstream copyright notices are "
            "preserved.\n"
        ).encode(),
        "LICENSE": (Path(__file__).resolve().parent.parent / "LICENSE").read_bytes(),
    }


def render(upstream: Path, overrides: Path, cfg: dict, target: str, version: str, openai_variant: str | None, app_id: str | None, kind: str = "core") -> dict[str, bytes]:
    if target == "openai" and openai_variant != "M":
        if openai_variant == "R":
            # Registered connection mapping must be tested with real plugin-creator.
            raise ValueError("OpenAI variant R requires a verified .app.json from G0-O")
        raise ValueError("OpenAI target gated: choose a verified --openai-variant M or R")
    assets = select_skills(upstream, overrides, target, kind)
    assets.update(common_assets(cfg))
    name = META_KEY if kind == "core" else EXTRAS_KEY
    description = ("Basic Memory plugin for a self-hosted server: upstream skills, schemas and output style"
                   if kind == "core" else
                   "Optional Basic Memory memory-* skill library; requires basic-memory-nas")
    if kind == "core":
        assets.update(native_assets(upstream, target))
    if target == "claude":
        assets[".claude-plugin/plugin.json"] = json_bytes({
            "name": name, "version": version, "description": description,
            "author": {"name": "elconcept"}, "repository": PLUGIN_REPO,
            "license": "AGPL-3.0-or-later",
        })
        if kind == "core":
            assets[".mcp.json"] = json_bytes({
                "mcpServers": {cfg["mcp_server_key"]: {"type": "http", "url": cfg["mcp_url"]}}
            })
            assets.update(local_hook_assets())
    else:
        ext: dict = {"interface": {
            "displayName": "Basic Memory (NAS)" if kind == "core" else "Basic Memory (NAS) extras",
            "shortDescription": "Self-hosted Basic Memory" if kind == "core" else "Basic Memory extra skills",
            "developerName": "elconcept", "category": "Productivity",
            "capabilities": [] if kind == "core" else ["Read", "Write"], "websiteURL": PLUGIN_REPO,
        }}
        # ChatGPT uses the NAS MCP registered separately by the user.
        # The OpenAI plugin must remain skills-only, including after rebuilds.
        assets["plugin.json"] = json_bytes({
            "$schema": OPENAI_SCHEMA, "name": name, "version": version,
            "description": description,
            "repository": PLUGIN_REPO, "license": "AGPL-3.0-or-later",
            "extensions": {"com.openai": ext},
        })
        if kind == "core":
            # Like the working Symetria Prawna account plugin, explicitly
            # expose skills for clients using the legacy Codex manifest.
            # Do not declare an MCP server: the user registers it separately.
            assets[".codex-plugin/plugin.json"] = json_bytes({
                "name": name,
                "version": version,
                "description": description,
                "author": {"name": "elconcept"},
                "repository": PLUGIN_REPO,
                "skills": "./skills",
                "interface": ext["interface"],
            })
    return assets


def compare_tree(root: Path, assets: dict[str, bytes]) -> list[str]:
    actual = {
        p.relative_to(root).as_posix(): p.read_bytes()
        for p in root.rglob("*") if p.is_file()
        and "__pycache__" not in p.parts and p.suffix not in {".pyc", ".pyo"}
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
        core_version = cfg.get("openai_core_version", version) if host == "openai" else version
        outputs[host] = render(upstream, overrides, cfg, host, core_version, openai_variant, None, "core")
        outputs[host + "-extras"] = render(upstream, overrides, cfg, host, version, openai_variant, None, "extras")
    hosts = list(outputs)
    result = {
        "upstream_sha": cfg["upstream_sha"], "version": version,
        "targets": list(targets),
        "files": {host: len(files) for host, files in outputs.items()},
        "packages": hosts,
        "content_sha256": sha256(b"".join(
            name.encode() + b"\0" + data
            for host in hosts for name, data in sorted(outputs[host].items())
        )),
        "status": "GENERATED",
    }
    if check:
        changed = [f"{host}/{name}" for host in hosts for name in compare_tree(out / host, outputs[host])]
        if changed:
            raise ValueError("Generated artifacts differ: " + ", ".join(changed[:20]))
    else:
        out.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(prefix=".bm-build-", dir=out) as tmp:
            staging = Path(tmp)
            for host in hosts:
                for name, data in outputs[host].items():
                    path = staging / host / name
                    path.parent.mkdir(parents=True, exist_ok=True)
                    path.write_bytes(data)
            for host in hosts:
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
