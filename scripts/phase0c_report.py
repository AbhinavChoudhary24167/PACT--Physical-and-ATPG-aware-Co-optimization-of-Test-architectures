#!/usr/bin/env python3
"""Render the final evidence-backed Phase-0C report."""
from __future__ import annotations

from collections import Counter, defaultdict
import hashlib
import json
from pathlib import Path
import subprocess

import numpy as np

from phase0c_classify import ROOT
from phase0c_classify_recovery import classify


def read(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def med_iqr(values) -> str:
    values = [float(value) for value in values if value is not None]
    if not values:
        return "unavailable"
    median = np.median(values)
    iqr = np.quantile(values, .75) - np.quantile(values, .25)
    return f"{median:,.3f} (IQR {iqr:,.3f}; range {min(values):,.3f}–{max(values):,.3f}; n={len(values)})"


def compact(value) -> str:
    if isinstance(value, float):
        return f"{value:.6g}"
    if isinstance(value, (dict, list)):
        return json.dumps(value, sort_keys=True, separators=(",", ":"))
    return str(value)


def main() -> None:
    analysis = classify()
    analysis_path = ROOT / "artifacts/derived/phase0c/gate_analysis.json"
    analysis_path.write_bytes((json.dumps(analysis, indent=2, sort_keys=True) + "\n").encode())
    execution = read(ROOT / "artifacts/manifests/phase0c/campaign_execution.json")
    recovery_execution = read(ROOT / "artifacts/manifests/phase0c/campaign_recovery.json")
    campaign = read(ROOT / "config/phase0c_campaign.json")
    contract = read(ROOT / "config/phase0c_analysis_contract.json")
    benchmark = read(ROOT / "artifacts/manifests/phase0b/benchmark_manifest.json")
    tool = read(ROOT / "artifacts/manifests/phase0c/tool_qualification.json")
    source = read(ROOT / "artifacts/derived/phase0c/figure_source_data.json")
    rows = source["rows"]
    proxies = [read(path) for path in sorted((ROOT / "artifacts/derived/phase0c").glob("*/s*/k*/*.proxy.json"))]
    final_routes = [read(path) for path in sorted((ROOT / "artifacts/raw/phase0c/physical").glob(
        "*/s*/k*/*/route_metrics.json")) if read(path).get("campaign_freeze_commit") == execution["freeze_commit"]]
    original_qualified = {key: value for key, value in execution["runs"].items()
                          if value.get("status") == "QUALIFIED"}
    combined_runs = {**original_qualified, **recovery_execution["runs"]}
    status_counts = Counter(record.get("status") for record in combined_runs.values())
    unattempted_labels = {"CAMPAIGN_CAP_REACHED", "WORKSPACE_DISK_FLOOR_REACHED"}
    physically_attempted = sum(status not in unattempted_labels for status in
                               (record.get("status") for record in combined_runs.values()))
    qualified = [record for record in final_routes
                 if record.get("status") == "QUALIFIED" and record.get("DRC_errors") == 0]
    proofs = [read(ROOT / record["postroute_verification"]) for record in qualified]
    exact_scan = [record["exact_scan_only_routed_length_um"] for record in qualified
                  if record.get("exact_scan_only_routed_length_um") is not None]
    figures = read(ROOT / "reports/figures/phase0c/figures_manifest.json")
    interventions = source["interventions"]

    benchmark_rows = "\n".join(
        f"| {row['design']} | {row['scan_ff_count']} | {row['pattern_count']} | "
        f"{row['stuck_at_coverage_percent']:.2f}% |"
        for row in benchmark["designs"])

    k_rows = []
    for k in campaign["K_values"]:
        subset = [row for row in rows if row["K"] == k]
        k_rows.append(
            f"| {k} | {len(subset)} | {med_iqr(row['chain_imbalance'] for row in subset)} | "
            f"{med_iqr(row['shift_cycles'] for row in subset)} | "
            f"{med_iqr(row['physical_um'] for row in subset)} | "
            f"{med_iqr(row['H_eff8'] for row in subset)} | "
            f"{med_iqr(row['setup_wns_ns'] for row in subset)} | "
            f"{med_iqr(row['global_route_usage_percent'] for row in subset)} |")
    k_table = "\n".join(k_rows)

    design_rows = []
    for design in campaign["designs"]:
        subset = [row for row in rows if row["design"] == design]
        design_rows.append(
            f"| {design} | {len(subset)} | {med_iqr(row['physical_um'] for row in subset)} | "
            f"{med_iqr(row['H_eff8'] for row in subset)} | "
            f"{med_iqr(row['detailed_route_wirelength_um'] for row in subset)} | "
            f"{med_iqr(row['routed_scan_path_upper_bound_um'] for row in subset)} | "
            f"{med_iqr(row['route_s'] for row in subset)} |")
    design_table = "\n".join(design_rows)

    conflict_rows = []
    for design in campaign["designs"]:
        subset = [row for row in analysis["conflicts"] if row["design"] == design]
        seeds = {row["physical_seed"] for row in subset if row["practical_conflict"]}
        conflict_rows.append(
            f"| {design} | {sum(row['practical_conflict'] for row in subset)}/{len(subset)} design-seed-K groups | "
            f"{len(seeds)}/5 | {med_iqr(row['physical_penalty_percent'] for row in subset)} | "
            f"{med_iqr(row['H_eff_gain_percent'] for row in subset)} |")
    conflict_table = "\n".join(conflict_rows)

    regret = analysis["descriptive_statistics"]["method_regret"]
    regret_rows = []
    for method, values in regret.items():
        regret_rows.append(
            f"| {method} | {values['physical_percent']['median']:.3f}% | "
            f"{values['physical_percent']['iqr']:.3f}% | "
            f"{values['activity_percent']['median']:.3f}% | "
            f"{values['activity_percent']['iqr']:.3f}% | "
            f"{analysis['descriptive_statistics']['pareto_membership_counts'].get(method, 0)} |")
    regret_table = "\n".join(regret_rows)

    contexts = defaultdict(list)
    for record in interventions:
        contexts[(record["design"], record["physical_seed"])].append(
            record["delta"]["scan_hpwl_proxy_um"])
    intervention_rows = []
    for design in campaign["designs"]:
        design_values = [value for (item, _), values in contexts.items() if item == design for value in values]
        passing = sum(len(values) >= contract["C7"]["minimum_matched_interventions_per_pair"]
                      and sum(value > 0 for value in values) / len(values) >= .2
                      and sum(value < 0 for value in values) / len(values) >= .2
                      for (item, _), values in contexts.items() if item == design)
        intervention_rows.append(
            f"| {design} | {sum(len(values) for (item, _), values in contexts.items() if item == design)} | "
            f"{passing}/5 | {sum(value < 0 for value in design_values)} | "
            f"{sum(value > 0 for value in design_values)} | {med_iqr(design_values)} |")
    intervention_table = "\n".join(intervention_rows)

    gate_rows = []
    for name in (f"C{i}" for i in range(1, 10)):
        record = analysis["gates"][name]
        numbers = "; ".join(f"{key}={compact(value)}" for key, value in record.items()
                            if key not in ("status", "reason"))
        gate_rows.append(f"| {name} | **{record['status']}** | {record['reason']}; {numbers} |")
    gates = "\n".join(gate_rows)

    figure_lines = "\n".join(
        f"- [{Path(row['figure']).name}](../{row['figure']}): {row['description']} "
        f"(`{row['sha256'][:12]}…`)" for row in figures)
    phase1_answer = ("Yes. The frozen gate justifies investigating a learned intervention model; it does not "
                     "predict that ML will work." if analysis["gates"]["C9"]["status"] == "PASS" else
                     "No. The frozen evidence does not satisfy every prerequisite for investigating a learned intervention model.")

    answers = [
        f"{len(benchmark['designs'])} benchmarks qualified; Ibex and JPEG were audited but not admitted.",
        ", ".join(f"{row['design']}={row['scan_ff_count']}" for row in benchmark["designs"]) + " scan FFs.",
        ", ".join(f"{row['design']}={row['pattern_count']}" for row in benchmark["designs"]) + " frozen FAN patterns.",
        ", ".join(f"{row['design']}={row['stuck_at_coverage_percent']:.2f}%" for row in benchmark["designs"]) + " stuck-at coverage.",
        f"K={campaign['K_values']} qualified under the final physical campaign.",
        f"{len({(row['design'], row['seed']) for row in rows})} design-seed units and {len({row['seed'] for row in rows})}/5 physical seeds completed qualified rows.",
        f"{len(proxies)} architecture variants were generated; planned={execution['planned_routes']}.",
        f"{physically_attempted} final variants were physically attempted; qualified={len(qualified)}.",
        f"{sum(proof.get('status') == 'PASS' for proof in proofs)} final routed variants passed structural verification.",
        f"{sum(record.get('DRC_errors') == 0 for record in final_routes)} final variants had zero detailed-route DRC; status counts={dict(status_counts)}.",
        f"Exact tool outputs include full-netlist detailed-route wirelength, via count, DRC, global-route timing and initial global-route utilization/overflow; exact exclusive scan-only routed length exists for {len(exact_scan)} rows.",
        "Port-aware FF-origin scan HPWL and mixed-net full-scan-path length upper bounds are physical proxies/bounds.",
        "Per-clock logical scan toggles, totals, peaks, quantiles and ATPG target reconstruction are exact within the frozen no-capture shift simulator.",
        "H8/H16/H32 and direct-sink-weighted H_eff are dimensionless activity proxies.",
        f"Shift-mode power status: {tool['physical_qualification']['power_mode_status']}; no watts are reported.",
        f"PDNSim status: {tool['physical_qualification']['PDNSim_status']}; no test-mode IR drop is reported.",
        "K effects on exact shift cycles are reported in the K table; capture cycles are excluded and reported separately in proxy rows.",
        "K effects on the port-aware physical proxy are reported as median/IQR/range in the K table.",
        "K effects on H_eff8 and exact cumulative hotspot maps are reported in the K table and figures 04–05.",
        "K effects on global-route setup WNS are reported in the K table; negative values, if present, are retained.",
        f"C3={analysis['gates']['C3']['status']}; practical conflict hits={analysis['gates']['C3']['practical_hits']}/{analysis['gates']['C3']['assessed_pairs']} assessed groups.",
        f"C4={analysis['gates']['C4']['status']}; qualifying seed counts={analysis['gates']['C4']['qualifying_seed_counts']}.",
        f"C5={analysis['gates']['C5']['status']}; replicated design count={analysis['gates']['C5']['replicated_design_count']}.",
        f"C6={analysis['gates']['C6']['status']}; maximum single-method 2% coverage={analysis['gates']['C6']['max_simple_heuristic_coverage']:.3f}, fixed-portfolio coverage={analysis['gates']['C6']['deterministic_portfolio_coverage']:.3f}.",
        "Median/IQR physical and activity regret for every deterministic method is reported in the heuristic table.",
        f"{len(interventions)} frozen local-swap records were eligible; C7={analysis['gates']['C7']['status']} with qualifying design count={analysis['gates']['C7']['qualifying_design_count']}.",
        f"C8={analysis['gates']['C8']['status']}; formal log10 architecture counts={analysis['gates']['C8']['log10_architecture_counts']}.",
        f"Phase 1 decision: {analysis['classification']}; {phase1_answer}",
    ]
    question_rows = "\n".join(f"| {index} | {answer} |" for index, answer in enumerate(answers, 1))
    evidence_commit = subprocess.check_output(
        ["git", "log", "-1", "--format=%H", "--",
         "artifacts/derived/phase0c/gate_analysis.json"], cwd=ROOT, text=True).strip()

    report = f"""# PACT Phase-0C final report

**Script-generated decision:** `{analysis['classification']}`

**Frozen analysis commit:** `{execution['freeze_commit']}`

**Report-generation evidence commit:** `{evidence_commit}`
**Scientific answer:** **{phase1_answer}**

No ML model was trained or evaluated. A PASS means only that a later investigation of learned intervention guidance is scientifically justified under this qualified benchmark regime.

## Provenance and benchmark population

The starting commit was `{tool['parent_commit']}`. Phase-0B remains byte-for-byte preserved across {tool['phase0b_pre_edit_hashed_files']:,} hashed files and retains `PACT_PHASE0B_CONFLICT_NOT_REPLICATED_PHASE1_NO_GO`. The Phase-0C contract, campaign, objectives, methods, hashes, toolchain and benchmark audit were frozen before final execution. The campaign used OpenROAD `{tool['WSL']['OpenROAD']['version']}`, ORFS `{tool['WSL']['ORFS']['commit']}`, Yosys `{tool['WSL']['Yosys']['version']}`, FAN commit `{tool['WSL']['FAN_ATPG']['repository_commit']}`, and Nangate45 Liberty `{tool['WSL']['Nangate45']['liberty_sha256']}`.

| Design | Scan FFs | FAN patterns | Frozen stuck-at coverage |
|---|---:|---:|---:|
{benchmark_rows}

No additional benchmark was admitted: the saved audit found no reproducible FAN full-scan/PPI-to-FF mapping for the otherwise licensed Ibex and JPEG candidates. The three ISCAS89 designs therefore support conditional conclusions within this benchmark regime.

## Campaign and infrastructure qualification

The frozen matrix contains 3 designs × 5 physical seeds × 4 K values × 6 common families, plus native B1 at K=1: **{execution['planned_routes']} planned physical rows**. The original session stopped at the frozen disk floor after 27 qualified rows; its manifest is immutable. The precommitted recovery ledger contains {len(recovery_execution['runs'])} eligible rows and status `{recovery_execution['status']}`. Combined ledger rows={len(combined_runs)}, physically attempted={physically_attempted}, qualified zero-DRC rows={len(qualified)}, status counts={dict(status_counts)}. All {len(proxies)} architecture rows use frozen input hashes and deterministic run IDs. Routed structural proofs passed={sum(proof.get('status') == 'PASS' for proof in proofs)}/{len(proofs)}; fixed-port proofs passed={sum(proof.get('fixed_port_positions_verified') is True for proof in proofs)}/{len(proofs)}; K-chain SI/SO proofs passed={sum(proof.get('all_chain_inputs_outputs_verified') is True for proof in proofs)}/{len(proofs)}.

Each architecture preserves the placed FF bijection and reconstructs all frozen ATPG PPI targets through fully clocked parallel loading, including leading padding on short chains. Every final route begins from its design/seed's identical Phase-0B `3_place.odb`. Failed and superseded attempts retain commands, return codes, logs and partial artifacts.

## Physical, activity and scaling results

The primary physical quantity is the **port-aware FF-origin scan HPWL proxy**, measured at fixed placement after including all 2K SI/SO links. It is a proxy, not routed scan wirelength. Full-netlist detailed-route wirelength/vias, detailed-route DRC, global-route setup/hold results, and initial global-route utilization/overflow are tool outputs. The verified mixed-net SI-to-SO total is an upper bound. Exact exclusive scan-only routed length qualified in {len(exact_scan)} rows.

| Design | Qualified rows | HPWL proxy median/IQR/range (µm) | H_eff8 median/IQR/range | Full-net DR wirelength (µm) | Full scan-path upper bound (µm) | Route runtime (s) |
|---|---:|---|---|---|---|---|
{design_table}

Logical shift toggles are exact within the no-capture model; H_eff8 is a dimensionless direct-sink-weighted spatial proxy. Shift-mode power and test-mode PDNSim were not qualified, so watts, current and IR drop remain null. Median exact total toggles={med_iqr(row['total_toggles'] for row in rows)}; peak simultaneous toggles={med_iqr(row['peak_toggles'] for row in rows)}. Compressed routed ODB size per row={med_iqr(row['odb_archive_bytes'] / 1048576 for row in rows)} MiB.

## Effect of K

| K | Qualified rows | Normalized chain imbalance | Exact shift clocks | HPWL proxy (µm) | H_eff8 | Setup WNS (ns) | Initial GRT usage (%) |
|---:|---:|---|---|---|---|---|---|
{k_table}

K changes the number and location of fixed SI/SO ports, chain balance, exact parallel test time, physical proxy, activity concentration, routed timing and congestion together. Results are paired within design×physical-seed contexts; architecture variants are not counted as independent design samples.

## Conflict and replication

The frozen C3 test compares the physically best and H_eff8-best qualified methods inside each complete design-seed-K group. A hit requires at least 5% H_eff8 improvement with at least 10% physical penalty.

| Design | Practical hits | Seeds with ≥1 hit | Physical penalty % | H_eff8 gain % |
|---|---:|---:|---|---|
{conflict_table}

The seed replicas are conditional perturb-and-legalize placements around a source placement. Medians and IQRs are descriptive; no population p-values or independence claim is made.

## Deterministic heuristics and intervention landscape

| Method | Median physical regret | Physical IQR | Median activity regret | Activity IQR | Pareto memberships |
|---|---:|---:|---:|---:|---:|
{regret_table}

C6 tests both each simple method and the frozen deterministic portfolio at 2% two-objective coverage. Its measured maximum single-method coverage is {analysis['gates']['C6']['max_simple_heuristic_coverage']:.3f}; portfolio coverage is {analysis['gates']['C6']['deterministic_portfolio_coverage']:.3f} over {analysis['gates']['C6']['complete_pairs']} complete groups.

The C7 screen applies 20 predeclared, deterministic local swaps around every qualified P/K2 parent. Children preserve FF inventory and exact ATPG loading; their physical response is the port-aware HPWL proxy and is not called routed.

| Design | Eligible swaps | Contexts passing both-sign rule | Negative ΔHPWL | Positive ΔHPWL | ΔHPWL median/IQR/range (µm) |
|---|---:|---:|---:|---:|---|
{intervention_table}

## Frozen learning gates

| Gate | Status | Exact mechanical reason and counts |
|---|---|---|
{gates}

## Reproducible figures

The figure source dataset records hashes for every proxy, final route, execution manifest, analysis and intervention input. The figure manifest records each output and generator hash.

{figure_lines}

## Answers to the 28 required questions

| # | Evidence-based answer |
|---:|---|
{question_rows}

## Scientific conclusion

**Has PACT demonstrated a problem for which investigating a learned intervention model is justified?** **{phase1_answer}** The conclusion follows the frozen C1–C9 contract and remains valid whether it is GO or NO-GO.

`{analysis['classification']}`
"""
    target = ROOT / "reports/PACT_PHASE0C_REPORT.md"
    target.write_bytes(report.encode())
    report_manifest = {
        "schema_version": "phase0c-report-manifest-1",
        "classification": analysis["classification"],
        "report": target.relative_to(ROOT).as_posix(),
        "report_sha256": sha256(target),
        "sources": {path.relative_to(ROOT).as_posix(): sha256(path) for path in (
            analysis_path, ROOT / "artifacts/manifests/phase0c/campaign_execution.json",
            ROOT / "artifacts/manifests/phase0c/campaign_execution_interrupted.json",
            ROOT / "artifacts/manifests/phase0c/campaign_recovery.json",
            ROOT / "artifacts/derived/phase0c/figure_source_data.json",
            ROOT / "reports/figures/phase0c/figures_manifest.json",
            ROOT / "config/phase0c_campaign.json", ROOT / "config/phase0c_analysis_contract.json",
            ROOT / "artifacts/manifests/phase0c/tool_qualification.json",
            ROOT / "artifacts/manifests/phase0b/benchmark_manifest.json")},
    }
    manifest_path = ROOT / "artifacts/manifests/phase0c/report_manifest.json"
    manifest_path.write_bytes((json.dumps(report_manifest, indent=2, sort_keys=True) + "\n").encode())
    print(json.dumps({"report": str(target), "classification": analysis["classification"],
                      "sha256": report_manifest["report_sha256"]}))


if __name__ == "__main__":
    main()
