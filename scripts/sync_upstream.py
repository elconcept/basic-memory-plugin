#!/usr/bin/env python3
"""Mirror upstream Basic Memory plugin sources without executing upstream code.

Used only by GitHub Actions. Copies public upstream assets into a reviewable
staging snapshot; the local build pipeline can later turn this into plugins.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path
import shutil
import tempfile

SOURCE_REPO = "basicmachines-co/basic-memory"
SKILL_ROOTS = (
    "skills",
    "plugins/claude-code/skills",
    "plugins/codex/skills",
)
EXTRA_DIRS = (
    "plugins/claude-code/schemas",
    "plugins/claude-code/output-styles",
    "plugins/claude-code/hooks",
    "plugins/codex/schemas",
    "plugins/codex/hooks",
)
EXTRA_FILES = (
    "LICENSE",
    "skills/README.md",
    "plugins/claude-code/README.md",
    "plugins/codex/README.md",
    "plugins/claude-code/.claude-plugin/plugin.json",
    "plugins/claude-code/.mcp.json",
    "plugins/codex/.codex-plugin/plugin.json",
    "plugins/codex/.mcp.json",
)
EXTENSIONS = {".md", ".json", ".yaml", ".yml", ".toml", ".py", ".svg", ".txt", ".sh"}
MAX_BYTES = 2 * 1024 * 1024


def collect(source: Path) -> dict[str, bytes]:
    """Select plugin/skill assets, never core code or eval fixtures."""
    selected: dict[str, bytes] = {}

    def add(path: Path) -> None:
        if path.is_symlink():
            raise ValueError(f"Symlink in source is not allowed: {path}")
        if not path.is_file():
            raise ValueError(f"Not a regular file: {path}")
        if path.suffix.lower() not in EXTENSIONS and path.name != "LICENSE":
            raise ValueError(f"Unexpected upstream file extension: {path}")
        if path.stat().st_size > MAX_BYTES:
            raise ValueError(f"Oversized upstream file: {path}")
        selected[path.relative_to(source).as_posix()] = path.read_bytes()

    def directory(path: Path) -> None:
        if path.is_symlink():
            raise ValueError(f"Symlink directory is not allowed: {path}")
        if not path.is_dir():
            return
        for item in sorted(path.rglob("*")):
            if any(x in {"evals", "tests", "__pycache__", ".git", ".pytest_cache"} for x in item.relative_to(path).parts):
                continue
            if item.is_symlink():
                raise ValueError(f"Symlink in source is not allowed: {item}")
            if item.is_file():
                add(item)

    for folder in SKILL_ROOTS:
        root = source / folder
        if not root.is_dir():
            raise ValueError(f"Missing upstream directory: {folder}")
        prefix = "memory-" if folder == "skills" else "bm-"
        skills = [p for p in root.iterdir() if p.is_dir() and p.name.startswith(prefix)]
        if not skills:
            raise ValueError(f"Missing expected skill folders: {folder}")
        for skill in sorted(skills):
            if not (skill / "SKILL.md").is_file():
                raise ValueError(f"Skill without SKILL.md: {skill}")
            directory(skill)

    for folder in EXTRA_DIRS:
        directory(source / folder)
    for fname in EXTRA_FILES:
        path = source / fname
        if path.exists() or path.is_symlink():
            add(path)
    return selected


def digest(files: dict[str, bytes]) -> str:
    h = hashlib.sha256()
    for name, content in sorted(files.items()):
        h.update(name.encode("utf-8") + b"\0" + len(content).to_bytes(8, "big") + content)
    return h.hexdigest()


def previous_files(dest: Path) -> dict[str, bytes]:
    if not dest.exists():
        return {}
    return {
        p.relative_to(dest).as_posix(): p.read_bytes()
        for p in dest.rglob("*") if p.is_file()
    }


def prepare_build_config(path: Path | None, sha: str) -> tuple[bytes | None, str | None]:
    """Bump the plugin version exactly once for an actual upstream SHA change."""
    if path is None or not path.exists():
        return None, None
    cfg = json.loads(path.read_text(encoding="utf-8"))
    current = cfg.get("upstream_sha")
    version = cfg.get("version")
    if not isinstance(current, str) or not isinstance(version, str):
        raise ValueError("Build config lacks upstream_sha or version")
    if not re.fullmatch(r"1\.0\.[0-9]+", version):
        raise ValueError("Unsupported version; manual review required")
    if current == sha:
        return None, version
    parts = version.split(".")
    cfg["version"] = ".".join([parts[0], parts[1], str(int(parts[2]) + 1)])
    cfg["upstream_sha"] = sha
    return (json.dumps(cfg, ensure_ascii=False, indent=2) + "\n").encode("utf-8"), cfg["version"]


def synchronize(source: Path, dest: Path, lock_path: Path, sha: str, report: Path, build_config: Path | None = None) -> dict:
    if len(sha) != 40 or any(c not in "0123456789abcdef" for c in sha):
        raise ValueError("Upstream SHA must be 40 lowercase hex characters")
    updated_build, release_version = prepare_build_config(build_config, sha)
    files = collect(source)
    old_files = previous_files(dest)
    old_lock = json.loads(lock_path.read_text("utf-8")) if lock_path.exists() else {}
    prior_sha = old_lock.get("upstream_sha")
    changes = [
        f"{'A' if p not in old_files else 'M' if p in files else 'D'} {p}"
        for p in sorted(set(files) | set(old_files))
        if old_files.get(p) != files.get(p)
    ]
    manifest = {
        "source_repo": SOURCE_REPO,
        "upstream_sha": sha,
        "snapshot_digest": digest(files),
        "file_count": len(files),
        "integration_status": "source-staging-until-artifact-build-is-tested",
    }

    # Prepare complete replacement before touching tracked snapshot.
    dest.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="bm-sync-", dir=dest.parent) as tmp:
        staging = Path(tmp) / "snapshot"
        for name, content in files.items():
            target = staging / name
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(content)
        backup = Path(tmp) / "old"
        if dest.exists():
            dest.rename(backup)
        staging.rename(dest)

    lock_path.parent.mkdir(parents=True, exist_ok=True)
    lock_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    if updated_build is not None and build_config is not None:
        build_config.write_bytes(updated_build)

    notable = [line for line in changes if any(x in line for x in ("/hooks/", "plugin.json", ".mcp.json", "/schemas/", "LICENSE"))]
    summary = (
        "# Upstream Basic Memory sync (review required)\n\n"
        f"- Base SHA: \`{prior_sha or 'none'}\`\n"
        f"- Candidate SHA: \`{sha}\`\n"
        f"- Snapshot files: {len(files)}; changed paths: {len(changes)}\n"
        "- **No auto-merge.** A reviewer must check upstream changes and licenses.\n"
        "- Until artifact builds pass, changes in \`vendor/upstream\` are *staged source*, not a deployed client update.\n"
        "- The upstream checkout is data only: its code is not executed by this workflow.\n\n"
        "## Changed paths\n\n" +
        ("\n".join(f"- \`{line}\`" for line in changes[:250]) if changes else "No snapshotted files changed.") +
        ("\n\nAdditional changed paths omitted from PR body; inspect the diff." if len(changes) > 250 else "") +
        "\n\n## High-attention changes\n\n" +
        ("\n".join(f"- \`{line}\`" for line in notable) if notable else "None in selected manifests, hooks or schemas.") +
        "\n"
    )
    report.parent.mkdir(parents=True, exist_ok=True)
    report.write_text(summary, encoding="utf-8")
    return {"manifest": manifest, "changes": changes, "prior_sha": prior_sha}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--dest", type=Path, required=True)
    parser.add_argument("--lock", type=Path, required=True)
    parser.add_argument("--sha", required=True)
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--build-config", type=Path)
    args = parser.parse_args()
    result = synchronize(args.source.resolve(), args.dest, args.lock, args.sha, args.report, args.build_config)
    print(json.dumps({"upstream_sha": args.sha, "changed_paths": len(result["changes"]), "snapshot_files": result["manifest"]["file_count"]}))


if __name__ == "__main__":
    main()
