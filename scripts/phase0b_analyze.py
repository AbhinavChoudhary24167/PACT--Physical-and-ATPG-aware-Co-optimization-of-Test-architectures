#!/usr/bin/env python3
"""Generate evidence-linked Phase-0B pair, replication, and GO/NO-GO fields."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

from pact.analysis.phase0b_conflict import classify_pair, paired_effect_summary


ROOT = Path(__file__).resolve().parents[1]
CONFIG = json.loads((ROOT / "config/phase0b_campaign.json").read_text(encoding="utf-8"))
DESIGNS = CONFIG["designs_predeclared"]
SEEDS = CONFIG["physical_seeds"]
CONFIG_SHA256 = hashlib.sha256((ROOT / "config/phase0b_campaign.json").read_bytes()).hexdigest()
SEED_METHOD_SHA256 = hashlib.sha256((ROOT / "config/phase0b_seed_method.json").read_bytes()).hexdigest()


def read(path: Path) -> dict | None:
    return json.loads(path.read_text(encoding="utf-8")) if path.is_file() else None


def rel(path: Path) -> str:
    return str(path.relative_to(ROOT)).replace("\\", "/")


def evidence_matches_pair(design: str, seed: int, method: str, architecture_sha256: str,
                          verification: dict, metrics: dict, route: dict) -> bool:
    """Reject accidentally cross-paired seeds, methods, or architectures."""
    return (verification.get("status") == "PASS"
            and verification.get("design") == design
            and verification.get("physical_seed") == seed
            and verification.get("method") == method
            and verification.get("architecture_sha256") == architecture_sha256
            and metrics.get("design") == design
            and metrics.get("physical_seed") == seed
            and metrics.get("method") == method
            and route.get("design") == design
            and route.get("physical_seed") == seed
            and route.get("method") == method
            and route.get("architecture_sha256") == architecture_sha256)


def plan_matches_contract(plan: dict, design: str, seed: int) -> bool:
    return (plan.get("design") == design and plan.get("physical_seed") == seed
            and plan.get("phase0b_config_sha256") == CONFIG_SHA256
            and plan.get("seed_method_sha256") == SEED_METHOD_SHA256
            and all(row.get("design") == design and row.get("physical_seed") == seed
                    for row in plan.get("rows", [])))


def analyze_pair(design: str, seed: int) -> dict[str, object]:
    folder = ROOT / f"artifacts/derived/phase0b/{design}/s{seed}"
    plan_path = folder / "plan.json"
    plan = read(plan_path)
    if plan is None:
        return {"design": design, "physical_seed": seed, "status": "NOT_STARTED",
                "complete": False, "strict_conflict": False,
                "practically_meaningful_conflict": False, "qualified_rows": []}
    if not plan_matches_contract(plan, design, seed):
        return {"design": design, "physical_seed": seed, "status": "PLAN_CONTRACT_MISMATCH",
                "complete": False, "strict_conflict": False,
                "practically_meaningful_conflict": False, "qualified_rows": [],
                "excluded_methods": {"plan": "CAMPAIGN_SEED_METHOD_OR_PAIR_IDENTITY_MISMATCH"}}
    required = plan["distinct_route_canonical_methods"]
    by_method = {row["method"]: row for row in plan["rows"] if row["method"] == row["canonical_method"]}
    rows = []
    excluded = {}
    for method in required:
        row = by_method[method]
        physical = ROOT / f"artifacts/raw/phase0b/physical/{design}/s{seed}/{method}"
        verification_path = folder / f"{method}.rewire_verification.json"
        metric_path = physical / "structured_metrics.json"
        route_path = physical / "scan_route_metrics.json"
        verification, metrics, route = read(verification_path), read(metric_path), read(route_path)
        missing = [label for label, value in (("verification", verification), ("structured_metrics", metrics),
                                               ("scan_route_metrics", route)) if value is None]
        if missing:
            excluded[method] = f"MISSING_{'_'.join(missing).upper()}"
            continue
        if not evidence_matches_pair(design, seed, method, row["architecture_sha256"], verification, metrics, route):
            excluded[method] = "VERIFICATION_FAILED_OR_PAIRED_EVIDENCE_MISMATCH"
            continue
        if metrics["detailed_route_drc_errors"] != 0:
            excluded[method] = "NONZERO_DETAILED_ROUTE_DRC"
            continue
        rows.append({
            "method": method, "architecture_sha256": row["architecture_sha256"],
            "run_id": row["run_id"],
            "scan_hpwl_proxy_um": row["primary_physical_proxy_scan_hpwl_um"],
            "H8": row["shift_activity"]["spatial_by_grid"]["8"]["distance_weighted_hotspot"],
            "total_shift_toggles": row["shift_activity"]["total_shift_toggles"],
            "Smax": row["shift_activity"]["peak_simultaneous_toggles"],
            "routed_scan_net_only_length_um": route["routed_scan_net_only_length_um"],
            "routed_scan_classification": route["classification"],
            "total_detailed_route_wirelength_um": metrics["total_detailed_route_wirelength_um"],
            "setup_wns_ns": metrics["setup_wns_ns"],
            "hold_wns_ns": metrics["hold_wns_ns"],
            "drc_errors": metrics["detailed_route_drc_errors"],
            "congestion": metrics["congestion"],
            "evidence": [rel(path) for path in (plan_path, verification_path, metric_path, route_path)],
        })
    exact_all = len(rows) >= 2 and all(row["routed_scan_classification"] == "QUALIFIED_EXACT_SCAN_ONLY" for row in rows)
    kind = "qualified_routed_scan_net_only_length_um" if exact_all else "scan_hpwl_proxy_um"
    for row in rows:
        row["primary_physical_cost_um"] = (row["routed_scan_net_only_length_um"] if exact_all
                                           else row["scan_hpwl_proxy_um"])
    pair = {
        "design": design, "physical_seed": seed,
        "physical_seed_method": "seeded_placement_perturb_and_legalize",
        "primary_physical_metric": kind,
        "primary_activity_metric": "distance_weighted_hotspot_grid8",
        "requested_routed_methods": required,
        "qualified_routed_methods": [row["method"] for row in rows],
        "excluded_methods": excluded,
        "complete": len(rows) == len(required),
        "status": "COMPLETE" if len(rows) == len(required) else "INCOMPLETE",
        "qualified_rows": rows,
        "proxy_only_methods": [row["method"] for row in plan["rows"]
                               if row["method"] not in required],
        "plan_evidence": rel(plan_path),
    }
    if len(rows) >= 2:
        pair.update(classify_pair(rows,
            physical_penalty_min_pct=CONFIG["meaningful_conflict_rule"]["physical_cost_penalty_min_pct"],
            hotspot_improvement_min_pct=CONFIG["meaningful_conflict_rule"]["hotspot_improvement_min_pct"]))
    else:
        pair.update({"strict_conflict": False, "practically_meaningful_conflict": False,
                     "pareto_methods": [], "pareto_architecture_sha256": []})
    return pair


def main() -> None:
    pairs = [analyze_pair(design, seed) for design in DESIGNS for seed in SEEDS]
    design_summaries = {}
    for design in DESIGNS:
        design_pairs = [pair for pair in pairs if pair["design"] == design]
        completed = [pair for pair in design_pairs if pair["complete"]]
        qualification = read(ROOT / f"artifacts/derived/phase0b/{design}/physical_seed_qualification.json")
        hashes = (qualification or {}).get("observed_component_placement_hashes", {})
        distinct = bool(qualification and qualification["all_completed_placements_distinct"]
                        and qualification["completed_physical_seeds"] == len(SEEDS)
                        and set(hashes) == {str(seed) for seed in SEEDS}
                        and len(set(hashes.values())) == len(SEEDS))
        meaningful = sum(pair["practically_meaningful_conflict"] for pair in completed)
        non_p_frontiers = sum(any(method != "P" for method in pair["pareto_methods"]) for pair in completed)
        full = len(completed) == len(SEEDS) and distinct
        design_summaries[design] = {
            "completed_physical_seeds": len(completed),
            "distinct_placement_qualification": distinct,
            "meaningful_conflict_seed_count": meaningful,
            "strict_conflict_seed_count": sum(pair["strict_conflict"] for pair in completed),
            "non_P_frontier_seed_count": non_p_frontiers,
            "replication_assessable": full,
            "replicated_within_design": full and meaningful >= 4,
            "simple_heuristic_not_trivially_sufficient": full and non_p_frontiers >= 4,
            "paired_effects": paired_effect_summary(completed),
            "evidence": rel(ROOT / f"artifacts/derived/phase0b/{design}/physical_seed_qualification.json")
                        if qualification else None,
        }
    complete_designs = sum(summary["replication_assessable"] for summary in design_summaries.values())
    replicated_designs = sum(summary["replicated_within_design"] for summary in design_summaries.values())
    g5 = complete_designs == len(DESIGNS) and all("B1" in pair.get("qualified_routed_methods", [])
                                                   for pair in pairs if pair["complete"])
    g6 = any(pair["complete"] and pair["practically_meaningful_conflict"] for pair in pairs)
    g7a = replicated_designs >= 1
    g7b = replicated_designs >= 2
    g8 = sum(summary["simple_heuristic_not_trivially_sufficient"] for summary in design_summaries.values()) >= 2
    go = g5 and g6 and g7a and g7b and g8
    complete_campaign = complete_designs == len(DESIGNS)
    classification = ("PACT_PHASE0B_CONFLICT_REPLICATED_PHASE1_GO" if go else
                      "PACT_PHASE0B_CONFLICT_NOT_REPLICATED_PHASE1_NO_GO" if complete_campaign else
                      "PACT_PHASE0B_INCOMPLETE_PHASE1_NO_GO")
    result = {
        "schema_version": "phase0b-1",
        "config_sha256": CONFIG_SHA256,
        "analysis_contract_sha256": hashlib.sha256((ROOT / "config/phase0b_analysis_contract.json").read_bytes()).hexdigest(),
        "design_summaries": design_summaries,
        "pairs": pairs,
        "completed_designs": complete_designs,
        "completed_design_seed_pairs": sum(pair["complete"] for pair in pairs),
        "qualified_physically_routed_architecture_count": sum(len(pair["qualified_rows"]) for pair in pairs),
        "routed_scan_net_only_available_pair_count": sum(pair.get("primary_physical_metric") == "qualified_routed_scan_net_only_length_um" for pair in pairs),
        "structured_congestion_available_pair_count": sum(bool(pair["qualified_rows"]) and all(row["congestion"] is not None for row in pair["qualified_rows"]) for pair in pairs),
        "qualified_power_integrity_available": False,
        "G5_baseline_architecture_set_established": g5,
        "G6_meaningful_physically_implemented_conflict": g6,
        "G7a_replicated_within_design": g7a,
        "G7b_replicated_across_designs": g7b,
        "G8_simple_heuristics_not_trivially_sufficient": g8,
        "replicated_across_designs": g7b,
        "phase1_go": go,
        "classification": classification,
    }
    target = ROOT / "artifacts/derived/phase0b/conflict_analysis.json"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({key: result[key] for key in ("completed_design_seed_pairs", "qualified_physically_routed_architecture_count", "classification")}, sort_keys=True))


if __name__ == "__main__":
    main()
