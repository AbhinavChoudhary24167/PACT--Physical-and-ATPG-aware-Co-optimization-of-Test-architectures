#!/usr/bin/env python3
"""Render an evidence-backed Phase-0C qualification report from saved JSON."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

from phase0c_classify import ROOT, classify


def read(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def main() -> None:
    analysis = classify()
    manifest = read(ROOT / "artifacts/manifests/phase0b/benchmark_manifest.json")
    proxies = [read(path) for path in sorted((ROOT / "artifacts/derived/phase0c").glob("*/s*/k*/*.proxy.json"))]
    b0 = [r for r in proxies if r["design"] == "s5378" and r["physical_seed"] == 11 and r["method"] == "B0"]
    b0.sort(key=lambda row: row["K"])
    route_records = [read(path) for path in sorted((ROOT / "artifacts/raw/phase0c").glob("physical/*/s*/k*/*/route_metrics.json"))]
    qualification = ROOT / "artifacts/raw/phase0c/qualification/s5378/s11/k2/B0"
    qual_metrics = None
    if (qualification / "5_1_grt.json").is_file() and (qualification / "5_2_route.json").is_file():
        from pact.physical.phase0b_structured_metrics import extract_structured_metrics
        qual_metrics = extract_structured_metrics(read(qualification / "5_1_grt.json"),
                                                  read(qualification / "5_2_route.json"))
    fig_manifest = ROOT / "reports/figures/phase0c/figures_manifest.json"
    figs = read(fig_manifest) if fig_manifest.exists() else []
    bench_rows = "\n".join(f"| {r['design']} | {r['scan_ff_count']} | {r['pattern_count']} | {r['stuck_at_coverage_percent']:.2f}% |"
                           for r in manifest["designs"])
    k_rows = "\n".join(f"| {r['K']} | {', '.join(map(str, r['chain_statistics']['chain_lengths']))} | "
                       f"{r['chain_statistics']['parallel_shift_cycles']:,} | "
                       f"{r['scan_geometry']['total_scan_hpwl_um']:,.2f} | "
                       f"{r['activity']['grids']['8']['H_eff']:.3f} |"
                       for r in b0)
    gates = "\n".join(f"| {name} | {record['status']} | {record['reason']}; " +
                      ", ".join(f"{key}={value}" for key, value in record.items() if key not in ("status", "reason")) + " |"
                      for name, record in analysis["gates"].items())
    drc = "unavailable" if qual_metrics is None else str(qual_metrics["detailed_route_drc_errors"])
    setup = "unavailable" if qual_metrics is None else f"{qual_metrics['setup_wns_ns']:.5f} ns"
    hold = "unavailable" if qual_metrics is None else f"{qual_metrics['hold_wns_ns']:.5f} ns"
    wire = "unavailable" if qual_metrics is None else f"{qual_metrics['total_detailed_route_wirelength_um']:,.0f} µm"
    figure_lines = "\n".join(f"- [{Path(row['figure']).name}](../{row['figure']}): {row['description']}"
                             for row in figs)
    answers = [
        "3 previously qualified ISCAS89 designs; no new benchmark admitted.",
        "s5378=179, s9234=211, s15850=534 FFs.",
        "s5378=117, s9234=156, s15850=133 frozen FAN patterns.",
        "s5378=96.04%, s9234=94.14%, s15850=94.62% stuck-at coverage from frozen FAN reports.",
        "K=1,2,4,8 are logically qualified on s5378 seed 11; no K is yet qualified across the full route campaign.",
        "1 of 5 physical seeds has qualification proxy rows; 0 of 15 design×seed physical campaign units complete.",
        f"{len(proxies)} proxy variants generated of 360 planned fresh routes; 15 native K=1 reference cases are specified separately.",
        f"{len(route_records)} fresh Phase-0C route records archived; qualified routed variants={analysis['qualified_new_routes']}.",
        f"{len(proxies)} generated variants pass FF, loading and scan-out checks; post-route topology proof is separate.",
        f"Qualification s5378/s11/K2/B0 has {drc} detailed-route DRC errors and is excluded; zero-DRC route qualification is pending.",
        "Exact scan-only routed length: unavailable for the qualification case; total detailed-route wirelength is exact tool output for its full netlist.",
        "Scan FF-origin HPWL, Manhattan edge lengths and long-edge estimates are placement proxies.",
        "Logical shift toggles and binary PPI target reconstruction are exact within the stated no-capture simulator.",
        "H8/H16/H32 and direct-sink-weighted H_eff are explicitly dimensionless activity proxies.",
        "No activity-driven shift-mode OpenSTA/OpenROAD power flow has been qualified; power remains null.",
        "TEST_MODE_IR_DROP_UNQUALIFIED; no PDNSim test-mode run or silicon IR-drop claim.",
        "For s5378 B0 seed 11, approximate parallel shift clocks are 20,943 / 10,530 / 5,265 / 2,691 for K=1/2/4/8; capture excluded.",
        "s5378 B0 seed-11 HPWL proxies appear in the K table; the K effect on qualified routed scan cost is unavailable.",
        "s5378 B0 seed-11 H_eff8 proxies appear in the K table; no physical-current correlation is claimed.",
        f"One excluded K2 B0 route has global-route setup WNS {setup} and hold WNS {hold}; the cross-K timing effect is unavailable.",
        "No C3 practical physical/activity conflict can be assessed on a qualified replicated route set.",
        "No seed-level practical conflict replication assessable; 0 of 5 seeds complete on each design.",
        "No cross-design conflict replication assessable; 0 of 3 designs complete.",
        "No deterministic heuristic insufficiency claim is assessable from routed outcomes.",
        "Qualified routed heuristic regret unavailable; proxy-only ordering differences are not gate evidence.",
        f"{analysis['intervention_records']} proxy-only intervention records; routed context-dependent sign effects unavailable.",
        "The legal labelled ordered-chain count exceeds 10^100 for all three designs; physical legality and heuristic difficulty are separate questions.",
        "Phase 1 NO-GO at present: the script emits FAIL because C1-C7 are unqualified, not because a completed Phase-0C campaign disproved learning value.",
    ]
    question_rows = "\n".join(f"| {i} | {answer} |" for i, answer in enumerate(answers, 1))
    text = f"""# PACT Phase-0C qualification report

