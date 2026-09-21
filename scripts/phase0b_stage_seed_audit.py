#!/usr/bin/env python3
"""Audit effective placement and global-route seed propagation per pair."""
from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SEEDS = (11, 13, 17, 19, 23)


def read(path: Path) -> dict | None:
    return json.loads(path.read_text(encoding="utf-8")) if path.is_file() else None


def seed_arguments_match(command: list[str], seed: int, method: str,
                         stage: str) -> bool:
    if stage == "placement_perturbation":
        return (f"PACT_PHASE0B_PHYSICAL_SEED={seed}" in command
                and any(f"phase0b_s{seed}_B0/3_place.odb" in arg for arg in command))
    if stage == "global_route":
        return (f"GRT_SEED={seed}" in command
                and f"FLOW_VARIANT=phase0b_s{seed}_{method}" in command)
    raise ValueError(stage)


def main() -> None:
    records = []
    for design in ("s5378", "s9234", "s15850"):
        for seed in SEEDS:
            legacy = ROOT / f"artifacts/raw/phase0b/placements/{design}/s{seed}/execution.json"
            current = ROOT / f"artifacts/raw/phase0b/runs/{design}/s{seed}/physical_seed/execution.json"
            placement_path = current if current.is_file() else legacy
            placement = read(placement_path)
            plan_path = ROOT / f"artifacts/derived/phase0b/{design}/s{seed}/plan.json"
            plan = read(plan_path)
            routes = []
            for method in (plan or {}).get("distinct_route_canonical_methods", []):
                path = ROOT / f"artifacts/raw/phase0b/runs/{design}/s{seed}/{method}_route/execution.json"
                execution = read(path)
                routes.append({"method": method, "record": str(path.relative_to(ROOT)).replace("\\", "/")
                               if execution else None,
                               "seed_propagated": bool(execution and execution.get("exit_code") == 0
                                                       and seed_arguments_match(execution["command"], seed,
                                                                                method, "global_route"))})
            records.append({
                "design": design, "physical_seed": seed,
                "source_global_placement_seed": None,
                "source_global_placement_reused": True,
                "placement_perturbation_record": str(placement_path.relative_to(ROOT)).replace("\\", "/")
                                                 if placement else None,
                "placement_seed_propagated": bool(placement and placement.get("exit_code") == 0
                                                  and seed_arguments_match(placement["command"], seed, "B0",
                                                                           "placement_perturbation")),
                "global_route_records": routes,
                "all_declared_routing_seeds_propagated": bool(routes) and all(r["seed_propagated"] for r in routes),
            })
    result = {"schema_version": "phase0b-stage-seeds-1",
              "source_global_placement_seed": None,
              "placement_stage": "seeded OpenROAD Tcl coordinate perturbation and detailed placement",
              "global_route_stage": "ORFS GRT_SEED feeds set_global_routing_random -seed",
              "detailed_route_seed": None,
              "dft_seed": None,
              "records": records}
    target = ROOT / "artifacts/derived/phase0b/stage_seed_audit.json"
    target.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"placement_seed_pass": sum(r["placement_seed_propagated"] for r in records),
                      "global_route_seed_pass": sum(r["all_declared_routing_seeds_propagated"] for r in records)}))


if __name__ == "__main__":
    main()
