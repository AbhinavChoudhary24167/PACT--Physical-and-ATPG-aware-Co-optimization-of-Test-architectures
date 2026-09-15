#!/usr/bin/env python3
"""Reverify pre-freeze pilot routes with final port and full-path-bound checks."""
from __future__ import annotations

import json
from pathlib import Path
import shutil

from phase0b_run_command import run
from phase0c_run_route import BLOCK, FLOW, ROOT


def main() -> None:
    passed = 0
    failed = 0
    for metrics_path in sorted((ROOT / "artifacts/raw/phase0c/physical").glob("*/s*/k*/*/route_metrics.json")):
        record = json.loads(metrics_path.read_text(encoding="utf-8"))
        if record.get("status") != "QUALIFIED" or not record.get("variant", "").startswith("phase0c_s"):
            continue
        design, seed, k, method = record["design"], record["physical_seed"], record["K"], record["method"]
        arch = ROOT / f"artifacts/derived/phase0c/{design}/s{seed}/k{k}/{method}.architecture.json"
        odb = FLOW / f"results/nangate45/{BLOCK[design]}/{record['variant']}/5_2_route.odb"
        proof_path = metrics_path.parent / "routed_verification_v2.json"
        command = ["openroad", "-python", "-no_init", "-exit",
                   str(ROOT / "scripts/phase0c_verify_routed.py"),
                   "--routed", str(odb), "--architecture", str(arch),
                   "--output", str(proof_path)]
        execution = run(command, metrics_path.parent / "postroute_verify_v2", ROOT, 90, [proof_path])
        proof = json.loads(proof_path.read_text()) if proof_path.exists() else {}
        if (execution["exit_code"] != 0 or execution["timed_out"] or proof.get("status") != "PASS"
                or not proof.get("fixed_port_positions_verified")
                or proof.get("bounded_scan_path_link_count") != proof.get("scan_ff_count", -1) + k):
            failed += 1
            print(json.dumps({"design": design, "seed": seed, "K": k, "method": method,
                              "status": "REVERIFICATION_FAILED"}), flush=True)
            continue
        backup = metrics_path.parent / "route_metrics_pre_reverification.json"
        if not backup.exists():
            shutil.copy2(metrics_path, backup)
        record["postroute_verification"] = str(proof_path.relative_to(ROOT)).replace("\\", "/")
        record["exact_scan_only_routed_length_um"] = proof["exact_scan_only_total_um"]
        record["routed_full_scan_path_net_length_upper_bound_um"] = proof["routed_full_scan_path_net_length_upper_bound_um"]
        metrics_path.write_text(json.dumps(record, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        passed += 1
    print(json.dumps({"reverified": passed, "failed": failed}))


if __name__ == "__main__":
    main()
