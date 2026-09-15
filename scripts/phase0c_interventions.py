#!/usr/bin/env python3
"""Write an explicitly proxy-only legal-intervention dataset; no training."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from pact.analysis.phase0c_activity import direct_sink_weights, parallel_activity_metrics
from pact.physical.phase0c_scan_geometry import phase0c_scan_geometry
from pact.scan.identity import scan_ff_instances
from pact.scan.model import ScanArchitecture
from pact.scan.phase0c import chain_statistics, verify_parallel_schedule
from pact.scan.phase0c_interventions import apply_intervention, sampled_local_swaps
from pact.test.pattern_parser import map_ppi_patterns, parse_fan_pat


ROOT = Path(__file__).resolve().parents[1]


def operations(arch: ScanArchitecture) -> list[dict]:
    result = [
        {"type": "swap", "chain": 0, "i": 0, "j": 1},
        {"type": "segment_reversal", "chain": 0, "i": 1, "j": 4},
        {"type": "two_opt", "chain": 0, "i": 2, "j": 5},
    ]
    if len(arch.chains) > 1:
        result.append({"type": "cross_chain_exchange", "chain": 0, "other_chain": 1, "i": 0, "j": 0})
        if len(arch.chains[0].cells) > len(arch.chains[1].cells):
            result += [
                {"type": "relocate", "chain": 0, "to_chain": 1, "i": 0, "to_index": 0},
                {"type": "chain_rebalance", "chain": 0, "to_chain": 1, "i": 1, "to_index": 0},
            ]
    return result


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--design", required=True)
    parser.add_argument("--seed", type=int, required=True)
    parser.add_argument("--k", type=int, required=True)
    parser.add_argument("--methods", nargs="+", default=["P", "A"])
    parser.add_argument("--sample-swaps", type=int, default=0)
    parser.add_argument("--screen-only", action="store_true")
    args = parser.parse_args()
    design, seed, k = args.design, args.seed, args.k
    folder = ROOT / f"artifacts/derived/phase0c/{design}/s{seed}/k{k}"
    placed = ROOT / f"artifacts/raw/phase0b/placements/{design}/s{seed}/placed.v"
    placed_def = ROOT / f"artifacts/raw/phase0b/placements/{design}/s{seed}/placed.def"
    ff = {item.name: item for item in scan_ff_instances(placed)}
    weights = direct_sink_weights(placed, {name: item.q_net for name, item in ff.items()})
    fan = parse_fan_pat(ROOT / f"artifacts/raw/tool_qualification/fan_atpg/patterns/FAN_{design}.pat")
    identity = json.loads((ROOT / f"artifacts/derived/{design}/ff_identity_map.json").read_text())["records"]
    patterns = map_ppi_patterns(fan, identity)
    campaign = json.loads((ROOT / "config/phase0c_campaign.json").read_text())
    records = []
    for method in args.methods:
        arch = ScanArchitecture.from_json(folder / f"{method}.architecture.json")
        before = json.loads((folder / f"{method}.proxy.json").read_text())
        sampled = sampled_local_swaps(arch, args.sample_swaps,
                                      campaign["intervention_screen"]["proposal_seed"])
        selected = sampled if args.screen_only else operations(arch) + sampled
        unique = list({json.dumps(operation, sort_keys=True): operation for operation in selected}.values())
        for operation in unique:
            child, intervention = apply_intervention(arch, operation)
            state = None
            for target in patterns:
                verify_parallel_schedule(child, target, state)
                state = target
            activity = parallel_activity_metrics(child, patterns, weights, (8,))
            geometry = phase0c_scan_geometry(child, placed_def)
            stats = chain_statistics(child, len(patterns))
            child_path = folder / f"{method}.{operation['type']}.{child.sha256()[:12]}.architecture.json"
            child.to_json(child_path)
            old_p = before["scan_geometry"]["total_scan_hpwl_um"]
            new_p = geometry["total_scan_hpwl_um"]
            old_a = before["activity"]["grids"]["8"]["H_eff"]
            new_a = activity["grids"]["8"]["H_eff"]
            records.append({
                "schema_version": "phase0c-proxy-intervention-1",
                "design": design, "physical_seed": seed, "K": k,
                "parent_method": method, "parent_architecture_sha256": arch.sha256(),
                "screen_id": "FROZEN_C7_LOCAL_SWAP" if args.screen_only else "EXPLORATORY",
                "child_architecture_sha256": child.sha256(),
                "child_architecture_path": str(child_path.relative_to(ROOT)).replace("\\", "/"),
                "intervention": intervention,
                "status": "STRUCTURAL_AND_PROXY_QUALIFIED_PHYSICAL_PENDING",
                "before": {"scan_hpwl_proxy_um": old_p, "H_eff8_proxy": old_a,
                           "parallel_shift_cycles": before["chain_statistics"]["parallel_shift_cycles"],
                           "setup_wns_ns": None},
                "after": {"scan_hpwl_proxy_um": new_p, "H_eff8_proxy": new_a,
                          "parallel_shift_cycles": stats["parallel_shift_cycles"],
                          "setup_wns_ns": None},
                "delta": {"scan_hpwl_proxy_um": new_p - old_p,
                          "H_eff8_proxy": new_a - old_a,
                          "parallel_shift_cycles": stats["parallel_shift_cycles"] - before["chain_statistics"]["parallel_shift_cycles"],
                          "setup_wns_ns": None},
                "qualified_physical": False,
            })
    output = ROOT / "artifacts/derived/phase0c/intervention_dataset.jsonl"
    output.parent.mkdir(parents=True, exist_ok=True)
    existing = [json.loads(line) for line in output.read_text(encoding="utf-8").splitlines()] if output.exists() else []
    def key(record):
        return (record["design"], record["physical_seed"], record["K"],
                record["parent_architecture_sha256"],
                record.get("screen_id", "EXPLORATORY"),
                json.dumps(record["intervention"]["operation"], sort_keys=True))
    merged = {key(record): record for record in existing}
    merged.update({key(record): record for record in records})
    output.write_text("".join(json.dumps(merged[item], sort_keys=True) + "\n" for item in sorted(merged)),
                      encoding="utf-8")
    print(json.dumps({"records_generated": len(records), "dataset_records": len(merged),
                      "dataset": str(output)}))


if __name__ == "__main__":
    main()
