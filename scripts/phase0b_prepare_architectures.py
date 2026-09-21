#!/usr/bin/env python3
"""Freeze legal architecture hashes and activity outcomes on one placed seed."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import re

from pact.analysis.phase0b_activity import exact_shift_metrics
from pact.physical.extract_placement import extract_def_scan_cells
from pact.physical.phase0b_geometry import scan_edge_distribution
from pact.physical.scan_wirelength import scan_wirelength
from pact.scan.model import ScanArchitecture
from pact.scan.orderings import activity_only, nearest_neighbor, physical_activity, random_order, serpentine
from pact.scan.validate import validate_scan
from pact.test.pattern_parser import map_ppi_patterns, parse_fan_pat


ROOT = Path(__file__).resolve().parents[1]
CONFIG = json.loads((ROOT / "config/phase0b_campaign.json").read_text(encoding="utf-8"))


def run_id(design: str, physical_seed: int, method: str, sha: str) -> str:
    data = {
        "campaign": "PACT_PHASE0B", "design": design, "physical_seed": physical_seed,
        "method": method, "architecture_sha256": sha,
        "openroad_version": "26Q2-1164-g08f67ee5ec",
        "orfs_commit": "5e8b1450d19263f797a27c4f371b9dd19f32a3aa",
    }
    return hashlib.sha256(json.dumps(data, sort_keys=True, separators=(",", ":")).encode()).hexdigest()[:20]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--design", choices=("s5378", "s9234", "s15850"), required=True)
    parser.add_argument("--seed", type=int, choices=CONFIG["physical_seeds"], required=True)
    args = parser.parse_args()
    design, seed = args.design, args.seed
    placement = ROOT / f"artifacts/raw/phase0b/placements/{design}/s{seed}"
    placed_v, placed_def = placement / "placed.v", placement / "placed.def"
    if not placed_v.is_file() or not placed_def.is_file():
        raise ValueError("Frozen placed netlist and DEF are required")
    source = ROOT / f"artifacts/derived/{design}"
    baseline = ScanArchitecture.from_json(source / "supplied_architecture.json")
    names = {cell.name for cell in baseline.cells}
    cells = extract_def_scan_cells(placed_def, names, "CK")
    base = ScanArchitecture(cells, baseline.chains)
    validate_scan(base)
    def_text = placed_def.read_text(encoding="utf-8")
    def_names = set(re.findall(r"(?m)^\s*-\s+(\S+)\s+SDFF_X1\s+\+", def_text))
    if def_names != names:
        raise ValueError("Placed scan-cell inventory or master differs")
    raw = ROOT / "artifacts/raw/tool_qualification/fan_atpg"
    parsed = parse_fan_pat(raw / f"patterns/FAN_{design}.pat")
    ff_map = json.loads((source / "ff_identity_map.json").read_text(encoding="utf-8"))["records"]
    patterns = map_ppi_patterns(parsed, ff_map)
    candidates = {"B0": base}
    native_qualification = ROOT / f"artifacts/derived/phase0b/{design}/s{seed}/B1.native_qualification.json"
    if native_qualification.is_file():
        qualification = json.loads(native_qualification.read_text(encoding="utf-8"))
        if qualification.get("status") != "PASS":
            raise ValueError("Native DFT qualification did not pass")
        native = ScanArchitecture.from_json(native_qualification.parent / "B1.architecture.json")
        if native.cells != base.cells:
            raise ValueError("Native paired ordering uses different placement")
        candidates["B1"] = native
    candidates.update({
        "P": nearest_neighbor(base),
        "S": serpentine(base),
        "A": activity_only(base, patterns),
        "J25": physical_activity(base, patterns, 0.25),
        "J50": physical_activity(base, patterns, 0.50),
        "J75": physical_activity(base, patterns, 0.75),
    })
    randoms = [(number, random_order(base, number)) for number in CONFIG["random_order_seeds"]]
    evaluated_random = [(number, arch, exact_shift_metrics(arch, patterns, grid_sizes=(8,)))
                        for number, arch in randoms]
    rseed, rarch, rmetrics = min(evaluated_random,
                                key=lambda item: (item[2]["spatial_by_grid"]["8"]["distance_weighted_hotspot"], item[1].sha256()))
    candidates["Rstar"] = rarch
    out = ROOT / f"artifacts/derived/phase0b/{design}/s{seed}"
    out.mkdir(parents=True, exist_ok=True)
    rows = []
    seen: dict[str, str] = {}
    metrics_by_hash: dict[str, dict[str, object]] = {}
    for method, arch in candidates.items():
        arch_sha = arch.sha256()
        if arch_sha not in metrics_by_hash:
            metrics_by_hash[arch_sha] = exact_shift_metrics(arch, patterns)
        metrics = metrics_by_hash[arch_sha]
        geometry = scan_wirelength(arch)
        geometry.update(scan_edge_distribution(arch))
        canonical = seen.setdefault(arch_sha, method)
        arch_path = out / f"{canonical}.architecture.json"
        if method == canonical:
            arch.to_json(arch_path)
        rows.append({
            "design": design, "physical_seed": seed, "method": method,
            "canonical_method": canonical, "run_id": run_id(design, seed, method, arch_sha),
            "architecture_sha256": arch_sha,
            "architecture_path": str(arch_path.relative_to(ROOT)).replace("\\", "/"),
            "physical_seed_method": "seeded_placement_perturb_and_legalize",
            "primary_physical_proxy_scan_hpwl_um": geometry["total_scan_hpwl_um"],
            "scan_geometry": geometry, "shift_activity": metrics,
            "pattern_source": str((raw / f"patterns/FAN_{design}.pat").relative_to(ROOT)).replace("\\", "/"),
            "placed_def": str(placed_def.relative_to(ROOT)).replace("\\", "/"),
            "placed_v": str(placed_v.relative_to(ROOT)).replace("\\", "/"),
            "status": "PROXY_ONLY_PENDING_ROUTE" if method != "B0" else "BASE_ROUTE_PENDING",
        })
    jrows = [row for row in rows if row["method"] in ("J25", "J50", "J75")]
    best_j = min(jrows, key=lambda row: (row["shift_activity"]["spatial_by_grid"]["8"]["distance_weighted_hotspot"],
                                         row["primary_physical_proxy_scan_hpwl_um"], row["architecture_sha256"]))
    route_methods = ["B0"] + (["B1"] if "B1" in candidates else []) + ["P", "A", best_j["method"], "Rstar"]
    plan = {
        "schema_version": "phase0b-1", "design": design, "physical_seed": seed,
        "phase0b_config_sha256": hashlib.sha256((ROOT / "config/phase0b_campaign.json").read_bytes()).hexdigest(),
        "seed_method_sha256": hashlib.sha256((ROOT / "config/phase0b_seed_method.json").read_bytes()).hexdigest(),
        "Rstar_random_order_seed": rseed,
        "random_candidate_H8": {str(number): result["spatial_by_grid"]["8"]["distance_weighted_hotspot"]
                                for number, _, result in evaluated_random},
        "best_joint_method": best_j["method"],
        "route_methods": route_methods,
        "distinct_route_canonical_methods": list(dict.fromkeys(next(r["canonical_method"] for r in rows if r["method"] == m)
                                                         for m in route_methods)),
        "rows": rows,
    }
    (out / "plan.json").write_text(json.dumps(plan, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"design": design, "seed": seed, "route": plan["distinct_route_canonical_methods"],
                      "random_winner": rseed}))


if __name__ == "__main__":
    main()
