#!/usr/bin/env python3
"""Correct pre-freeze pilot HPWL to include fixed SI/SO port links.

The original route metrics are archived next to the corrected record.
"""
from __future__ import annotations

import json
from pathlib import Path
import shutil

from pact.physical.phase0c_scan_geometry import phase0c_scan_geometry
from pact.scan.model import ScanArchitecture


ROOT = Path(__file__).resolve().parents[1]


def main() -> None:
    updated = 0
    for path in sorted((ROOT / "artifacts/raw/phase0c/physical").glob("*/s*/k*/*/route_metrics.json")):
        record = json.loads(path.read_text(encoding="utf-8"))
        design, seed, k, method = (record["design"], record["physical_seed"],
                                   record["K"], record["method"])
        arch_path = ROOT / f"artifacts/derived/phase0c/{design}/s{seed}/k{k}/{method}.architecture.json"
        def_path = ROOT / f"artifacts/raw/phase0b/placements/{design}/s{seed}/placed.def"
        arch = ScanArchitecture.from_json(arch_path)
        if arch.sha256() != record["architecture_sha256"]:
            raise ValueError(f"Architecture mismatch in {path}")
        geometry = phase0c_scan_geometry(arch, def_path)
        new_cost = geometry["total_scan_hpwl_um"]
        if abs(record["scan_hpwl_proxy_um"] - new_cost) < 1e-9:
            continue
        backup = path.parent / "route_metrics_pre_port_hpwl.json"
        if not backup.exists():
            shutil.copy2(path, backup)
        record["scan_hpwl_proxy_um"] = new_cost
        record["scan_hpwl_proxy_components_um"] = {
            "internal_ff": geometry["internal_ff_hpwl_um"],
            "SI_SO_port_links": geometry["port_edge_hpwl_um"],
        }
        record["physical_primary_um"] = new_cost if record["status"] == "QUALIFIED" else None
        path.write_text(json.dumps(record, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        updated += 1
    print(json.dumps({"updated": updated}))


if __name__ == "__main__":
    main()
