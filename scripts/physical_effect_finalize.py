"""Render a factual final report from the measured comparison, then seal evidence."""
from pact.environment import python_executable
from physical_effect_report import collect, plots, delta
from physical_effect import *

def pct(v): return f'{v:+.2f}%'

def finalize():
    rows=collect()
    if len(rows)!=9: raise ValueError('All nine measurements required')
    plots(rows)
    pact=[r for r in rows if r['architecture']=='PACT']
    # Fixed primary criterion: whole nonclock data, total and spatial activity.
    keys=['total_transitions','cap_weighted_ff_transitions','peak_local','peak_local_cap_ff']
    changes=[r[k+'_pct_vs_physical_start'] for r in pact for k in keys]
    if all(v<0 for v in changes): classification='PACT_PHYSICAL_EFFECT_CONFIRMED'
    elif any(v<0 for v in changes): classification='PACT_PHYSICAL_EFFECT_MIXED'
    else: classification='PACT_PHYSICAL_EFFECT_NOT_CONFIRMED'
    # This classification is evidence-limited; physical costs remain explicit.
    table=['| Design | Architecture | Patterns / shift cycles | Transitions (Δ) | Peak/cycle (Δ) | C·N, million fF transitions (Δ) | Local peak (Δ) | Local C·N, fF (Δ) |',
           '|---|---|---:|---:|---:|---:|---:|---:|']
    for r in rows:
        table.append(f'| {r["design"]} | {r["architecture"]} | {r["patterns"]} / {r["shift_cycles"]:,} | '
            f'{r["total_transitions"]:,} ({pct(r["total_transitions_pct_vs_physical_start"])}) | '
            f'{r["peak_transitions"]} ({pct(r["peak_transitions_pct_vs_physical_start"])}) | '
            f'{r["cap_weighted_ff_transitions"]/1e6:.4f} ({pct(r["cap_weighted_ff_transitions_pct_vs_physical_start"])}) | '
            f'{r["peak_local"]} ({pct(r["peak_local_pct_vs_physical_start"])}) | '
            f'{r["peak_local_cap_ff"]:.3f} ({pct(r["peak_local_cap_ff_pct_vs_physical_start"])}) |')
    costs=['| Design | Architecture | Routed scan-path upper bound (µm) | Δ | Setup / hold WNS (ns) | DRC |',
           '|---|---|---:|---:|---:|---:|']
    for r in rows:
        costs.append(f'| {r["design"]} | {r["architecture"]} | {r["routed_path_upper_bound_um"]:.2f} | '
            f'{pct(r["routed_path_upper_bound_um_pct_vs_physical_start"])} | {r["setup_wns_ns"]:.5f} / {r["hold_wns_ns"]:.6f} | 0 |')
    correspondence=['| Design | Architecture | M3 total / local Δ | M5 total / local Δ | Actual total / local Δ | Weighted total / local Δ |',
                    '|---|---|---:|---:|---:|---:|']
    for r in [v for v in rows if v['architecture'] in ('J50','PACT')]:
        correspondence.append('| '+r['design']+' | '+r['architecture']+' | '+' | '.join(
            pct(r[a+'_pct_vs_physical_start'])+' / '+pct(r[b+'_pct_vs_physical_start'])
            for a,b in [('M3_load','M3_load_local'),('M5_hpwl','M5_hpwl_local'),('total_transitions','peak_local'),('cap_weighted_ff_transitions','peak_local_cap_ff')])+' |')
    disagreements=[]
    for r in pact:
        for key,label in [('total_transitions','total transitions'),('peak_transitions','peak transitions/cycle'),
                          ('cap_weighted_ff_transitions','weighted total'),('peak_local','unweighted local peak'),
                          ('peak_local_cap_ff','weighted local peak')]:
            value=r[key+'_pct_vs_physical_start']
            if value>=0:
                disagreements.append(f'- {r["design"]}: {label} '+('is unchanged' if value==0 else f'worsens by {value:.2f}%')+
                                     ', despite lower recorded M3/M5 objectives.')
    sensitivity=['| Design | 4×4 local transitions Δ | 4×4 local C·N Δ | 8×8 local transitions Δ | 8×8 local C·N Δ |',
                 '|---|---:|---:|---:|---:|']
    coarse_failures=[]
    for r in pact:
        d=r['design']; start='T' if d=='s9234' else 'P'
        a=read(OUT/d/'PACT/activity_summary.json')['scopes']['all_data']['grids']
        b=read(OUT/d/start/'activity_summary.json')['scopes']['all_data']['grids']
        sensitivity.append('| '+d+' | '+' | '.join(pct(delta(a[g][m]['maximum'],b[g][m]['maximum']))
            for g,m in [('4','peak_per_cycle'),('4','cap_peak_per_cycle'),('8','peak_per_cycle'),('8','cap_peak_per_cycle')])+' |')
        change=delta(a['4']['cap_peak_per_cycle']['maximum'],b['4']['cap_peak_per_cycle']['maximum'])
        if change>0: coarse_failures.append(f'{d} worsens by {change:.2f}%')
    local=[]; total=[]; j50=[]; scopes=[]
    for r in pact:
        local.append(f'- {r["design"]}: unweighted peak {pct(r["peak_local_pct_vs_physical_start"])}, '
                     f'weighted peak {pct(r["peak_local_cap_ff_pct_vs_physical_start"])}.')
        total.append(f'- {r["design"]}: transitions {pct(r["total_transitions_pct_vs_physical_start"])}, '
                     f'weighted total {pct(r["cap_weighted_ff_transitions_pct_vs_physical_start"])}, '
                     f'peak/cycle {pct(r["peak_transitions_pct_vs_physical_start"])}.')
        j50.append(f'- {r["design"]}, PACT versus J50: total transitions {pct(r["total_transitions_pct_vs_J50"])}, '
                   f'C·N {pct(r["cap_weighted_ff_transitions_pct_vs_J50"])}, local transitions {pct(r["peak_local_pct_vs_J50"])}, '
                   f'local C·N {pct(r["peak_local_cap_ff_pct_vs_J50"])}; routed-path upper bound {pct(r["routed_path_upper_bound_um_pct_vs_J50"])}.')
        scopes.append(f'- {r["design"]}, scan-data scope: total {pct(r["scan_transitions_pct_vs_physical_start"])}, '
                      f'weighted total {pct(r["scan_cap_weighted_pct_vs_physical_start"])}, local peak {pct(r["scan_peak_local_pct_vs_physical_start"])}, '
                      f'weighted local peak {pct(r["scan_peak_local_cap_ff_pct_vs_physical_start"])}.')
    text=f'''# PACT implementation physical-effect milestone

## Classification

**{classification}**

All nine exact routed implementations were measured. No optimizer, architecture
selection, workload, M3/M5 definition or physical route was regenerated.
The same frozen methodology was applied in order s5378 → s9234 → s15850.

## Physical quantity measured

Binary net transitions during real ATPG scan load and response unload, per
shift cycle, and extracted-ground-plus-sink-pin-capacitance-weighted transitions.
The primary comparison is the whole measured non-clock data network; a
scan-data scope separately isolates FF Q/QN and transparent descendants.
Local values use a source-localized 8×8 die grid. Prespecified 4×4 results,
means, P95/P99, separate load/unload totals and scope-specific measurements are
in `physical_metrics.csv`, `comparison.csv` and each architecture's summaries.
This is logical switching activity and C·N, not watts, full dynamic energy,
IR-drop, signoff activity or a silicon reliability result. No voltage is assumed.

## End-to-end measurement flow

```text
Original qualified FAN BASIC_SCAN patterns + verified FF identity map
→ original/remapped serial vectors (existing integration vectors for PACT)
→ exact archived 5_2_route.odb, topology/FF/placement/connectivity checks
→ OpenROAD Verilog export + exact ODB input-port alias adapter
→ Icarus Verilog 12.0 + original Nangate45 library, -DTETRAMAX, zero delay
→ timestamped VCD; explicit shift-cycle windows; capture excluded
→ OpenRCX on the same routed ODB + Nangate45 typical Liberty sink pin caps
→ per-net/per-cycle counts and 4×4 / 8×8 source-coordinate bins
→ fixed P/T, J50 and PACT comparison
```

Every pattern is checked at FF Q after load and actual functional capture;
every valid SO response bit is checked during unload. PACT uses the saved
`patterns_remapped.json` vector values, verified against its original hash and
the named source states. Baselines serialize those same logical states. No
ATPG regeneration or random test workload is used. The two chains shift on
one 10 ns clock. Both load and zero-filled unload are included; initialization,
PI/SE setup, and capture are excluded. The cycles are identical across roles
within each design. The root manifest and per-role simulation manifests bind
the input and generated netlist/ODB/workload/parasitic hashes before simulation.

## Results

Signed deltas use P for s5378/s15850 and T for s9234. Negative means reduction.
All results below use non-clock data scope and the 8×8 primary spatial grid.

{chr(10).join(table)}

## Local physical effect

{chr(10).join(local)}

Prespecified grid-scale sensitivity (no resolution was selected after seeing results):

{chr(10).join(sensitivity)}

The coarser 4×4 weighted local result is negative evidence:
{'; '.join(coarse_failures) if coarse_failures else 'no weighted local worsening was observed'}.
Thus the spatial benefit is not robust across the prespecified locality scales.
The s15850 8×8 weighted improvement is only 0.05% in this model, not a demonstrated
signoff or silicon benefit.

These maxima do not necessarily occur at the same cycle or bin. Capacitance
weighting can change the conclusion because architecture-specific net loading
and the location of the worst event both change. Entire net weights are placed
at the source cell origin, or input-port center. This measures source-localized
demand, not the physical distribution of wire dissipation along routed segments.

## Total effect

{chr(10).join(total)}

Strong activity-oriented baseline comparison:

{chr(10).join(j50)}

The explicitly order-sensitive scan-data scope gives:

{chr(10).join(scopes)}

Clock nets and their transparent descendants are excluded and enumerated.
Meaningful secondary combinational switching is included in the primary scope.
Nets without a unique driver and power/ground are separately listed in
`net_mapping.json`; none is silently assigned a fabricated capacitance.

## M3/M5 correspondence

{chr(10).join(correspondence)}

Explicit failures to confirm the predicted direction:

{chr(10).join(disagreements) if disagreements else 'None in the prespecified primary metrics.'}

PACT's optimizer predicts improvements in all four displayed objectives. The
independent measurements must be interpreted column by column: zero/positive
physical deltas do not confirm the predicted improvement. The comparison is
descriptive; no fitted correlation, model tuning or objective revision occurs.
The measurement also differs intentionally from the objective protocol: common
clock leading padding, actual capture between phases, zero-filled unload and
secondary gate activity. These are reasons the proxy need not predict every
physical extremum; this experiment does not isolate their individual causality.

## Physical cost

{chr(10).join(costs)}

The length is a sum of complete routed nets on scan paths, including shared
functional branches: an upper bound, not exclusive scan-only metal length.
DRC is from the exact detailed-route qualification. WNS is from the associated
**global-route stage of that same implementation run**, not post-extraction
signoff timing or a scan-mode timing proof. All reported setup/hold slacks are
positive. Archives, reports, topology, functional sink connectivity through
buffers/inverters, FF inventory and fixed FF coordinates were checked. No
freshness reroutes were performed.

## Electrical interpretation and IR-drop status

**Mode A** extraction succeeded on the actual routed implementations. OpenRCX
uses the installed Nangate45 rules, model index 0, coupling threshold 0.1 fF,
cc_model 10, context depth 5 and version 1.0. The primary C is the extracted
grounded capacitance plus actual Liberty input-pin capacitance. Extraction
grounds couplings below its threshold. Explicit larger coupling capacitances
are retained in `net_activity_capacitance.csv` but are excluded from the
primary C·N proxy because relative aggressor/victim waveforms determine their
energy. There is no arbitrary constant capacitance or assumed supply voltage.
Missing extraction on any switched net fails the analysis; missing static
nets, if any, are explicitly listed and excluded.

**IR_DROP_NOT_RUN**. OpenROAD and PDN geometry are available, and the library
contains electrical characterization. What is absent is a qualified mapping
from this workload's switching to instance current waveforms and qualified
PDN voltage-source boundary conditions for these runs. The existing route
reports likewise record `NOT_RUN_NO_QUALIFIED_TEST_CURRENT_MODEL`. No static
IR calculation is substituted for transient scan-shift voltage droop.

## Limitations

- Zero-delay simulation does not accurately model hazards, path delays or
  timing failures. VCD timestamp events are logical net events, not signoff
  glitch energy. The entire routed logic is simulated, with physical-only
  signal-free tap cells stubbed.
- C·N excludes internal cell power, short-circuit power, leakage, explicitly
  coupled-net energy and the clock network. It is not full-chip power.
- Cell-origin spatial assignment is approximate; no segment-resolved power
  density, current waveform, package/PDN droop or silicon margin was measured.
- This is three small qualified benchmarks, one physical seed, K=2, the saved
  recommendations and one explicit load/capture/unload protocol. It establishes
  these comparisons, not general industrial superiority over other frameworks.
- FAN **coverage/count equivalence PASS; detected-fault identity-set comparison
  BLOCKED** remains unchanged. The detailed-reporter SIGSEGV was not the work
  of this milestone. Actual functional capture/response checks are additional
  evidence, not a substitute for exact fault-set comparison.

## Next solution milestone

Deliver a **timing-aware, implementation-load-aware scan architecture backend**
that targets the physical tradeoff exposed here: retain the demonstrated
total-activity benefit while addressing spatial peaks and the J50 tradeoff.
Use the measured discrepancies to specify the backend's requirements before
changing objectives or search. Include characterized gate delays and actual
post-route loads; do not begin another broad validation or solver-runtime
optimization campaign. A PDN/current model is required before claiming IR benefit.

## Reproduction, evidence and repository state

Run with the existing Ubuntu-24.04 toolchain and qualified external paths:

```bash
PYTHONPATH=src:.optimizer-deps {python_executable()} scripts/physical_effect.py prepare
# prepare is first-run only and refuses to overwrite the frozen manifest.
PYTHONPATH=src:.optimizer-deps {python_executable()} scripts/physical_effect.py run --design s5378
PYTHONPATH=src:.optimizer-deps {python_executable()} scripts/physical_effect.py run --design s9234
PYTHONPATH=src:.optimizer-deps {python_executable()} scripts/physical_effect.py run --design s15850
PYTHONPATH=src:.optimizer-deps {python_executable()} scripts/physical_effect_finalize.py
```

Existing manifests contain absolute artifact paths and must be verified or
explicitly rebased on another machine. Raw VCD/SPEF/ODB files are local ignored
intermediates. Their hashes and generation commands, raw/corrected Verilog,
compressed stimulus and per-cycle schedules/summaries, per-net counts/caps, spatial summaries,
verification records and tool execution logs are preserved. Each execution
record includes elapsed seconds. Lossless count arrays remain local and hash-indexed
alongside the raw waveform. `validation_summary.json` records tests and
deterministic replay; `evidence_manifest.json` hashes compact deliverables and
measurement source. The milestone commit is the Git commit containing this
report; its parent is recorded in the frozen manifest (avoiding a self-referential
commit hash). Work remains on the existing development branch and is not pushed.

Figures: each design has `activity_cycles.png` and `spatial_hotspots.png`;
the root has `tradeoff.png` and `objective_correspondence.png`. No fitted trend
is asserted from the three designs.
'''
    (OUT/'final_report.md').write_text(text)
    write(OUT/'classification.json',dict(classification=classification,scope='all_data',primary_grid=8,
        criteria='strict reductions in total and local transition and capacitance-weighted metrics on every design for strong positive; otherwise mixed if any improvement',
        PACT_changes={r['design']:{k:r[k+'_pct_vs_physical_start'] for k in keys} for r in pact}))
    print(classification)

if __name__=='__main__': finalize()
