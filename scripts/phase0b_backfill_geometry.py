#!/usr/bin/env python3
"""Archive old Phase-0B plans and add lossless scan-edge distributions."""
from __future__ import annotations

import json
import math
from pathlib import Path
import shutil

from pact.physical.phase0b_geometry import scan_edge_distribution
from pact.scan.model import ScanArchitecture


ROOT = Path(__file__).resolve().parents[1]


def main() -> None:
    folders = [ROOT / f"artifacts/derived/phase0b/{design}/s{seed}"
               for design in ("s5378", "s9234") for seed in (11, 13, 17, 19, 23)]
    folders.append(ROOT / "artifacts/derived/phase0b/s15850/s11")
    for folder in folders:
        plan_path = folder / "plan.json"
        if not plan_path.is_file():
            continue
        plan = json.loads(plan_path.read_text(encoding="utf-8"))
        if all("edge_lengths_um" in row["scan_geometry"] for row in plan["rows"]):
            continue
        archive = folder / "plan.pre_edge_distribution.json"
        if not archive.exists():
            shutil.copy2(plan_path, archive)
        for row in plan["rows"]:
            arch = ScanArchitecture.from_json(ROOT / row["architecture_path"])
            new = scan_edge_distribution(arch)
            old = row["scan_geometry"]
            if len(new["edge_lengths_um"]) != old["num_edges"]:
                raise ValueError(f"Scan-edge count changed: {folder} {row['method']}")
            if not math.isclose(new["scan_chain_manhattan_um"], old["total_scan_hpwl_um"],
                                rel_tol=0, abs_tol=1e-6):
                raise ValueError(f"Scan HPWL changed: {folder} {row['method']}")
            old.update(new)
        plan_path.write_text(json.dumps(plan, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        print(f"GEOMETRY_COMPLETED {folder.relative_to(ROOT)}", flush=True)


if __name__ == "__main__":
    main()
