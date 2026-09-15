#!/usr/bin/env python3
"""Generate reproducible Phase-0C logical/proxy qualification rows from frozen inputs."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import time

from pact.analysis.phase0c_activity import direct_sink_weights, parallel_activity_metrics
from pact.physical.extract_placement import extract_def_scan_cells
from pact.physical.phase0c_scan_geometry import phase0c_scan_geometry
from pact.scan.identity import scan_ff_instances
from pact.scan.model import ScanArchitecture, ScanChain
from pact.scan.phase0c import (chain_statistics, experiment_id, generate_architecture,
                               verify_parallel_schedule)
from pact.test.pattern_parser import map_ppi_patterns, parse_fan_pat


ROOT = Path(__file__).resolve().parents[1]
CAMPAIGN = json.loads((ROOT / "config/phase0c_campaign.json").read_text(encoding="utf-8"))


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def prepare(design: str, seed: int, k: int, methods: list[str], force: bool = False) -> list[dict]:
    if design not in CAMPAIGN["designs"] or seed not in CAMPAIGN["physical_seeds"] or k not in CAMPAIGN["K_values"]:
        raise ValueError("Design, physical seed or K is not predeclared")
    if any(method not in CAMPAIGN["route_families_each_K"] and not (method == "B1" and k == 1)
           for method in methods):
        raise ValueError("Architecture method not predeclared")
    frozen = ROOT / f"artifacts/raw/phase0b/placements/{design}/s{seed}"
    placed_v, placed_def = frozen / "placed.v", frozen / "placed.def"
    supplied = ScanArchitecture.from_json(ROOT / f"artifacts/derived/{design}/supplied_architecture.json")
    names = {cell.name for cell in supplied.cells}
    cells = extract_def_scan_cells(placed_def, names, "CK")
    base = ScanArchitecture(cells, supplied.chains)
    ff = {item.name: item for item in scan_ff_instances(placed_v)}
    if set(ff) != names:
        raise ValueError("Placed FF identity differs from frozen supplied architecture")
    fan = ROOT / f"artifacts/raw/tool_qualification/fan_atpg/patterns/FAN_{design}.pat"
    identity = ROOT / f"artifacts/derived/{design}/ff_identity_map.json"
    patterns = map_ppi_patterns(parse_fan_pat(fan), json.loads(identity.read_text())["records"])
    weights = direct_sink_weights(placed_v, {name: item.q_net for name, item in ff.items()})
    contract = ROOT / "config/phase0c_analysis_contract.json"
    contract_sha = sha(contract)
    out = ROOT / f"artifacts/derived/phase0c/{design}/s{seed}/k{k}"
    out.mkdir(parents=True, exist_ok=True)
    rows = []
    for method in methods:
        start = time.perf_counter()
        if method == "B1":
            native_dir = ROOT / f"artifacts/derived/phase0b/{design}/s{seed}"
            qualification = json.loads((native_dir / "B1.native_qualification.json").read_text())
            if qualification.get("status") != "PASS":
                raise ValueError("Frozen OpenROAD-native B1 evidence did not qualify")
            native = ScanArchitecture.from_json(native_dir / "B1.architecture.json")
            if native.cells != base.cells or len(native.chains) != 1:
                raise ValueError("Native B1 does not share the frozen placed FFs")
            arch = ScanArchitecture(base.cells, (ScanChain("C00", native.chains[0].cells,
                                                         "test_si_0", "test_so_0"),))
        else:
            arch = generate_architecture(base, k, method, patterns,
                                         CAMPAIGN["architecture_randomization_seed"])
        arch_path = out / f"{method}.architecture.json"
        arch.to_json(arch_path)
        input_paths = [placed_v, placed_def, fan, identity, contract,
                       ROOT / "config/phase0c_campaign.json",
                       ROOT / "config/phase0c_seed_method.json",
                       ROOT / "config/phase0c_objectives.json",
                       ROOT / "scripts/phase0c_prepare.py",
                       ROOT / "src/pact/scan/phase0c.py",
                       ROOT / "src/pact/analysis/phase0c_activity.py",
                       ROOT / "src/pact/physical/phase0c_port_policy.py",
                       ROOT / "src/pact/physical/phase0c_scan_geometry.py"]
        if method == "B1":
            input_paths += [native_dir / "B1.native_qualification.json", native_dir / "B1.architecture.json"]
        input_hashes = {str(path.relative_to(ROOT)).replace("\\", "/"): sha(path)
                        for path in input_paths}
        row_path = out / f"{method}.proxy.json"
        if row_path.is_file() and not force:
            saved = json.loads(row_path.read_text(encoding="utf-8"))
            if (saved.get("architecture_sha256") == arch.sha256()
                    and saved.get("input_sha256") == input_hashes
                    and saved.get("all_patterns_parallel_load_verified")
                    and saved.get("all_patterns_scan_out_verified")):
                rows.append(saved)
                print(json.dumps({"design": design, "seed": seed, "K": k,
                                  "method": method, "status": "RESUMED_VERIFIED"}), flush=True)
                continue
        state = None
        for target in patterns:
            verification = verify_parallel_schedule(arch, target, state)
            state = target
        activity_start = time.perf_counter()
        activity = parallel_activity_metrics(arch, patterns, weights)
        activity_s = time.perf_counter() - activity_start
        geometry = phase0c_scan_geometry(arch, placed_def)
        row = {
            "schema_version": "phase0c-qualification-1", "design": design,
            "physical_seed": seed, "K": k, "method": method,
            "architecture_sha256": arch.sha256(),
            "run_id": experiment_id(design, seed, k, method, arch.sha256(), contract_sha),
            "architecture_path": str(arch_path.relative_to(ROOT)).replace("\\", "/"),
            "status": "LOGICAL_AND_PROXY_QUALIFIED_PHYSICAL_PENDING",
            "FF_inventory_verified": True,
            "all_patterns_parallel_load_verified": True,
            "all_patterns_scan_out_verified": True,
            "pattern_count": len(patterns),
            "chain_statistics": chain_statistics(arch, len(patterns)),
            "scan_geometry": geometry, "activity": activity,
            "physical": {"exact_scan_only_routed_length_um": None, "congestion": None,
                         "detailed_route_DRC_errors": None},
            "timing": {"setup_wns_ns": None, "hold_wns_ns": None},
            "input_sha256": input_hashes,
        }
        row_path.write_text(json.dumps(row, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        (out / f"{method}.runtime.json").write_text(json.dumps({
            "architecture_sha256": arch.sha256(),
            "generation_verification_and_metrics_s": time.perf_counter() - start,
            "parallel_shift_activity_s": activity_s,
            "host_runtime_is_provenanced_in": "artifacts/manifests/phase0c/tool_qualification.json"
        }, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        rows.append(row)
        print(json.dumps({"design": design, "seed": seed, "K": k, "method": method,
                          "run_id": row["run_id"], "H_eff8": activity["grids"]["8"]["H_eff"]}), flush=True)
    return rows


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--design", choices=CAMPAIGN["designs"], required=True)
    parser.add_argument("--seed", choices=CAMPAIGN["physical_seeds"], type=int, required=True)
    parser.add_argument("--k", choices=CAMPAIGN["K_values"], type=int, required=True)
    parser.add_argument("--methods", nargs="+", default=CAMPAIGN["route_families_each_K"])
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()
    prepare(args.design, args.seed, args.k, args.methods, force=args.force)


if __name__ == "__main__":
    main()
