#!/usr/bin/env python3
"""Render the Phase-0B decision report from frozen machine-readable records."""
from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
REPORT = ROOT / "reports/PHASE0B_CONFLICT_ESTABLISHMENT_REPORT.md"


def read(relative: str) -> dict:
    return json.loads((ROOT / relative).read_text(encoding="utf-8"))


def link(relative: str, label: str | None = None) -> str:
    return f"[{label or Path(relative).name}](../{relative})"


def num(value, digits: int = 2) -> str:
    return "unavailable" if value is None else f"{value:,.{digits}f}"


def yn(value: bool) -> str:
    return "yes" if value else "no"


def pair_table(pairs: list[dict]) -> str:
    lines = ["| Design | Physical seed | Qualified routes | Physical optimum | H8 optimum | H8 gain | Physical penalty | Strict / practical | A/B/C/D | Pareto methods | Evidence |",
             "|---|---:|---:|---|---|---:|---:|---|---|---|---|"]
    for pair in pairs:
        folder = f"artifacts/derived/phase0b/{pair['design']}/s{pair['physical_seed']}"
        if pair["complete"]:
            gain = f"{num(pair['H8_absolute_improvement_vs_physical_optimum'], 4)} ({num(pair['H8_percent_improvement_vs_physical_optimum'])}%)"
            penalty = f"{num(pair['physical_absolute_penalty_um_for_H8_optimum'])} µm ({num(pair['physical_percent_penalty_for_H8_optimum'])}%)"
            abcd = "/".join("1" if pair[key] else "0" for key in
                            ("A_physical_optimum_also_minimizes_H8", "B_H8_optimum_also_minimizes_physical",
                             "C_distinct_architectures_on_frontier", "D_joint_meaningfully_dominates_single_objective"))
            lines.append(f"| {pair['design']} | {pair['physical_seed']} | {len(pair['qualified_rows'])} | {pair['physical_optimum_method']} | {pair['H8_optimum_method']} | {gain} | {penalty} | {yn(pair['strict_conflict'])} / {yn(pair['practically_meaningful_conflict'])} | {abcd} | {', '.join(pair['pareto_methods'])} | {link(folder + '/plan.json', 'plan')} |")
        else:
            reason = ", ".join(f"{k}: {v}" for k, v in pair.get("excluded_methods", {}).items())
            lines.append(f"| {pair['design']} | {pair['physical_seed']} | {len(pair['qualified_rows'])} | — | — | — | — | not assessable | — | — | {link(folder + '/plan.json', 'plan') if (ROOT / folder / 'plan.json').is_file() else 'not started'}{'; ' + reason if reason else ''} |")
    return "\n".join(lines)


def design_effect_table(summaries: dict) -> str:
    lines = ["| Design | Complete seeds | Strict | Practical | Median H8 gain (IQR) | Median physical penalty (IQR) | Exploratory 95% bootstrap CI, H8 gain |",
             "|---|---:|---:|---:|---:|---:|---|"]
    for design, s in summaries.items():
        effects = s["paired_effects"]
        if effects["n_physical_seeds"]:
            h = effects["H8_percent_improvement"]
            p = effects["physical_percent_penalty"]
            ci = h["bootstrap_median_ci95"]
            cis = f"{num(ci[0])}–{num(ci[1])}%" if ci else "not calculated (fewer than five seeds)"
            lines.append(f"| {design} | {s['completed_physical_seeds']}/5 | {s['strict_conflict_seed_count']} | {s['meaningful_conflict_seed_count']} | {num(h['median'])}% ({num(h['iqr'])} points) | {num(p['median'])}% ({num(p['iqr'])} points) | {cis} |")
        else:
            lines.append(f"| {design} | 0/5 | 0 | 0 | unavailable | unavailable | not calculated |")
    return "\n".join(lines)


