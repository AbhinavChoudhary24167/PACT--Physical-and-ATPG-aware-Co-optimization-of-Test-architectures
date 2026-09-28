# PACT implementation physical-effect milestone

## Classification

**PACT_PHYSICAL_EFFECT_MIXED**

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

| Design | Architecture | Patterns / shift cycles | Transitions (Δ) | Peak/cycle (Δ) | C·N, million fF transitions (Δ) | Local peak (Δ) | Local C·N, fF (Δ) |
|---|---|---:|---:|---:|---:|---:|---:|
| s5378 | P | 117 / 21,060 | 5,147,171 (+0.00%) | 603 (+0.00%) | 19.3755 (+0.00%) | 31 (+0.00%) | 186.564 (+0.00%) |
| s5378 | J50 | 117 / 21,060 | 4,889,711 (-5.00%) | 567 (-5.97%) | 18.6337 (-3.83%) | 33 (+6.45%) | 176.168 (-5.57%) |
| s5378 | PACT | 117 / 21,060 | 4,955,244 (-3.73%) | 595 (-1.33%) | 18.5634 (-4.19%) | 31 (+0.00%) | 167.803 (-10.06%) |
| s9234 | T | 156 / 33,072 | 11,805,835 (+0.00%) | 933 (+0.00%) | 39.3431 (+0.00%) | 54 (+0.00%) | 192.039 (+0.00%) |
| s9234 | J50 | 156 / 33,072 | 10,901,893 (-7.66%) | 876 (-6.11%) | 36.4532 (-7.35%) | 50 (-7.41%) | 197.393 (+2.79%) |
| s9234 | PACT | 156 / 33,072 | 11,671,923 (-1.13%) | 931 (-0.21%) | 38.8815 (-1.17%) | 50 (-7.41%) | 188.343 (-1.92%) |
| s15850 | P | 133 / 71,022 | 51,656,644 (+0.00%) | 1731 (+0.00%) | 161.9348 (+0.00%) | 90 (+0.00%) | 277.177 (+0.00%) |
| s15850 | J50 | 133 / 71,022 | 45,881,553 (-11.18%) | 1556 (-10.11%) | 145.2769 (-10.29%) | 90 (+0.00%) | 267.992 (-3.31%) |
| s15850 | PACT | 133 / 71,022 | 51,185,084 (-0.91%) | 1712 (-1.10%) | 160.4748 (-0.90%) | 90 (+0.00%) | 277.050 (-0.05%) |

## Local physical effect

- s5378: unweighted peak +0.00%, weighted peak -10.06%.
- s9234: unweighted peak -7.41%, weighted peak -1.92%.
- s15850: unweighted peak +0.00%, weighted peak -0.05%.

Prespecified grid-scale sensitivity (no resolution was selected after seeing results):

| Design | 4×4 local transitions Δ | 4×4 local C·N Δ | 8×8 local transitions Δ | 8×8 local C·N Δ |
|---|---:|---:|---:|---:|
| s5378 | -1.14% | +0.74% | +0.00% | -10.06% |
| s9234 | -0.79% | -8.15% | -7.41% | -1.92% |
| s15850 | +0.00% | +2.94% | +0.00% | -0.05% |

The coarser 4×4 weighted local result is negative evidence:
s5378 worsens by 0.74%; s15850 worsens by 2.94%.
Thus the spatial benefit is not robust across the prespecified locality scales.
The s15850 8×8 weighted improvement is only 0.05% in this model, not a demonstrated
signoff or silicon benefit.

These maxima do not necessarily occur at the same cycle or bin. Capacitance
weighting can change the conclusion because architecture-specific net loading
and the location of the worst event both change. Entire net weights are placed
at the source cell origin, or input-port center. This measures source-localized
demand, not the physical distribution of wire dissipation along routed segments.

## Total effect

- s5378: transitions -3.73%, weighted total -4.19%, peak/cycle -1.33%.
- s9234: transitions -1.13%, weighted total -1.17%, peak/cycle -0.21%.
- s15850: transitions -0.91%, weighted total -0.90%, peak/cycle -1.10%.

Strong activity-oriented baseline comparison:

- s5378, PACT versus J50: total transitions +1.34%, C·N -0.38%, local transitions -6.06%, local C·N -4.75%; routed-path upper bound -12.21%.
- s9234, PACT versus J50: total transitions +7.06%, C·N +6.66%, local transitions +0.00%, local C·N -4.58%; routed-path upper bound -7.55%.
- s15850, PACT versus J50: total transitions +11.56%, C·N +10.46%, local transitions +0.00%, local C·N +3.38%; routed-path upper bound -12.54%.

