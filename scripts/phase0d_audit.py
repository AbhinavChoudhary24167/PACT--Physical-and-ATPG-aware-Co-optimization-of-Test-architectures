#!/usr/bin/env python3
"""Hash and verify frozen Phase-0C evidence without recomputing experiments."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from pact.phase0d.campaign import atomic_write_json, file_sha256, utc_now  # noqa: E402


def git(*args: str) -> str:
    return subprocess.check_output(["git", *args], cwd=ROOT, text=True, encoding="utf-8").strip()


def collect_dependency_hashes() -> dict[str, str]:
    dependencies: dict[str, str] = {}
    for proxy_path in sorted((ROOT / "artifacts/derived/phase0c").glob("**/*.proxy.json")):
        row = json.loads(proxy_path.read_text(encoding="utf-8"))
        for relative, expected in row.get("input_sha256", {}).items():
            old = dependencies.setdefault(relative.replace("\\", "/"), expected)
            if old != expected:
                raise ValueError(f"Conflicting frozen hashes for {relative}: {old} vs {expected}")
    report_manifest = json.loads((ROOT / "artifacts/manifests/phase0c/report_manifest.json").read_text(encoding="utf-8"))
    for relative, expected in report_manifest.get("sources", {}).items():
        old = dependencies.setdefault(relative.replace("\\", "/"), expected)
        if old != expected:
            raise ValueError(f"Conflicting report hash for {relative}: {old} vs {expected}")
    return dependencies


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", type=Path, default=ROOT / "reports/phase0d")
    args = parser.parse_args()
    output_dir = args.output_dir if args.output_dir.is_absolute() else ROOT / args.output_dir

    head = git("rev-parse", "HEAD")
    branch = git("branch", "--show-current")
    tracked = sorted(path for path in git("ls-files").splitlines() if "phase0c" in path.lower())
    phase0c_records: list[tuple[str, str]] = []
    missing: list[str] = []
    for relative in tracked:
        path = ROOT / relative
        if not path.is_file():
            missing.append(relative)
            continue
        phase0c_records.append((relative.replace("\\", "/"), file_sha256(path)))

    dependency_expected = collect_dependency_hashes()
    dependency_records: list[dict[str, object]] = []
    mismatches: list[dict[str, str | None]] = []
    for relative, expected in sorted(dependency_expected.items()):
        path = ROOT / relative
        actual = file_sha256(path) if path.is_file() else None
        ok = actual == expected
        dependency_records.append({"path": relative, "expected_sha256": expected, "actual_sha256": actual, "verified": ok})
        if not ok:
            mismatches.append({"path": relative, "expected_sha256": expected, "actual_sha256": actual})

    digest_lines = [f"{sha}  {path}" for path, sha in phase0c_records]
    root_digest = hashlib.sha256(("\n".join(digest_lines) + "\n").encode("utf-8")).hexdigest()
    porcelain = git("status", "--porcelain=v1", "--untracked-files=no")
    tracked_changes = [line for line in porcelain.splitlines() if line]
    full_porcelain = git("status", "--porcelain=v1", "--untracked-files=all")
    inherited_untracked = [
        line for line in full_porcelain.splitlines()
        if line.startswith("?? ")
        and "phase0d" not in line.lower()
        and "reports/phase0d/" not in line.lower()
    ]
    gate_analysis = json.loads((ROOT / "artifacts/derived/phase0c/gate_analysis.json").read_text(encoding="utf-8"))
    audit = {
        "schema_version": "phase0d-phase0c-audit-1",
        "timestamp_utc": utc_now(),
        "starting_branch": branch,
        "starting_commit": head,
        "phase0c_frozen_commit": "06d97d82263b3671d8a56c9e6ed104cf88d40266",
        "phase0c_decision": gate_analysis["classification"],
        "tracked_phase0c_file_count": len(phase0c_records),
        "tracked_phase0c_bytes": sum((ROOT / path).stat().st_size for path, _ in phase0c_records),
        "tracked_phase0c_sha256_root": root_digest,
        "dependency_file_count": len(dependency_records),
        "dependency_hashes_verified": len(mismatches) == 0,
        "missing_tracked_phase0c_files": missing,
        "dependency_mismatches": mismatches,
        "tracked_worktree_changes_at_audit": tracked_changes,
        "working_tree_clean_before_phase0d": not inherited_untracked and not tracked_changes,
        "inherited_untracked_paths": inherited_untracked,
        "qualified_route_rows": gate_analysis["qualified_new_routes"],
        "complete_design_seed_K_contexts": gate_analysis["gates"]["C2"]["complete_pairs"],
        "phase0c_immutable": not missing and not mismatches and not tracked_changes and head == "06d97d82263b3671d8a56c9e6ed104cf88d40266",
        "dependency_records": dependency_records,
    }
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "phase0c_evidence.sha256").write_text("\n".join(digest_lines) + "\n", encoding="utf-8")
    atomic_write_json(output_dir / "phase0c_audit.json", audit)
    print(json.dumps({key: audit[key] for key in (
        "starting_branch", "starting_commit", "phase0c_decision", "tracked_phase0c_file_count",
        "tracked_phase0c_sha256_root", "dependency_file_count", "dependency_hashes_verified",
        "qualified_route_rows", "phase0c_immutable",
    )}, indent=2))
    return 0 if audit["phase0c_immutable"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
