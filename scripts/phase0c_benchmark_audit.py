#!/usr/bin/env python3
"""Record reproducible local candidate audits without admitting unqualified designs."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
ORFS = ROOT / "external/OpenROAD-flow-scripts/flow/designs"
ORFS_COMMIT = "5e8b1450d19263f797a27c4f371b9dd19f32a3aa"


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    candidates = []
    for name, source, config, license_name, license_note in (
        ("ibex", "ibex_sv", "ibex", "Apache-2.0", "Bundled Apache License 2.0 text"),
        ("jpeg", "jpeg", "jpeg", "ASICs World permissive notice", "Bundled redistribution notice; preserve notices"),
    ):
        folder = ORFS / "src" / source
        rtl = sorted(path for path in folder.rglob("*") if path.suffix in {".v", ".vh", ".sv", ".svh"})
        source_rows = [{"path": str(path.relative_to(ROOT)).replace("\\", "/"), "sha256": sha(path)}
                       for path in rtl]
        canonical = json.dumps(source_rows, sort_keys=True, separators=(",", ":")).encode()
        conf = ORFS / "nangate45" / config / "config.mk"
        license_path = folder / "LICENSE"
        candidates.append({
            "design": name,
            "status": "NOT_ADMITTED_ATPG_AND_SCAN_IDENTITY_UNQUALIFIED",
            "source_url": f"https://github.com/The-OpenROAD-Project/OpenROAD-flow-scripts/tree/{ORFS_COMMIT}/flow/designs/src/{source}",
            "source_license": license_name, "license_note": license_note,
            "license_path": str(license_path.relative_to(ROOT)).replace("\\", "/"),
            "license_sha256": sha(license_path),
            "source_files": source_rows, "source_file_count": len(source_rows),
            "source_tree_sha256": hashlib.sha256(canonical).hexdigest(),
            "synthesis_config": str(conf.relative_to(ROOT)).replace("\\", "/"),
            "synthesis_config_sha256": sha(conf),
            "synthesis_executed_for_phase0c": False,
            "scan_insertion_executed_for_phase0c": False,
            "scan_ff_count": None, "FAN_pattern_count": None, "fault_coverage_percent": None,
            "qualification_reason": "No reproducible FAN full-scan/PPI-to-FF mapping and frozen architecture-independent ATPG patterns. Source/license/config audit alone does not qualify a benchmark.",
        })
    target = ROOT / "artifacts/manifests/phase0c/benchmark_candidate_audit.json"
    target.write_text(json.dumps({"schema_version": "phase0c-benchmark-candidates-1",
                                  "ORFS_commit": ORFS_COMMIT, "candidates": candidates},
                                 indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"audited": len(candidates), "admitted": 0,
                      "source_files": [c["source_file_count"] for c in candidates]}))


if __name__ == "__main__":
    main()