def main() -> None:
    analysis = read("artifacts/derived/phase0b/conflict_analysis.json")
    config = read("config/phase0b_campaign.json")
    manifest = read("artifacts/manifests/phase0b/benchmark_manifest.json")
    bootstrap = read("artifacts/manifests/phase0b/campaign_manifest.json")
    native = list((ROOT / "artifacts/derived/phase0b").glob("*/s*/B1.native_qualification.json"))
    native_pass = sum(read(str(p.relative_to(ROOT)).replace("\\", "/"))["status"] == "PASS" for p in native)
    route_files = list((ROOT / "artifacts/raw/phase0b/physical").glob("*/s*/*/5_2_route.odb"))
    fully_complete = analysis["completed_design_seed_pairs"] == len(config["designs_predeclared"]) * len(config["physical_seeds"])
    benchmark_rows = []
    for row in manifest["designs"]:
        source = row["evidence"][0]
        report = row["evidence"][2]
        translation = row["compatibility_translations"][0]
        benchmark_rows.append(f"| {row['design']} | {row['scan_ff_count']} | {row['pattern_count']} | {num(row['stuck_at_coverage_percent'])}% | {link(source['path'], source['sha256'][:12])} | {link(report['path'], 'FAN report')} | {translation['instance_count']} BUF_X3→BUF_X4 |")
    benchmark_table = "\n".join(["| Design | Scan FFs | Patterns | Stuck-at coverage | Frozen source SHA256 prefix | ATPG evidence | Explicit compatibility translation |",
                                 "|---|---:|---:|---:|---|---|---|"] + benchmark_rows)
    figures = "\n".join(f"- **{d}:** " + ", ".join(link(f"reports/figures/phase0b/{d}/{name}.png", label)
        for name, label in (("physical_vs_H8", "physical vs H8"), ("pareto_frontier", "Pareto"),
                            ("scan_chain_overlays", "scan overlays"), ("activity_heatmaps", "activity heatmaps"),
                            ("congestion_comparison", "congestion"), ("physical_seed_variability", "seed variability"),
                            ("routed_scan_length_comparison", "routed scan length"),
                            ("timing_comparison", "timing"))) for d in config["designs_predeclared"])
    gates = [("G5 baseline set", analysis["G5_baseline_architecture_set_established"]),
             ("G6 meaningful routed conflict", analysis["G6_meaningful_physically_implemented_conflict"]),
             ("G7a within-design replication", analysis["G7a_replicated_within_design"]),
             ("G7b cross-design replication", analysis["G7b_replicated_across_designs"]),
             ("G8 nontrivial heuristic landscape", analysis["G8_simple_heuristics_not_trivially_sufficient"])]
    gate_rows = "\n".join(f"| {name} | {'PASS' if passed else 'FAIL / not established'} |" for name, passed in gates)
    practical = sum(p["complete"] and p["practically_meaningful_conflict"] for p in analysis["pairs"])
    strict = sum(p["complete"] and p["strict_conflict"] for p in analysis["pairs"])
    complete_pairs = [p for p in analysis["pairs"] if p["complete"]]
    practical_pairs = [p for p in complete_pairs if p["practically_meaningful_conflict"]]
    practical_detail = (f"The {len(practical_pairs)} threshold hits have primary physical-cost penalties from "
                        f"{num(min(p['physical_percent_penalty_for_H8_optimum'] for p in practical_pairs))}% to "
                        f"{num(max(p['physical_percent_penalty_for_H8_optimum'] for p in practical_pairs))}%. "
                        f"{'No design reaches the four-seed replication threshold.' if not analysis['G7a_replicated_within_design'] else ''}"
                        if practical_pairs else "No complete pair satisfies both practical-effect thresholds.")
    joint_vs_p = sum(p["D_joint_meaningfully_dominates_P"] for p in complete_pairs)
    joint_vs_a = sum(p["D_joint_meaningfully_dominates_A"] for p in complete_pairs)
    joint_vs_both = sum(p["D_joint_meaningfully_dominates_both"] for p in complete_pairs)
    all_proxy = analysis["routed_scan_net_only_available_pair_count"] == 0
    methods = sorted({r["method"] for p in complete_pairs for r in p["qualified_rows"]})
    classification = analysis["classification"]
    heuristic_answer = ("Insufficiency is not established. P is not the sole Pareto architecture in ≥4 seeds on two designs, so the narrow G8 rule passes; the surviving candidates are themselves deterministic heuristics."
                        if analysis["G8_simple_heuristics_not_trivially_sufficient"] else
                        "The predeclared G8 rule is not met; simple heuristic sufficiency remains unresolved or P often dominates the qualified frontier.")
    recommendation = ("The predeclared gate permits consideration of Phase 1; these ISCAS89 observations still require broader benchmark and test-power validation."
                      if analysis["phase1_go"] else
                      "The completed campaign does not replicate a practically meaningful conflict under its predeclared gate. Prioritize a better test-power/current objective, multi-chain partitioning or compression, timing-aware insertion, and larger licensed benchmarks before reconsidering ML."
                      if fully_complete else
                      "Complete every predeclared seed and qualified metric before revisiting the gate. If conflict still fails, prioritize a better test-power/current objective, multi-chain partitioning or compression, timing-aware insertion, and larger licensed benchmarks.")
    text = f"""# PACT Phase-0B: establishing the physical–ATPG activity conflict

**Decision:** {'Phase 1 GO' if analysis['phase1_go'] else 'Phase 1 NO-GO'}. The predeclared learning gate is {'satisfied' if analysis['phase1_go'] else 'not satisfied'}. This report is generated by `scripts/phase0b_report.py` from the {link('artifacts/derived/phase0b/conflict_analysis.json', 'pair-by-pair analysis')}; its final classification is the script's `classification` field. {'All 15 predeclared design×seed pairs are complete.' if fully_complete else 'The campaign is incomplete, so absence of replication is not a conclusive null result.'} No ML, surrogate, GNN, reinforcement-learning, or policy training was performed.

## Frozen scope and research contract

The Phase-0 pre-edit Git commit was `{bootstrap['phase0_pre_edit_commit']['stdout']}` and the working tree was observed clean before additive Phase-0B work. The {link('artifacts/manifests/phase0b/campaign_manifest.json', 'campaign manifest')} verified all {bootstrap['phase0_evidence_file_count']} frozen Phase-0 file checksums; OpenROAD, ORFS, FAN, Yosys, and Python versions are recorded there and in the {link('artifacts/manifests/phase0b/runtime_supplement.json', 'actual WSL runtime supplement')}. Every architecture has a canonical hash and deterministic run ID in its plan. Failed attempts remain under `artifacts/raw/phase0b/runs/`.

The {link('config/phase0b_campaign.json', 'predeclared campaign')} fixes physical seeds 11, 13, 17, 19, 23; B0/B1/P/S/A/J25/J50/J75/Rstar; and the physical metric priority. Exact routed scan-only length is primary only if every qualified member of a pair admits exclusive Q→SI extraction; otherwise the primary physical value is **scan HPWL proxy** for the whole pair. The primary activity objective is the exact serial-shift, 8×8 distance-weighted H8 hotspot. The {link('config/phase0b_analysis_contract.json', 'analysis contract')} requires a distinct H8 optimum with at least 5% H8 improvement and at least 10% physical penalty relative to the physical optimum, in at least four of five physical seeds and on two designs. This deliberately conservative engineering threshold was frozen before the final routes. Strict numerical disagreement alone does not satisfy it.

Physical replicas were generated by independent seeded 40%-instance ±8 µm placement perturbations from one common source placement, followed by OpenROAD detailed placement and placement checks; see the {link('config/phase0b_seed_method.json', 'seed-method record')}. This is conditional replication around one source placement, not five fresh global-placement optimizations. Every architecture in a design×seed pair starts from the same frozen placed ODB, and each ORFS global route receives the matching `GRT_SEED`; the {link('artifacts/derived/phase0b/stage_seed_audit.json', 'stage-seed audit')} checks the saved command arguments. The distinct component-coordinate hashes are in each design's `physical_seed_qualification.json`. Ordering seeds for Rstar are a separate, predeclared set and are never treated as physical replicas.

## Benchmarks and test quality

{benchmark_table}

All three sources came from the pinned [FAN_ATPG repository]({manifest['designs'][0]['upstream_repository']}); the source URL for each is in the {link('artifacts/manifests/phase0b/benchmark_manifest.json', 'benchmark manifest')}. FAN_ATPG itself is MIT-licensed; rights to the underlying original ISCAS89 circuits were not independently established. The additional-benchmark audit did not admit `pact_sanity` because no verified FAN full-scan/PPI abstraction exists; additional FAN ISCAS89 sources have the same unresolved original-netlist rights and no completed identity qualification. No benchmark was substituted silently. All physical results use Nangate45/FreePDK45. Each translated BUF_X3→BUF_X4 count was checked against the frozen source; FF names, PPI mapping, and logical scan targets are preserved.

The frozen FAN runs use single stuck-at `SAF`, BASIC one-frame scan patterns, static and dynamic compression on, and X-fill on. The same saved patterns and FF identity map are used for every architecture within a design. Rewire verification checks exact order, SI and scan-out connectivity, unchanged non-scan logic and fixed placement, and complete serial loading of every mapped ATPG target; see each pair's verification JSON and the {link('artifacts/raw/tool_qualification/fan_atpg/s5378.atpg.log', 'FAN command log')}. Each plan stores scan HPWL, identical total Manhattan distance for these two-pin edges, mean/max/P95/P99, and the full placed-FF edge-length distribution. The distribution was appended after an audit, with original plans archived as `plan.pre_edge_distribution.json`; every appended sum was checked against the original HPWL, and no objective or architecture selection changed. The shift simulator records total toggles, simultaneous peak/P95/P99, H8/H16/H32, and cumulative-bin Gini. H8 is the largest clock-by-bin value after dividing bin toggles by resident FF count and applying the saved 3×3 kernel `1/(1+Manhattan bin distance)`. These are activity proxies, **not power or IR drop**; functional capture between pattern shifts is unmodelled.

## The B0/B1 baseline distinction

The direct `scan_replace; report_dft_plan; execute_dft_plan` probe on the already pre-scanned FAN s5378 netlist reported **zero chains** ({link('artifacts/raw/phase0b/dft_probe/s5378/s11/stdout.log', 'probe log')}). For B1, the flow instead converts the same placed SDFF inventory to prescan DFFs without moving instances or changing D/CK/Q/QN functional connectivity, uses an isolated Nangate45 Liberty copy with `SDFF_X1` declared as a DFT `test_cell`, and runs those OpenROAD commands. In the pinned OpenROAD source, `scan_replace` maps eligible DFFs to scan cells; the architect groups them by clock domain, applies the configured maximum chain length (1,000 here, yielding one chain per research design), then orders placed cells from the lowest x+y origin by an R-tree nearest-neighbor search, with falling-edge cells before rising-edge cells. `report_dft_plan` previews that architecture without stitching; `execute_dft_plan` stitches it and writes scan-chain metadata. This is OpenROAD's own placement-aware heuristic, distinct from PACT's Manhattan P order; see the pinned {link('external/OpenROAD/src/dft/src/architect/ScanArchitectHeuristic.cpp', 'architect')} and {link('external/OpenROAD/src/dft/src/architect/Opt.cpp', 'ordering implementation')}. The actual report order is checked against the stitched netlist and then rewired onto the paired FAN `test_si/test_so` interface. Native port names and the normalized paired implementation are both recorded in each `B1.native_qualification.json`. This establishes {native_pass} qualified B1 seed orders so far; B0 remains the **supplied FAN order**, never relabelled as OpenROAD-native. The {link('scripts/tcl/phase0b_prescan_native.tcl', 'DFT script')} and {link('scripts/phase0b_extract_native.py', 'extraction verifier')} reproduce the distinction. OpenROAD's [DFT command documentation](https://openroad.readthedocs.io/en/latest/main/src/dft/README.html) describes the commands.

ORFS inserted a transparent BUF_X1 between two B0 scan FFs in at least the s9234 and s15850 seed-11 placements. The first direct-net-only s9234 check failed and remains archived; a constrained one-hop buffer proof and regression test established the same FF order (see {link('artifacts/derived/phase0b/s9234/s11/B0.scan_edge_diagnosis.json', 's9234 scan-edge diagnosis')}). The geometric HPWL is FF-origin based and does not include that buffer's physical route.

## Completed physical evidence and primary conflict test

{analysis['completed_design_seed_pairs']} of 15 design×physical-seed pairs are complete. {len(route_files)} architecture variants have a saved detailed-route ODB; {analysis['qualified_physically_routed_architecture_count']} satisfy the paired verification, zero-DRC, timing-record, and scan-route-record gates. Timing was measured, **not required to close**, so negative WNS remains visible. The complete-pair routed methods currently include {', '.join(methods) if methods else 'none'}. S and the two nonselected J alpha methods remain predeclared proxy rows in each plan; the best J is selected by H8, then HPWL, before physical routing. Every qualifying detailed route has zero saved DRC errors, with structured total routed wirelength, vias, setup/hold WNS/TNS, endpoint and DRV counts in `structured_metrics.json`.

{pair_table(analysis['pairs'])}

The 15 rows above keep incomplete and failed or excluded pairs visible. A/B/C/D use `1=true, 0=false`: A says the physical optimum also minimizes H8, B the reverse, C that multiple architectures lie on the frontier, and D that a joint candidate meaningfully dominates at least one single-objective candidate. Disaggregated D fields show dominance over P in {joint_vs_p} complete pairs, over A in {joint_vs_a}, and over both by the **same** joint candidate in {joint_vs_both}. Their booleans, Pareto architecture hashes, and exact absolute and percent deltas are generated in {link('artifacts/derived/phase0b/conflict_analysis.json', 'conflict_analysis.json')}; they are not inferred from figures. Among complete pairs, {strict} have distinct optima but {practical} satisfy both practical-effect thresholds. Do not extrapolate from these fixed ISCAS89 layouts to a population of designs.

{practical_detail}

{design_effect_table(analysis['design_summaries'])}

The median and IQR summarize paired physical seeds **within each design**; ordering samples are not pooled. A deterministic 10,000-resample percentile interval is shown only for designs with all five completed seeds and is descriptive for those realizations, not a population-level confidence claim. No p-value is reported.

## Physical, timing, congestion, and power limits

{'No complete pair has exact routed scan-only length.' if all_proxy else f"{analysis['routed_scan_net_only_available_pair_count']} pairs have exact routed scan-only length."} OpenDB `dbWire.getLength` is used only when a Q→SI net has exactly the scan terminals and no functional branch; mixed nets are recorded separately as upper bounds and never called scan-only length. The scan-net records show whether a buffered or mixed edge prevents extraction. Total **detailed-route** wirelength is available, but is never substituted for scan-only length. Structured global-route congestion is available for {analysis['structured_congestion_available_pair_count']} of {analysis['completed_design_seed_pairs']} complete pairs; absent JSON keys remain null, as do unavailable overflow and layer-utilization values. Timing comparisons use the same global-route stage; detailed-route DRC and via counts come from the detailed-route stage. See the {link('scripts/phase0b_extract_structured_metrics.py', 'metric extractor')} and {link('scripts/phase0b_parse_scan_route.py', 'scan-net extractor')}.

The {link('artifacts/derived/phase0b/pdnsim_feasibility.json', 'PDNSim feasibility record')} classifies test-mode IR drop as **unavailable**. OpenROAD [PDNSim documentation](https://openroad.readthedocs.io/en/latest/main/src/psm/README.html) describes a static grid solver and optional per-instance power override. This campaign has logical shift toggles but no calibrated test-mode instance currents, supply/current waveform, or activity-to-current model. No current waveform, test power, silicon-calibrated IR drop, or PDNSim output was fabricated; no sensitivity result was run.

## Reproducible figures

{figures}

- **Cross-design:** {link('reports/figures/phase0b/aggregate_cross_design.png', 'paired effects and completion')}. Figure inputs and hashes are in {link('reports/figures/phase0b/figures_manifest.json', 'figures_manifest.json')}. Unavailable metrics are displayed as no-data panels.

## Answers to the required decision questions

| Question | Evidence-based answer |
|---|---|
| 1. OpenROAD-native order available? | {'Yes' if native_pass else 'No'}: {native_pass} qualified B1 seed orders, from DFT insertion on placed prescan equivalents, distinct from B0. |
| 2. Benchmarks completed? | {analysis['completed_designs']} of 3 have all five qualified physical pairs and distinct placement hashes; {len(manifest['designs'])} have frozen benchmark/ATPG provenance. |
| 3. Physical seeds completed? | {analysis['completed_design_seed_pairs']} of 15 full design×seed pairs; per-design counts appear above. |
| 4. Architectures physically routed? | {len(route_files)} saved route variants, {analysis['qualified_physically_routed_architecture_count']} qualified pair rows. |
| 5. Routed scan-only length available? | {yn(not all_proxy)}; mixed functional/scan nets force a labelled HPWL proxy where exact extraction fails. |
| 6. Structured congestion available? | {yn(analysis['structured_congestion_available_pair_count'] > 0)}; unavailable entries are null. |
| 7. Qualified power-integrity quantity? | No; no defensible test-current model or PDNSim test-mode result. |
| 8. Physical-vs-activity conflict? | {strict} strict numerical disagreements; {practical} complete pairs clear both predeclared practical-effect thresholds. |
| 9. Effect size? | Absolute, percent, per-design median/IQR, and conditional bootstrap summaries appear in the pair and design tables. |
| 10. Replicated across physical seeds? | {yn(analysis['G7a_replicated_within_design'])}; requires ≥4 of 5 qualifying pairs in one design. |
| 11. Replicated across designs? | {yn(analysis['G7b_replicated_across_designs'])}; requires two designs passing within-design replication. |
| 12. Simple heuristics sufficient? | {heuristic_answer} |
| 13. Landscape complex enough for ML? | {yn(analysis['phase1_go'])}; no learning is justified unless G5–G8 all pass. |
| 14. Phase 1? | {'GO' if analysis['phase1_go'] else 'NO-GO'}. {'The complete campaign supports the stated classification.' if fully_complete else 'This is an incomplete-campaign hold, not a completed null result.'} |

| Learning gate | Result |
|---|---|
{gate_rows}

The optional G7b alternative for a demonstrably complex non-monotonic response was not invoked: no quantitative criterion for that stronger claim was frozen before the outcomes, and a non-P Pareto point alone does not establish a learning-worthy surface. G8 is assessed separately by its predeclared P-only frontier rule; passing that narrow rule does not show that learning is needed or that the other deterministic heuristics are insufficient.

{recommendation}

`{classification}`
"""
    REPORT.write_text(text, encoding="utf-8")
    print(REPORT)


if __name__ == "__main__":
    main()
