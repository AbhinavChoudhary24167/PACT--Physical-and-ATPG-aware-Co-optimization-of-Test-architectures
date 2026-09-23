#!/usr/bin/env python3
"""Human-readable research report and complete reproducibility manifests."""
from phase2b_common import *
from datetime import datetime, timezone
import importlib.metadata
import subprocess
import numpy as np

DESIGNS=('s5378','s9234','s15850')
def fmt(value): return 'NA' if value is None else f'{value:.3f}'

def main():
    integrity()
    rows=read(REPORT/'candidate_metrics.json')['rows'];corr=read(REPORT/'correlation.json')
    cap=read(REPORT/'extraction_audit.json');wave=read(REPORT/'waveform_audit.json')
    assert wave['status']=='FF_LOAD_CAPTURE_UNLOAD_QUALIFIED' and len(wave['rows'])==21, 'Do not publish stale successful waveform claims'
    cost=read(REPORT/'complexity.json'); comparisons=read(REPORT/'target_comparison.json')
    proofs={(r['design'],r['label']):r for r in read(OLD/'shift_reconstruction.json')['rows']}
    diagnostics=[]
    for row in rows:
        key=row['design'],row['label'];counts=proofs[key]['FF_transition_totals']
        weights=read(WORK/row['architecture_sha256']/'reference_weights.json') if cap['capacitance_qualified'] else None
        rec=dict(design=key[0],label=key[1],**row['diagnostics'])
        if weights:
            sums={k:sum(counts[n]*v[k] for n,v in weights.items()) for k in ('ground_ff','coupling_ff','pin_ff')}
            rec['cap_activity_components_fF_transitions']=sums
            rec['cap_activity_fractions']={k:v/sum(sums.values()) for k,v in sums.items()}
            assert np.isclose(sum(sums.values()),row['targets']['cap_total'],rtol=1e-12)
        diagnostics.append(rec)
    write(REPORT/'physical_diagnostics.json',dict(rows=diagnostics,
        interpretation='Descriptive component accounting, not a causal experiment. Pin, ground and incident coupling contributions to the exact FF-source load-reference total.'))
    write(REPORT/'feature_stage_audit.json',dict(
        note='Frozen feature_availability.json records earliest conceptual availability. This audit records actual consumed snapshots; no post-synthesis-only result is claimed from placed connectivity.',
        actual_metric_stage={m:'POST-PLACEMENT' for m in rows[0]['predictors']},
        primitives=dict(pin_cap_lookup='PRE-SYNTHESIS technology library; actual mapped sink master/connectivity POST-PLACEMENT',
            functional_fanout='POST-PLACEMENT snapshot used here; a synthesis-only graph was not evaluated',
            waveform_bits='POST-SYNTHESIS FAN patterns, evaluated on the selected fixed architecture',
            labels='POST-ROUTE; not consumed by predictor construction'),
        extra_waveform_library='FAN behavioral Liberty-compatible Verilog model hashed in waveform_audit; additional simulation dependency, not part of the original 649-file freeze. No fitted coefficients or correlation-based selection.'))
    # Installed SDC files are inventoried; no timing or power claim consumes them.
    sdcs=[ROOT/'experiments/phase0/s5378_orfs/constraint.sdc',ROOT/'experiments/phase0/s9234_orfs/constraint.sdc',ROOT/'experiments/phase0b/s15850_orfs/constraint.sdc']
    write(REPORT/'environment.json',dict(python=read(REPORT/'provenance.json')['python'],
        openroad=read(REPORT/'provenance.json')['openroad'],
        iverilog=subprocess.run(['iverilog','-V'],text=True,stdout=subprocess.PIPE,stderr=subprocess.STDOUT).stdout.splitlines()[0],
        packages={p:importlib.metadata.version(p) for p in ('numpy','scipy','matplotlib','pytest','threadpoolctl')},
        available_sdc={str(p):file_sha256(p) for p in sdcs},
        extraction_needs='Exact detailed-routed ODB already contains LEF technology and topology; rules model supplies wire RC. SDC not needed for static RC. No route DEF rewriting.',
        source_binary_mismatch='Installed binary lacks newer source set_extraction_rules_file API; used supported -ext_model_file with identical frozen rule file. No RC model change.',
        commands={
            'freeze':'PYTHONDONTWRITEBYTECODE=1 /root/pact-deps/pact-venv/bin/python scripts/phase2b_freeze.py',
            'extract':'PYTHONDONTWRITEBYTECODE=1 openroad -python -no_init -exit scripts/phase2b_extract.py',
            'waveform':'PYTHONDONTWRITEBYTECODE=1 /root/pact-deps/pact-venv/bin/python scripts/phase2b_waveform.py',
            'measure':'PYTHONDONTWRITEBYTECODE=1 OPENBLAS_NUM_THREADS=1 /root/pact-deps/pact-venv/bin/python scripts/phase2b_measure.py',
            'report':'PYTHONDONTWRITEBYTECODE=1 OPENBLAS_NUM_THREADS=1 MPLCONFIGDIR=/mnt/d/PACT_EXPERIMENTS/cache/matplotlib /root/pact-deps/pact-venv/bin/python scripts/phase2b_report.py',
            'focused':'PYTHONPATH=src:/mnt/d/PACT_EXPERIMENTS/cache/phase2a_python PYTHONDONTWRITEBYTECODE=1 OPENBLAS_NUM_THREADS=1 TMPDIR=/mnt/d/PACT_EXPERIMENTS/tmp MPLCONFIGDIR=/mnt/d/PACT_EXPERIMENTS/cache/matplotlib /root/pact-deps/pact-venv/bin/python -m pytest -q --capture=sys --basetemp=/mnt/d/PACT_EXPERIMENTS/pytest_tmp/phase2b_focused tests/unit/test_phase2b_activity.py tests/unit/test_phase2a_shift.py tests/unit/test_phase2a_physical_stats.py',
            'regression':'PYTHONPATH=src:/mnt/d/PACT_EXPERIMENTS/cache/phase2a_python PYTHONDONTWRITEBYTECODE=1 OPENBLAS_NUM_THREADS=1 TMPDIR=/mnt/d/PACT_EXPERIMENTS/tmp MPLCONFIGDIR=/mnt/d/PACT_EXPERIMENTS/cache/matplotlib /root/pact-deps/pact-venv/bin/python -m pytest -q --capture=sys --basetemp=/mnt/d/PACT_EXPERIMENTS/pytest_tmp/phase2b_regression'}))
    s=corr['per_design']; decision=corr['decision']
    lines=['# PACT Phase-2B — Physical Activity Model Qualification','',
        f'**Classification: `{decision["classification"]}`.**','',
        'The best inexpensive metric depends on the physical reference. M5 owned-net placement HPWL '
        'passes the preregistered geometric gate on every design. M3 input pin capacitance plus a '
        'fixed technology wire-capacitance estimate passes the capacitance-load gate on every design. '
        'No one family passes both gates, so the overall result is PARTIAL. These gates describe '
        '21 selected frozen architectures, not universal validation.','',
        '**Capacitance extraction succeeded for all 21 routes. Electrical energy/power validation remains '
        'INCOMPLETE.** The experiment measures stable-state load-transition counts. No optimizer '
        'integration, search, new candidate selection, routing, placement or ATPG generation was performed.','',
        '## Frozen scope and reference qualification','',
        'All nine s5378 architectures (P/A/J50/T and all five Phase-0D candidates) and all six each '
        'for s9234/s15850 (P/A/J50/T/balanced/activity_extreme) are retained. Seed 11 and K=2 remain '
        'fixed. The [contract](EXPERIMENT_CONTRACT.md), [freeze](freeze.json), '
        '[architecture set](architecture_set.json) and [provenance](provenance.json) identify the inputs. '
        'Every one of 649 frozen input files was rehashed after execution.','',
        'The Phase-2A classification remains `PACT_PHASE2A_H_EFF8_ACTIVITY_VALIDATION_PARTIAL`; '
        'its geometric correlations and counterexamples are unchanged. New electrical load evidence '
        'does not retroactively qualify Phase-2A energy or reinterpret its µm-transition results.','',
        'OpenROAD `26Q2-1164-g08f67ee5ec` / OpenRCX extracted copies of the exact decompressed '
        '5_2_route ODBs with the installed Nangate45 rules, model index 0, corner X. The binary '
        'uses `extract_parasitics -ext_model_file`; newer ORFS source suggested an unavailable '
        '`set_extraction_rules_file` command. Failed API probe logs are retained. No ORFS finish '
        'or obstruction deletion was run. [extraction_audit.json](extraction_audit.json) records '
        'every command, version, warning, input/output hash, net/resistor/capacitor count and total capacitance.','',
        'The primary electrical load convention is **C_eff = extracted ground capacitance + 1× incident '
        'coupling capacitance + input pin capacitance**. Wire geometry and vias are handled by the '
        'OpenRCX model; there is no invented separate via-capacitance constant. Coupling below '
        '0.1 fF is grounded by OpenRCX. Explicit coupling is charged once to each incident net '
        'when that net toggles; this is a stated endpoint-load convention, not aggressor-aware '
        'coupling energy. Ground-plus-pin results provide a sensitivity check. Output external '
        'pin loading is not fabricated. Liberty pin loads use Nangate typical, 1.10 V / 25°C; '
        'no voltage-squared conversion is applied.','',
        '`A_cap_total` covers the uniquely FF-owned Q/QN net trees through BUF/CLKBUF/INV branches. '
        'For these relevant nets stable toggles equal source toggles, so this sum equals `A_ff_cap`. '
        'The load contains actual routed buffer/sink input pins. It excludes nontransparent '
        'combinational outputs, clock/SE/PI nets, internal cell activity and glitches. A full-circuit '
        'all-net electrical target cannot be supplied from these FF-only waveforms. Units are '
        '**fF-transitions**, distinct from **µm-transitions** and from energy or power.','',
        '## Primary comparison','',
        'The primary waveform is exactly Phase-2A: zero initial FF state, states carry between '
        'loads, no capture, no final unload. Original total/per-FF counts and both geometric '
        'labels reproduce exactly (floating geometric sums within 1e-12 relative tolerance). '
        'All primary candidate metrics were recomputed twice with byte-identical JSON.','',
        'Spearman rho below uses each total candidate for total targets and its M6 fixed-window '
        'local version for local targets. H_eff8 is unchanged.','',
        '| Design | Candidate | Wire total | Wire local peak | Cap total | Cap local peak |',
        '|---|---|---:|---:|---:|---:|']
    for d in DESIGNS:
        for m in ('M1_H_eff8','M0','M2_port','M4_pin','M5_hpwl','M3_load'):
            ml=m if m=='M1_H_eff8' else m+'_local'
            vals=[s[d][m]['wire_total']['spearman'],s[d][ml]['wire_local_peak']['spearman'],
                  s[d][m]['cap_total']['spearman'],s[d][ml]['cap_local_peak']['spearman']]
            lines.append(f'| {d} | {m} | '+' | '.join(map(fmt,vals))+' |')
    lines += ['', '![Design-by-metric comparison](activity_model_comparison.png)','',
        'M5 = sum FF toggle × sum HPWL of its pre-route driven net trees, including functional '
        'sinks, selected SI sinks and fixed SO port. M3 = sum FF toggle × '
        '(sum input pin capacitance + **0.103981 fF/µm × HPWL**). The coefficient is the frozen '
        'metal3 signal-wire value from platform `setRC.tcl`, not a fitted parameter. Geometry '
        'uses cell origins. No routed buffer/topology/length or SPEF feature enters either predictor.','',
        'The placed-only graph removes old SI/SO connections before adding each frozen scan order. '
        'Existing transparent cells remain; their input loads and separate branch trees are counted '
        'once. SO ports contribute geometry and no invented external capacitance. The API rejects '
        'post-route stages and unexpected net fields. [feature_availability.json](feature_availability.json) '
        'lists every stage; [candidate_metrics.json](candidate_metrics.json) includes every formula and result.','',
        'The availability table names the earliest conceptual stage. Actual fanout/master values '
        'here come from the frozen placed snapshot, so this experiment makes a placement-time '
        'claim for all physical predictors, not a measured synthesis-only claim. See '
        '[feature_stage_audit.json](feature_stage_audit.json).','',
        'Spatial versions use the frozen die outline, 10×10 bins and all 81 contained 2×2 windows. '
        'They assign load to the FF origin and measure stable per-cycle peaks. They do not locate '
        'distributed wire dissipation.','',
        'All candidate/target Spearman, Kendall tau-b, secondary Pearson and equal-design pooled '
        'results are in [correlation.json](correlation.json). [rankings.json](rankings.json) retains '
        'exact values and ascending orders; [pairwise_comparisons.json](pairwise_comparisons.json) '
        'lists every pair, with predictor/target/both ties distinguished. No p-value or significance '
        'claim is used. Selected architectures are not random independent samples.','',
        '| Family / endpoint | Mean-normalized pooled rho | Fractional-rank pooled rho | Worst-design rho |',
        '|---|---:|---:|---:|']
    for m,t in [('M5_hpwl','wire_total'),('M5_hpwl_local','wire_local_peak'),('M3_load','cap_total'),('M3_load_local','cap_local_peak')]:
        p=corr['pooled'][m][t]
        lines.append(f'| {m} / {t} | {fmt(p["mean_normalized"]["spearman"])} | {fmt(p["fractional_ranks"]["spearman"])} | {fmt(min(s[d][m][t]["spearman"] for d in DESIGNS))} |')
    lines += ['', 'Each design receives total weight one. There are no fitted coefficients, per-design '
        'coefficients, ML models or leave-one-design-out tuning; the same frozen formulations apply '
        'to all designs. This is evidence of consistency within this set, not extrapolation to other '
        'technologies, placement seeds, chain counts or large designs.','',
        '## Direct answers to the research questions','',
        '**1. Why did H_eff8 fail?** It summarizes logical/spatial FF transitions without the actual '
        'source-dependent driven-load distribution. A low logical hotspot score can move transitions '
        'onto physically longer or more heavily loaded net trees. It neither accounts for each '
        'functional-plus-scan tree nor reproduces this experiment’s fixed-window local objective. '
        's15850 preserves the sign reversals for both routed-wire endpoints.','',
        '**2. Which physical property explains the largest mismatch?** The evidence points to '
        'whole FF-driven tree extent for the geometric mismatch: M5 HPWL reaches rho 0.943–1.000 '
        'for geometric totals and 0.943–1.000 for local peaks. Scan-link-only distance, raw toggles '
        'and fanout/pin-only alternatives fail to do this across designs. For the electrical-load '
        'target, input pin capacitance changes the balance: M3 adds it to estimated wire load and '
        'reaches total rho 0.943–1.000 and local rho 0.886–0.983. The component fractions below '
        'quantify contributions; this diagnostic does not establish a unique causal variance decomposition.','',
        '| Design | Pin share of cap activity, range | Ground-wire share, range | Incident-coupling share, range |',
        '|---|---:|---:|---:|']
    for d in DESIGNS:
        g=[r for r in diagnostics if r['design']==d]
        ranges=[]
        for k in ('pin_ff','ground_ff','coupling_ff'):
            v=[r['cap_activity_fractions'][k]*100 for r in g]
            ranges.append(f'{min(v):.1f}–{max(v):.1f}%')
        lines.append(f'| {d} | '+' | '.join(ranges)+' |')
    lines += ['', '**3. Does routed-wirelength weighting materially change ranking?** Yes. The '
        'raw-total versus wire-total comparisons below include negative s15850 association and '
        'many reversed architecture pairs.','',
        '**4. Does capacitance weighting change ranking further?** Yes. Capacitance-plus-pin '
        'load is a different reference and changes further total/local pair orders. Ground-only '
        'versus incident-coupling results also differ, especially s9234; the coupling convention '
        'is consequential and must accompany any use of the metric.','',
        '| Design | Comparison | rho | Reversed / all non-tied pairs |',
        '|---|---|---:|---:|']
    for d in DESIGNS:
        for key,v in comparisons[d].items():
            counts=v['counts'];den=counts['agree']+counts['disagree']
            lines.append(f'| {d} | {key.replace("__"," → ")} | {fmt(v["spearman"])} | {counts["disagree"]}/{den} |')
    lines += ['', '**5. Can placement-time information predict the post-route target?** Yes, '
        'within the frozen set and specified waveform/reference: the appropriate whole-tree '
        'geometric or pin-plus-wire feature consistently improves the relevant endpoint. This '
        'does not establish accurate absolute electrical energy.','',
        '**6. Which surrogate works best without target leakage?** M5 HPWL is the strongest '
        'simple geometric family; M3 pin-plus-estimated-wire load is the preferred electrical-load '
        'candidate. M3 is the research recommendation for a future load-aware objective, with '
        'M5 retained as a geometric diagnostic. A universal metric independent of target choice '
        'has not been qualified.','',
        '**7. Does it generalize across all three designs?** M5 passes both geometric endpoints '
        'and M3 passes both capacitance-load endpoints on all three. M3 does not pass the geometric '
        'gate and M5 does not pass the electrical gate. The joint preregistered outcome is PARTIAL. '
        'The separate FF capture/unload sensitivity below supports M3 but does not replace the '
        'primary waveform or upgrade the preregistered result.','',
        '**8. What is the computational complexity?** Shared graph construction is '
        'O(N_instances + N_sinks), sparse per-architecture weights O(N_ff + reachable N_sinks). '
        'Given cached per-FF toggle counts, a total is an O(N_ff) dot product. The implemented '
        'packed-trace evaluator costs O(N_ff × N_shift_cycles + N_spatial_bins × N_shift_cycles) '
        'per total/local pair. N_shift_cycles = N_patterns × longest_chain for the primary waveform. '
        'Working memory uses 1,024-cycle chunks, O(1,024 × (N_ff + N_spatial_bins)), plus packed '
        'input trace; no dense N_ff² matrix is built. An event-based implementation can update '
        'totals/local bins in O(number_of_shift_toggles), but that performance is not measured here.','',
        '**9. Is it cheap enough for future large-scale optimization?** Weight construction and '
        'cached-count totals are plausible building blocks. Exhaustive waveform recreation and '
        'full local-peak scoring per search candidate are not yet demonstrated practical at '
        '100k–1M gates. The supplementary proof recorder retains full states/toggles and is '
        'unsuitable at that scale without streaming. Do not extrapolate these small-design '
        'timings into a million-gate throughput claim.','',
        '**10. Is electrical validation complete?** No. Exact-route RC extraction and a clearly '
        'defined FF-source capacitance-load reference are qualified here. Actual energy/dynamic '
        'power, time-dependent coupling, clock/PI/SE and full combinational/internal/glitch activity '
        'remain INCOMPLETE. This is no longer blocked on obtaining SPEF; it is limited by reference '
        'scope and waveform/power analysis.','',
        '**11. Should PACT replace H_eff8 now?** Do not install an optimizer replacement in '
        'Phase-2B. H_eff8 should not be treated as a physical/electrical switching objective. '
        'Retain it as a logical diagnostic; carry M3 load weighting forward as the most defensible '
        'electrical-load candidate and M5 as the geometric companion. Further qualification '
        'across seeds/designs and scalable waveform evaluation should precede a separately '
        'authorized integration decision. The evidence supports continued activity research, '
        'not abandonment or automatic Phase-2C.','',
        '## Waveform audit and supplementary sensitivity','',
        'FAN BASIC_SCAN contains complete binary PI1/PPI/PPO for these patterns; PI2/PO2/SI '
        'fields are empty. The upstream STIL writer defines PI1 setup, a capture clock, next '
        'load/unload and final unload. An independent Icarus simulation forces each loaded '
        'Q, applies PI1 with SE=0, checks D against PPO and PO against PO1, then pulses the '
        'actual library FF clock and verifies captured Q after release. All three designs pass. '
        's9234 source uses a different module name, resolved from its netlist.','',
        'The existing cell-library `TETRAMAX` functional mode disables SDF xbuf wrappers, '
        'including a self-driven SE wrapper that produced unknown captured Q in the default '
        'Icarus configuration. The functional mux and sequential UDP remain unchanged. Failed '
        'wrapper-probe logs are retained; no frozen library or netlist was edited.','',
        'The new recorder checks every SI stream, final loaded state, scan-out sequence and '
        'padding tail against the existing independent verifier. Next load starts from the '
        'validated captured response. Short chains receive leading zero padding and continue '
        'clocking; final unload clocks the longest length with explicit zero SI. This is a '
        'qualified **FF-boundary reconstructed protocol**, not an observed timed tester waveform. '
        'The full-circuit status remains `FULL_TEST_WAVEFORM_UNQUALIFIED`.','',
        '[waveform_audit.json](waveform_audit.json) contains field counts, commands, logs, '
        'pattern boundaries and hashes. Supplementary correlations use this separate sequence '
        'and its correspondingly rescored reference labels; frozen H_eff8 is not redefined.','',
        '| Design | Family | Wire total rho | Wire local rho | Cap total rho | Cap local rho |',
        '|---|---|---:|---:|---:|---:|']
    sc=read(REPORT/'waveform_sensitivity_statistics.json')['correlation']['per_design']
    for d in DESIGNS:
        for m in ('M5_hpwl','M3_load'):
            vals=[sc[d][m]['wire_total']['spearman'],sc[d][m+'_local']['wire_local_peak']['spearman'],sc[d][m]['cap_total']['spearman'],sc[d][m+'_local']['cap_local_peak']['spearman']]
            lines.append(f'| {d} | {m} | '+' | '.join(map(fmt,vals))+' |')
    timings=cost['rows'];evals=[r['total_and_local_seconds'] for r in timings]
    constructions=[r['shared_weight_construction_seconds'] for r in timings]
    lines += ['', '## Measured cost and validation','',
        f'Placed graph export took {min(v["seconds"] for v in cost["placed_graph_construction"].values()):.3f}–'
        f'{max(v["seconds"] for v in cost["placed_graph_construction"].values()):.3f} s/design. Shared construction '
        f'of all weight vectors took {min(constructions):.3f}–{max(constructions):.3f} s/architecture. '
        f'An individual total-plus-local evaluation took {min(evals):.3f}–{max(evals):.3f} s '
        f'(179–534 FFs; single BLAS thread). Peak measurement-process RSS was '
        f'{cost["peak_process_RSS_KiB"]/1024:.1f} MiB. These include packed trace decoding and '
        'binning, not extraction or graph construction. [complexity.json](complexity.json) '
        'contains every metric/architecture timing and dimensions; waveform reconstruction '
        'runtime/RSS is separately reported in waveform_audit.json.','']
    for name in ('focused_tests.log','regression.log'):
        text=(REPORT/name).read_text();summary=next((l for l in reversed(text.splitlines()) if 'passed' in l),'INCOMPLETE')
        lines.append(f'- [{name}]({name}): {summary}.')
    lines += ['', 'Tests cover hand-calculated shift/capture/padding/unload behavior, FF counts, '
        'fanout, nested Liberty units, HPWL versus shared/star trees, sparse binning, missing '
        'SPEF/cap accounting, target-feature rejection, tied statistics, decision gates, '
        'determinism and provenance corruption. Old tests were not edited.','',
        '## Reproduction and figure index','',
        'See [README](README.md) for execution order and [environment.json](environment.json) '
        'for exact commands. The initial Git commit and dirty state are recorded; earlier '
        'uncommitted work remains untouched. Input, source, raw measurement and compact output '
        'hashes are verified in [integrity_audit.json](integrity_audit.json), '
        '[measurement_provenance.json](measurement_provenance.json) and [result_provenance.json](result_provenance.json).','',
        '- [Geometric totals](surrogate_vs_wireweighted_total.png) and [geometric local peaks](surrogate_vs_wireweighted_local_peak.png).',
        '- [Capacitance totals](surrogate_vs_capweighted_total.png) and [capacitance local peaks](surrogate_vs_capweighted_local_peak.png).',
        '- [s5378](s5378_scatter_rank_atlas.png), [s9234](s9234_scatter_rank_atlas.png), [s15850](s15850_scatter_rank_atlas.png): complete cross-endpoint atlases, normalized scatter with rank insets.',
        '', 'Raw SPEF, ODB copies, traces, testbenches, logs and per-FF weights remain under '
        '`D:/PACT_EXPERIMENTS/results/phase2b_activity_model`. The repository contains only '
        'compact reports, code, tests and figures. Phase-2B ends here.']
    (REPORT/'phase2b_summary.md').write_text('\n'.join(lines)+'\n')
    (REPORT/'README.md').write_text('''# Phase-2B activity model qualification

Read [phase2b_summary.md](phase2b_summary.md) for the decision and all 11 research answers.
Classification: **PACT_PHASE2B_SURROGATE_PARTIAL**. M5 qualifies for geometric ranking,
M3 for the defined capacitance-load ranking on the frozen set; no joint qualification.
Electrical energy/power remains INCOMPLETE. Phase-2A evidence remains unchanged.

Run from the PACT repository in the existing WSL environment. Exact commands and
dependencies are recorded in environment.json. Freeze is one-time and refuses
replacement; existing evidence must pass its hashes before any stage runs.

1. `scripts/phase2b_freeze.py` — one-time contract; requires native initial_git_status.txt.
2. `openroad -python -no_init -exit scripts/phase2b_extract.py` — placed-only graph and copied-route extraction.
3. `/root/pact-deps/pact-venv/bin/python scripts/phase2b_waveform.py` — independent Icarus capture checks and supplementary FF traces.
4. `OPENBLAS_NUM_THREADS=1 /root/pact-deps/pact-venv/bin/python scripts/phase2b_measure.py` — metrics with no optimizer import or search.
5. `/root/pact-deps/pact-venv/bin/python scripts/phase2b_report.py` — correlations, ranks, pairwise comparisons and figures.
6. Focused tests, then full regression (commands in environment.json).
7. `/root/pact-deps/pact-venv/bin/python scripts/phase2b_finalize.py` — report, complete manifests and integrity.

Set PYTHONDONTWRITEBYTECODE=1, PYTHONPATH=src:/mnt/d/PACT_EXPERIMENTS/cache/phase2a_python,
TMPDIR=/mnt/d/PACT_EXPERIMENTS/tmp, MPLCONFIGDIR=/mnt/d/PACT_EXPERIMENTS/cache/matplotlib.
Large artifacts stay on D:. The prior dirty source dependencies are hash-frozen in
provenance.json; the parent Git commit alone does not reconstruct that prior state.

The primary comparison uses frozen carry-loaded/no-capture/no-final-unload activity.
Supplementary load/capture/unload results never replace primary measurements.
Capacitance counts are fF-transitions with explicit coupling convention, not energy.
''')
    checkpoint=json.loads((REPORT/'determinism_checkpoint.json').read_text(encoding='utf-8-sig'))
    assert checkpoint['primary_candidate_metrics_sha256']==file_sha256(REPORT/'candidate_metrics.json')
    assert checkpoint['supplementary_metrics_sha256']==file_sha256(REPORT/'waveform_sensitivity.json')
    integrity()
    raw={str(p):file_sha256(p) for p in sorted(WORK.rglob('*')) if p.is_file()}
    source={str(p):file_sha256(p) for folder in (ROOT/'scripts',ROOT/'src/pact/analysis',ROOT/'tests/unit') for p in sorted(folder.glob('*phase2b*')) if p.is_file()}
    write(REPORT/'measurement_provenance.json',dict(completed_utc=datetime.now(timezone.utc).isoformat(),files=raw,source_files=source))
    write(REPORT/'integrity_audit.json',dict(status='PASS',
        frozen_input_files_unchanged=len(read(REPORT/'provenance.json')['inputs']),architectures=21,
        new_routes=0,new_optimizer_runs=0,new_ATPG_runs=0,new_placements=0,
        old_evidence_and_source_unchanged=True,primary_metric_byte_identical_rerun=True,
        capacitance_qualified=cap['capacitance_qualified'],FF_waveform_status=wave['status'],
        energy_portion='INCOMPLETE',raw_files_hashed=len(raw),source_files_hashed=len(source),
        raw_storage_bytes=sum(p.stat().st_size for p in WORK.rglob('*') if p.is_file())))
    compact={p.name:file_sha256(p) for p in sorted(REPORT.iterdir()) if p.is_file() and p.name!='result_provenance.json'}
    write(REPORT/'result_provenance.json',dict(files=compact,note='This manifest is excluded from its own hash. Source and raw files are in measurement_provenance.json.'))
    print('FINAL',decision['classification'],'integrity PASS',len(raw),'raw files hashed')

if __name__=='__main__':main()