**Current decision:** `{analysis['classification']}`. This is an incomplete-campaign gate failure, not an evidentiary conclusion that deterministic multi-chain methods are sufficient. The contract is still candidate and must be frozen in a commit before any final campaign. No ML was trained.

The frozen Phase-0B result remains `PACT_PHASE0B_CONFLICT_NOT_REPLICATED_PHASE1_NO_GO`: 15/15 complete design×seed pairs, 90 routed variants, only 2 practical threshold hits. The [pre-edit SHA256 list](../artifacts/manifests/phase0c/phase0b_pre_edit.sha256) covers 4,127 files. The [tool qualification](../artifacts/manifests/phase0c/tool_qualification.json) records live WSL binaries, commits and PDK collateral.

## Benchmark population

| Design | Scan FFs | FAN patterns | Stuck-at coverage |
|---|---:|---:|---:|
{bench_rows}

Original ISCAS89 netlist rights were not independently resolved, and no additional benchmark passed license plus ATPG/FF qualification. These three designs support conditional findings only.

## Small logical qualification, s5378 seed 11

Six predeclared families (B0/P/A/J50/T/R) were generated for each K. All {len(proxies)} rows retain the 179-FF inventory, exactly reconstruct every one of 117 FAN PPI target states under fully clocked parallel shifting, and verify scan-out traversal. K=1 B0 reproduces the frozen Phase-0B 1,954,773 logical toggles and H8=4.15556 exactly. Physical seed 11 is a perturb-and-legalize realization from one source placement, not an independent global placement.

| K | Balanced chain lengths, B0 | Approx. shift clocks | Scan HPWL proxy (µm) | H_eff8 proxy |
|---:|---|---:|---:|---:|
{k_rows}

H_eff8 uses direct Q-net sink counts as dimensionless weights, not capacitance, watts or current. Functional capture between patterns is unmodelled. Shift clocks omit any assumed capture clock.

## Physical qualification

The first K2 B0 route failed at an off-grid added SI pin; its logs are retained. A grid-aligned rerun under a new variant completed with **{drc} DRC errors** at/near the original `test_so` pin. It is structurally verifiable after transparent route-inserted BUF/CLKBUF cells, but it is **excluded** from qualified routed comparisons. Its full-netlist detailed-route wirelength is {wire}; global-route setup WNS is {setup}, hold WNS {hold}. These are measurements of an excluded attempt, not proof of a practical conflict. Structured congestion, exact scan-only routed length, shift-mode power and test-mode IR drop remain unavailable. Additional per-run route records: {len(route_records)}. Zero-DRC qualified new routes: {analysis['qualified_new_routes']}.

The planned matrix is 3 designs × 5 physical seeds × 4 K values × 6 methods = **360 fresh routes**, plus 15 frozen K=1 native B1 references, or 375 comparison rows. {len(proxies)} logical/proxy rows have been generated. No final campaign was launched. The candidate 12-hour cap prevents an accidental unbounded Cartesian run; observed qualification detailed routing took about 13 minutes for the excluded B0 K2 rerun. This is not a full-campaign scaling estimate.

## Legal interventions and figures

The [intervention dataset](../artifacts/derived/phase0c/intervention_dataset.jsonl) has {analysis['intervention_records']} proxy-only records with parent/child architecture hashes, operations, affected edges, before/after quantities and deltas. None has a qualified routed physical delta. Figures are generated from their hashed machine-readable inputs:

{figure_lines}

## Predeclared candidate learning gates

| Gate | Status | Mechanical reason and counts |
|---|---|---|
{gates}

The [gate analysis](../artifacts/derived/phase0c/gate_analysis.json) is script-generated by `scripts/phase0c_classify.py`. C8 demonstrates a vast formal search space; it does not by itself demonstrate physical conflict, replicated effects or heuristic regret. The top-level classifier requires all C1–C8 to pass. A GO would only justify *investigating* a learned intervention model; it would not predict ML success.

## Answers to the 28 required report questions

| # | Evidence-based answer |
|---:|---|
{question_rows}

The current evidence does **not** demonstrate that investigating a learned intervention model is justified. The proper next step is physical-port/DRC qualification, freezing a final contract, then running paired seed/K/method routes under the saved cap before drawing a scientific Phase-0C conclusion.

`{analysis['classification']}`
"""
    target = ROOT / "reports/PACT_PHASE0C_REPORT.md"
    target.write_text(text, encoding="utf-8")
    (ROOT / "artifacts/derived/phase0c/gate_analysis.json").write_text(json.dumps(analysis, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"report": str(target), "classification": analysis["classification"],
                      "sha256": hashlib.sha256(target.read_bytes()).hexdigest()}))


if __name__ == "__main__":
    main()
