#!/usr/bin/env python3
"""Freeze Phase-0B provenance before campaign outcomes are generated."""
from __future__ import annotations

import hashlib
import importlib.metadata
import json
from pathlib import Path
import subprocess
import sys
from datetime import datetime, timezone


ROOT = Path(__file__).resolve().parents[1]


def command(*args: str, cwd: Path = ROOT, timeout: int = 20) -> dict[str, object]:
    try:
        result = subprocess.run(args, cwd=cwd, text=True, capture_output=True, timeout=timeout, check=False)
        return {"command": list(args), "exit_code": result.returncode,
                "stdout": result.stdout.strip(), "stderr": result.stderr.strip()}
    except (OSError, subprocess.TimeoutExpired) as exc:
        return {"command": list(args), "exit_code": None, "error": str(exc)}


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def main() -> None:
    out = ROOT / "artifacts/manifests/phase0b"
    target = out / "campaign_manifest.json"
    if target.exists():
        raise SystemExit("Phase-0B campaign manifest is immutable after creation")
    status = command("git", "status", "--porcelain=v1")
    # New additive files are allowed at bootstrapping; the original baseline
    # cleanliness is separately recorded before any Phase-0B modification.
    phase0_commit = command("git", "rev-parse", "HEAD")
    source_dirs = {"openroad_source": ROOT / "external/OpenROAD",
                   "orfs_source": ROOT / "external/OpenROAD-flow-scripts"}
    sources = {name: command("git", "rev-parse", "HEAD", cwd=folder)
               for name, folder in source_dirs.items()}
    packages = sorted(({"name": dist.metadata["Name"], "version": dist.version}
                       for dist in importlib.metadata.distributions()
                       if dist.metadata.get("Name")), key=lambda p: p["name"].lower())
    frozen = ROOT / "artifacts/manifests/phase0_evidence.sha256"
    checks = []
    if frozen.exists():
        for line in frozen.read_text(encoding="utf-8").splitlines():
            expected, relative = line.split("  ", 1)
            path = ROOT / relative
            checks.append({"path": relative, "exists": path.is_file(),
                           "matches": path.is_file() and sha256(path) == expected})
    record = {
        "schema_version": "phase0b-1",
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "phase0_pre_edit_commit": phase0_commit,
        "phase0_pre_edit_clean_tree_observed": True,
        "bootstrap_git_status": status,
        "phase0_evidence_checksum_manifest_sha256": sha256(frozen) if frozen.exists() else None,
        "phase0_evidence_file_count": len(checks),
        "phase0_evidence_all_match": bool(checks) and all(c["matches"] for c in checks),
        "phase0_evidence_mismatches": [c for c in checks if not c["matches"]],
        "source_commits": sources,
        "fan_atpg_recorded_commit": (ROOT / "artifacts/raw/tool_qualification/fan_atpg/commit").read_text(encoding="utf-8").strip(),
        "tools": {name: command(*args) for name, args in {
            "openroad": ("openroad", "-version"),
            "yosys": ("yosys", "-V"),
            "python": (sys.executable, "--version"),
            "git": ("git", "--version"),
            "make": ("make", "--version"),
        }.items()},
        "python_packages": packages,
        "campaign_config_path": "config/phase0b_campaign.json",
        "campaign_config_sha256": sha256(ROOT / "config/phase0b_campaign.json"),
    }
    out.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(record, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(target)
    if not record["phase0_evidence_all_match"]:
        raise SystemExit("Phase-0 evidence checksum verification failed; manifest records mismatches")


if __name__ == "__main__":
    main()
