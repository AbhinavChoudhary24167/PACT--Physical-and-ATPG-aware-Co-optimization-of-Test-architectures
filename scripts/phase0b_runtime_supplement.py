#!/usr/bin/env python3
"""Freeze package and binary provenance from the actual PACT WSL runtime."""
from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import importlib.metadata
import json
from pathlib import Path
import subprocess
import sys


ROOT = Path(__file__).resolve().parents[1]
TARGET = ROOT / "artifacts/manifests/phase0b/runtime_supplement.json"


def run(args: list[str]) -> dict:
    try:
        p = subprocess.run(args, text=True, capture_output=True, timeout=20, check=False)
        return {"argv": args, "exit_code": p.returncode,
                "stdout": p.stdout.strip(), "stderr": p.stderr.strip()}
    except (OSError, subprocess.TimeoutExpired) as exc:
        return {"argv": args, "error": str(exc)}


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def main() -> None:
    if TARGET.exists():
        raise SystemExit("Runtime supplement already frozen")
    package_rows = sorted(
        ({"name": d.metadata["Name"], "version": d.version}
         for d in importlib.metadata.distributions() if d.metadata.get("Name")),
        key=lambda row: row["name"].casefold())
    binaries = {str(path): {"sha256": sha256(path), "bytes": path.stat().st_size}
                for path in (Path("/usr/bin/openroad"), Path("/usr/bin/yosys"), Path(sys.executable))
                if path.is_file()}
    record = {
        "schema_version": "phase0b-runtime-1",
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "python_executable": sys.executable,
        "python_version": sys.version,
        "python_packages": package_rows,
        "pip_freeze": run([sys.executable, "-m", "pip", "freeze"]),
        "binary_versions": {name: run(argv) for name, argv in {
            "openroad": ["openroad", "-version"], "yosys": ["yosys", "-V"],
        }.items()},
        "binary_checksums": binaries,
        "tool_source_commits": {name: run(["git", "-C", str(path), "rev-parse", "HEAD"])
                                for name, path in {
            "OpenROAD": ROOT / "external/OpenROAD",
            "ORFS": ROOT / "external/OpenROAD-flow-scripts",
            "FAN_ATPG": Path("/root/pact-deps/FAN_ATPG"),
        }.items()},
    }
    TARGET.parent.mkdir(parents=True, exist_ok=True)
    TARGET.write_text(json.dumps(record, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(TARGET)


if __name__ == "__main__":
    main()
