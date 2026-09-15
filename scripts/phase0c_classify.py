#!/usr/bin/env python3
"""Mechanically classify Phase-0C without promoting incomplete proxy evidence."""
from __future__ import annotations

from collections import Counter, defaultdict
import hashlib
import json
import math
from pathlib import Path
from statistics import median

from pact.scan.model import ScanArchitecture
from pact.scan.phase0c import architecture_space_log10, experiment_id


ROOT = Path(__file__).resolve().parents[1]


def read(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def gate(status: str, reason: str, **numbers) -> dict:
    return {"status": status, "reason": reason, **numbers}


def pareto(rows: list[dict]) -> list[dict]:
    result = []
    for row in rows:
        if not any(other is not row and
                   other["physical_primary_um"] <= row["physical_primary_um"] and
                   other["H_eff8"] <= row["H_eff8"] and
                   (other["physical_primary_um"] < row["physical_primary_um"] or
                    other["H_eff8"] < row["H_eff8"])
                   for other in rows):
            result.append(row)
    return result


def median_iqr(values: list[float]) -> dict:
    if not values:
        return {"n": 0, "median": None, "iqr": None}
    ordered = sorted(values)
    def quantile(q: float) -> float:
        position = q * (len(ordered) - 1)
        lo, hi = math.floor(position), math.ceil(position)
        return ordered[lo] + (ordered[hi] - ordered[lo]) * (position - lo)
    return {"n": len(values), "median": median(ordered),
            "iqr": quantile(.75) - quantile(.25)}


def spearman(xs: list[float], ys: list[float]) -> float | None:
    if len(xs) != len(ys) or len(xs) < 3:
        return None
    def ranks(values):
        order = sorted(range(len(values)), key=lambda i: values[i])
        result = [0.0] * len(values)
        start = 0
        while start < len(order):
            stop = start + 1
            while stop < len(order) and values[order[stop]] == values[order[start]]:
                stop += 1
            rank = (start + stop - 1) / 2
            for position in order[start:stop]:
                result[position] = rank
            start = stop
        return result
    a, b = ranks(xs), ranks(ys)
    mean_a, mean_b = sum(a) / len(a), sum(b) / len(b)
    denominator = math.sqrt(sum((x - mean_a) ** 2 for x in a)
                            * sum((y - mean_b) ** 2 for y in b))
    return sum((x - mean_a) * (y - mean_b) for x, y in zip(a, b)) / denominator if denominator else None


def describe_complete_pairs(complete_pairs: dict) -> tuple[list[dict], dict]:
    pair_summaries = []
    regret = defaultdict(lambda: defaultdict(list))
    pareto_counts = Counter()
    for (design, seed, k), rows in sorted(complete_pairs.items()):
        best_p = min(rows, key=lambda row: (row["physical_primary_um"], row["H_eff8"]))
        best_a = min(rows, key=lambda row: (row["H_eff8"], row["physical_primary_um"]))
        front = pareto(rows)
        pareto_counts.update(row["method"] for row in front)
        method_regrets = {}
        for row in rows:
            p = 100 * (row["physical_primary_um"] - best_p["physical_primary_um"]) / abs(best_p["physical_primary_um"])
            a = 100 * (row["H_eff8"] - best_a["H_eff8"]) / abs(best_a["H_eff8"])
            method_regrets[row["method"]] = {"physical_percent": p, "activity_percent": a}
            regret[row["method"]]["physical_percent"].append(p)
            regret[row["method"]]["activity_percent"].append(a)
        pair_summaries.append({
            "design": design, "physical_seed": seed, "K": k,
            "physical_optimum_method": best_p["method"],
            "activity_optimum_method": best_a["method"],
            "physical_penalty_percent": 100 * (best_a["physical_primary_um"] / best_p["physical_primary_um"] - 1),
            "H_eff_gain_percent": 100 * (1 - best_a["H_eff8"] / best_p["H_eff8"]),
            "pareto_methods": sorted(row["method"] for row in front),
            "method_regrets": method_regrets,
            "spearman_physical_vs_activity": spearman(
                [row["physical_primary_um"] for row in rows],
                [row["H_eff8"] for row in rows]),
            "shift_cycles": rows[0].get("parallel_shift_cycles"),
            "qualified_method_count": len(rows),
        })
    method_stats = {method: {objective: median_iqr(values)
                             for objective, values in objectives.items()}
                    for method, objectives in sorted(regret.items())}
    correlations = [row["spearman_physical_vs_activity"] for row in pair_summaries
                    if row["spearman_physical_vs_activity"] is not None]
    descriptive = {"method_regret": method_stats,
                   "pareto_membership_counts": dict(sorted(pareto_counts.items())),
                   "spearman_physical_vs_activity": median_iqr(correlations)}
    return pair_summaries, descriptive


def proxy_integrity(proxies: list[dict], campaign: dict, contract_sha256: str) -> tuple[bool, dict]:
    expected = {(design, seed, k, method)
                for design in campaign["designs"]
                for seed in campaign["physical_seeds"]
                for k in campaign["K_values"]
                for method in campaign["route_families_each_K"]}
    expected |= {(design, seed, 1, campaign["native_B1_k1_method"])
                 for design in campaign["designs"] for seed in campaign["physical_seeds"]}
    actual = {(row["design"], row["physical_seed"], row["K"], row["method"]) for row in proxies}
    counts = {"missing_rows": len(expected - actual),
              "extra_rows": len(actual - expected),
              "duplicate_rows": len(proxies) - len(actual),
              "invalid_rows": 0}
    if counts["missing_rows"] or counts["extra_rows"] or counts["duplicate_rows"]:
        return False, counts
    hash_cache: dict[str, str] = {}
    for row in proxies:
        try:
            arch = ScanArchitecture.from_json(ROOT / row["architecture_path"])
            arch_sha = arch.sha256()
            if (arch_sha != row["architecture_sha256"] or
                    row["run_id"] != experiment_id(row["design"], row["physical_seed"],
                                                   row["K"], row["method"], arch_sha,
                                                   contract_sha256) or
                    not all(row.get(key) for key in ("FF_inventory_verified",
                                                     "all_patterns_parallel_load_verified",
                                                     "all_patterns_scan_out_verified"))):
                counts["invalid_rows"] += 1
                continue
            hashes = row.get("input_sha256", {})
            if not hashes:
                counts["invalid_rows"] += 1
                continue
            for relative, expected_sha in hashes.items():
                if relative not in hash_cache:
                    hash_cache[relative] = hashlib.sha256((ROOT / relative).read_bytes()).hexdigest()
                if hash_cache[relative] != expected_sha:
                    counts["invalid_rows"] += 1
                    break
        except (KeyError, OSError, ValueError):
            counts["invalid_rows"] += 1
    return counts["invalid_rows"] == 0, counts


def classify() -> dict:
    campaign = read(ROOT / "config/phase0c_campaign.json")
    contract_path = ROOT / "config/phase0c_analysis_contract.json"
    contract = read(contract_path)
    proxies = [read(path) for path in sorted((ROOT / "artifacts/derived/phase0c").glob("*/s*/k*/*.proxy.json"))]
    planned_new = len(campaign["designs"]) * len(campaign["physical_seeds"]) * len(campaign["K_values"]) * len(campaign["route_families_each_K"])
    planned_native = len(campaign["designs"]) * len(campaign["physical_seeds"])
    planned = planned_new + planned_native
    routed = []
    superseded_routes = 0
    rewire_hash = hashlib.sha256((ROOT / "scripts/phase0c_rewire_odb.py").read_bytes()).hexdigest()[:8]
    execution = ROOT / "artifacts/manifests/phase0c/campaign_execution.json"
    final_prefix = (f"phase0c_f{read(execution)['freeze_commit'][:8]}"
                    if execution.exists() else "phase0c")
    for path in sorted((ROOT / "artifacts/raw/phase0c").glob("physical/*/s*/k*/*/route_metrics.json")):
        record = read(path)
        if record.get("status") == "QUALIFIED" and record.get("DRC_errors") == 0:
            expected = (f"{final_prefix}_s{record['physical_seed']}_k{record['K']}_{record['method']}_"
                        f"{record['architecture_sha256'][:8]}_{rewire_hash}")
            proof_path = ROOT / record["postroute_verification"] if record.get("postroute_verification") else None
            proof = read(proof_path) if proof_path and proof_path.is_file() else {}
            archive = ROOT / record["routed_odb_archive"] if record.get("routed_odb_archive") else None
            archive_valid = (archive is not None and archive.is_file()
                             and hashlib.sha256(archive.read_bytes()).hexdigest()
                             == record.get("routed_odb_gzip_sha256")) if execution.exists() else True
            if (record.get("variant") == expected and proof.get("status") == "PASS"
                    and (not execution.exists() or proof.get("fixed_port_positions_verified"))
                    and archive_valid):
                routed.append(record)
            else:
                superseded_routes += 1
    by_identity = {(row["design"], row["physical_seed"], row["K"], row["method"]): row for row in proxies}
    joined = []
    for physical in routed:
        key = (physical["design"], physical["physical_seed"], physical["K"], physical["method"])
        proxy = by_identity.get(key)
        if proxy and proxy["architecture_sha256"] == physical.get("architecture_sha256"):
            joined.append({**physical, "H_eff8": proxy["activity"]["grids"]["8"]["H_eff"],
                           "parallel_shift_cycles": proxy["chain_statistics"]["parallel_shift_cycles"]})
    pair_rows = defaultdict(list)
    for row in joined:
        pair_rows[(row["design"], row["physical_seed"], row["K"])].append(row)
    complete_pairs = {key: rows for key, rows in pair_rows.items()
                      if {r["method"] for r in rows} >=
                      (set(campaign["route_families_each_K"]) |
                      ({campaign["native_B1_k1_method"]} if key[2] == 1 else set()))}
    pair_summaries, descriptive = describe_complete_pairs(complete_pairs)
    c = {}
    expected_proxies = planned
    integrity, integrity_counts = proxy_integrity(proxies, campaign,
                                                   hashlib.sha256(contract_path.read_bytes()).hexdigest())
    execution_intact = False
    if execution.exists():
        frozen_hashes = read(execution).get("frozen_input_sha256", {})
        execution_intact = bool(frozen_hashes) and all(
            (ROOT / name).is_file() and hashlib.sha256((ROOT / name).read_bytes()).hexdigest() == saved
            for name, saved in frozen_hashes.items())
    c["C1"] = gate("PASS" if integrity and execution_intact and
                   contract["status"] == "FROZEN_FOR_FINAL_CAMPAIGN" else "NOT QUALIFIED",
                   "all planned proxy rows, structural checks, provenance and frozen contract required",
                   proxy_rows=len(proxies), expected_proxy_rows=expected_proxies,
                   execution_manifest_intact=execution_intact, **integrity_counts)
    route_fraction = len(joined) / planned if planned else 0
    planned_pairs = len(campaign["designs"]) * len(campaign["physical_seeds"]) * len(campaign["K_values"])
    complete_pair_fraction = len(complete_pairs) / planned_pairs if planned_pairs else 0
    c["C2"] = gate("PASS" if route_fraction >= contract["C2"]["minimum_route_completion_fraction"]
                   and complete_pair_fraction >= contract["C2"]["minimum_complete_pair_fraction"]
                   and len({r["design"] for r in joined}) >= contract["C2"]["minimum_complete_designs"]
                   else "NOT QUALIFIED",
                   f"qualified routes compared with predeclared {planned}-row matrix",
                   qualified_new_routes=len(joined), planned_routes=planned,
                   completion_fraction=route_fraction,
                   complete_pairs=len(complete_pairs), planned_pairs=planned_pairs,
                   complete_pair_fraction=complete_pair_fraction)
    practical = defaultdict(int)
    conflicts = []
    if c["C2"]["status"] == "PASS":
        for key, rows in complete_pairs.items():
            physical = min(rows, key=lambda row: (row["physical_primary_um"], row["H_eff8"]))
            activity = min(rows, key=lambda row: (row["H_eff8"], row["physical_primary_um"]))
            p_penalty = 100 * (activity["physical_primary_um"] / physical["physical_primary_um"] - 1)
            a_gain = 100 * (1 - activity["H_eff8"] / physical["H_eff8"])
            hit = (p_penalty >= contract["C3"]["physical_penalty_min_percent"] and
                   a_gain >= contract["C3"]["H_eff_improvement_min_percent"])
            practical[(key[0], key[1])] += int(hit)
            conflicts.append({"design": key[0], "physical_seed": key[1], "K": key[2],
                              "physical_penalty_percent": p_penalty, "H_eff_gain_percent": a_gain,
                              "practical_conflict": hit})
    hit_seeds = {design: {seed for (d, seed), count in practical.items() if d == design and count > 0}
                 for design in campaign["designs"]}
    replicated = [design for design, seeds in hit_seeds.items()
                  if len(seeds) >= contract["C4"]["minimum_supporting_seeds_per_design"]]
    c["C3"] = gate("PASS" if any(x["practical_conflict"] for x in conflicts) else
                   "FAIL" if c["C2"]["status"] == "PASS" else "NOT QUALIFIED",
                   "both 5% effective-activity improvement and 10% physical penalty required",
                   practical_hits=sum(x["practical_conflict"] for x in conflicts), assessed_pairs=len(conflicts))
    c["C4"] = gate("PASS" if replicated else "FAIL" if c["C2"]["status"] == "PASS" else "NOT QUALIFIED",
                   "at least 4 of 5 physical seeds on one design", replicated_designs=replicated,
                   qualifying_seed_counts={d: len(s) for d, s in hit_seeds.items()})
    c["C5"] = gate("PASS" if len(replicated) >= contract["C5"]["minimum_replicated_designs"] else
                   "FAIL" if c["C2"]["status"] == "PASS" else "NOT QUALIFIED",
                   "at least two designs satisfy C4", replicated_design_count=len(replicated))
    coverage = Counter()
    portfolio_covered = 0
    for rows in complete_pairs.values():
        front = pareto(rows)
        epsilon = contract["C6"]["simple_heuristic_epsilon_fraction"]
        portfolio = [r for r in rows if r["method"] in contract["C6"]["portfolio_methods"]]
        if all(any(candidate["physical_primary_um"] <= (1 + epsilon) * p["physical_primary_um"]
                   and candidate["H_eff8"] <= (1 + epsilon) * p["H_eff8"]
                   for candidate in portfolio) for p in front):
            portfolio_covered += 1
        for method in contract["C6"]["methods"]:
            ours = next((r for r in rows if r["method"] == method), None)
            if ours and all(ours["physical_primary_um"] <= (1 + epsilon) * p["physical_primary_um"]
                            and ours["H_eff8"] <= (1 + epsilon) * p["H_eff8"]
                            for p in front):
                coverage[method] += 1
    max_cover = max(coverage.values(), default=0) / max(1, len(complete_pairs))
    portfolio_fraction = portfolio_covered / max(1, len(complete_pairs))
    c["C6"] = gate("NOT QUALIFIED" if c["C2"]["status"] != "PASS" else
                   "PASS" if max_cover < contract["C6"]["maximum_fraction_of_pairs_covered_by_one_simple_heuristic"]
                   and portfolio_fraction < contract["C6"]["maximum_fraction_of_pairs_covered_by_deterministic_portfolio"]
                   else "FAIL",
                   "neither one simple heuristic nor their fixed portfolio may epsilon-cover all Pareto points in 80% of complete cases",
                   complete_pairs=len(complete_pairs), max_simple_heuristic_coverage=max_cover,
                   deterministic_portfolio_coverage=portfolio_fraction,
                   per_method_coverage=dict(coverage))
    dataset = ROOT / "artifacts/derived/phase0c/intervention_dataset.jsonl"
    interventions = [json.loads(line) for line in dataset.read_text(encoding="utf-8").splitlines()] if dataset.exists() else []
    qualified_parents = {(r["design"], r["physical_seed"], r["K"], r["method"],
                          r["architecture_sha256"]) for r in joined}
    eligible = [r for r in interventions
                if r.get("screen_id") == "FROZEN_C7_LOCAL_SWAP"
                and r.get("status") == "STRUCTURAL_AND_PROXY_QUALIFIED_PHYSICAL_PENDING"
                and r.get("delta", {}).get("scan_hpwl_proxy_um") is not None
                and (r["design"], r["physical_seed"], r["K"], r["parent_method"],
                     r["parent_architecture_sha256"]) in qualified_parents]
    by_context = defaultdict(list)
    for record in eligible:
        by_context[(record["design"], record["physical_seed"], record["K"],
                    record["intervention"]["type"])].append(record["delta"]["scan_hpwl_proxy_um"])
    reversals = defaultdict(set)
    for (design, seed, k, kind), values in by_context.items():
        min_n = contract["C7"]["minimum_matched_interventions_per_pair"]
        fraction = contract["C7"]["minimum_opposite_sign_fraction_per_class"]
        if len(values) >= min_n and sum(v > 0 for v in values) / len(values) >= fraction and sum(v < 0 for v in values) / len(values) >= fraction:
            reversals[design].add(seed)
    c7_designs = sum(len(seeds) >= contract["C7"]["minimum_seeds_per_design"] for seeds in reversals.values())
    c["C7"] = gate("NOT QUALIFIED" if c["C2"]["status"] != "PASS" else
                   "PASS" if c7_designs >= contract["C7"]["minimum_designs"] else "FAIL",
                   "material opposite-sign port-aware HPWL proxy deltas around qualified routed parents required; children are structurally verified but not routed",
                   qualified_parent_proxy_interventions=len(eligible), qualifying_design_count=c7_designs)
    manifest = read(ROOT / "artifacts/manifests/phase0b/benchmark_manifest.json")
    space = {row["design"]: {str(k): architecture_space_log10(row["scan_ff_count"], k)
                              for k in campaign["K_values"]} for row in manifest["designs"]}
    c["C8"] = gate("PASS" if all(max(values.values()) >= contract["C8"]["minimum_log10_legal_architectures"]
                                   for values in space.values()) else "FAIL",
                   "combinatorial lower-bound scale of ordered labelled nonempty chains",
                   log10_architecture_counts=space)
    go = all(c[f"C{i}"]["status"] == "PASS" for i in range(1, 9))
    c["C9"] = gate("PASS" if go else "FAIL", "all C1-C8 must pass")
    return {"schema_version": "phase0c-analysis-1",
            "contract_sha256": hashlib.sha256(contract_path.read_bytes()).hexdigest(),
            "campaign_status": campaign["status"],
            "proxy_rows": len(proxies), "qualified_new_routes": len(joined),
            "superseded_qualified_routes": superseded_routes,
            "planned_comparison_rows": planned, "intervention_records": len(interventions),
            "conflicts": conflicts, "gates": c,
            "complete_pair_descriptives": pair_summaries,
            "descriptive_statistics": descriptive,
            "classification": "PACT_PHASE0C_LEARNING_GATE_PASS" if go else "PACT_PHASE0C_LEARNING_GATE_FAIL"}


def main() -> None:
    result = classify()
    target = ROOT / "artifacts/derived/phase0c/gate_analysis.json"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(result["classification"])


if __name__ == "__main__":
    main()