The explicitly order-sensitive scan-data scope gives:

- s5378, scan-data scope: total -3.53%, weighted total -3.81%, local peak -5.56%, weighted local peak -4.32%.
- s9234, scan-data scope: total -1.75%, weighted total -1.53%, local peak +0.00%, weighted local peak -1.11%.
- s15850, scan-data scope: total -1.22%, weighted total -0.99%, local peak +0.00%, weighted local peak -0.35%.

Clock nets and their transparent descendants are excluded and enumerated.
Meaningful secondary combinational switching is included in the primary scope.
Nets without a unique driver and power/ground are separately listed in
`net_mapping.json`; none is silently assigned a fabricated capacitance.

## M3/M5 correspondence

| Design | Architecture | M3 total / local Δ | M5 total / local Δ | Actual total / local Δ | Weighted total / local Δ |
|---|---|---:|---:|---:|---:|
| s5378 | J50 | -23.65% / -3.15% | -16.59% / +8.37% | -5.00% / +6.45% | -3.83% / -5.57% |
| s5378 | PACT | -5.87% / -5.04% | -5.58% / -0.71% | -3.73% / +0.00% | -4.19% / -10.06% |
| s9234 | J50 | -14.93% / -6.16% | -10.85% / -0.50% | -7.66% / -7.41% | -7.35% / +2.79% |
| s9234 | PACT | -3.04% / -2.39% | -2.87% / -1.51% | -1.13% / -7.41% | -1.17% / -1.92% |
| s15850 | J50 | -23.35% / -9.09% | -17.62% / -0.68% | -11.18% / +0.00% | -10.29% / -3.31% |
| s15850 | PACT | -1.44% / -0.62% | -1.01% / -0.14% | -0.91% / +0.00% | -0.90% / -0.05% |

Explicit failures to confirm the predicted direction:

- s5378: unweighted local peak is unchanged, despite lower recorded M3/M5 objectives.
- s15850: unweighted local peak is unchanged, despite lower recorded M3/M5 objectives.

PACT's optimizer predicts improvements in all four displayed objectives. The
independent measurements must be interpreted column by column: zero/positive
physical deltas do not confirm the predicted improvement. The comparison is
descriptive; no fitted correlation, model tuning or objective revision occurs.
The measurement also differs intentionally from the objective protocol: common
clock leading padding, actual capture between phases, zero-filled unload and
secondary gate activity. These are reasons the proxy need not predict every
physical extremum; this experiment does not isolate their individual causality.

## Physical cost

| Design | Architecture | Routed scan-path upper bound (µm) | Δ | Setup / hold WNS (ns) | DRC |
|---|---|---:|---:|---:|---:|
| s5378 | P | 5172.87 | +0.00% | 9.08788 / 0.002729 | 0 |
| s5378 | J50 | 5911.57 | +14.28% | 9.08673 / 0.002739 | 0 |
| s5378 | PACT | 5189.61 | +0.32% | 9.08655 / 0.002710 | 0 |
| s9234 | T | 10520.99 | +0.00% | 8.74351 / 0.000690 | 0 |
| s9234 | J50 | 11490.19 | +9.21% | 8.74920 / 0.000694 | 0 |
| s9234 | PACT | 10622.83 | +0.97% | 8.74283 / 0.001955 | 0 |
| s15850 | P | 24095.05 | +0.00% | 8.13298 / 0.000547 | 0 |
| s15850 | J50 | 27774.43 | +15.27% | 8.13268 / 0.001362 | 0 |
| s15850 | PACT | 24290.78 | +0.81% | 8.13237 / 0.000863 | 0 |

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
PYTHONPATH=src:.optimizer-deps /root/pact-deps/pact-venv/bin/python scripts/physical_effect.py prepare
# prepare is first-run only and refuses to overwrite the frozen manifest.
PYTHONPATH=src:.optimizer-deps /root/pact-deps/pact-venv/bin/python scripts/physical_effect.py run --design s5378
PYTHONPATH=src:.optimizer-deps /root/pact-deps/pact-venv/bin/python scripts/physical_effect.py run --design s9234
PYTHONPATH=src:.optimizer-deps /root/pact-deps/pact-venv/bin/python scripts/physical_effect.py run --design s15850
PYTHONPATH=src:.optimizer-deps /root/pact-deps/pact-venv/bin/python scripts/physical_effect_finalize.py
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
