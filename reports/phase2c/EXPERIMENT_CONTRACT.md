# PACT Phase-2C preregistered contract

A/B. Primary benchmarks s5378, s9234, s15850; ALL existing qualified physical
seeds 11,13,17,19,23. These are correlated perturb-and-legalize replicas from
one global placement (config/phase0b_seed_method.json), not independent placer runs.
No seed replacement or correlation-driven selection. Secondary larger design:
LARGE_DESIGN_NOT_AVAILABLE under the existing qualified scan/ATPG pipeline.

C/D. All 21 Phase-2B scan orders, nine/six/six per design, K=2; 105 cells in
the design x seed x architecture matrix. Preserve exact chain membership,
order, IDs and FF bijection. Architecture SHA includes coordinates: record
original SHA, new physical SHA and invariant scan-order SHA separately.
Use seed-specific frozen cell origins with identical chains. Existing routes
may be reused ONLY if physical architecture and input/proof hashes match;
do not confuse a per-seed regenerated P/A/J50/T order with the seed-11 order.
New routes use existing rewire/verification/ORFS flow, GRT_SEED=physical seed,
one attempt each, 600 s route/120 s rewire/90 s verify/180 s extraction caps.
Existing seed-11 measurements, traces and RC are reused after hashing.

E. EXACT Phase-2B primary: all-zero initial FF state; carry-loaded between
patterns; leading zero pad on short chains; clock every chain Lmax times;
no capture and no final unload. Frozen FAN patterns and identity mapping.
Supplementary final unload and arbitrary initial states are engineering tests
only and do not alter physical correlation labels.

F/G. Reuse phase2b_loads.construct_weights unchanged, graph export unchanged,
M5_hpwl = sum toggles * owned-tree placed HPWL; M3_load = sum toggles *
(input pin fF + 0.103981 fF/um * owned-tree HPWL). Coefficient from same
Nangate45 setRC.tcl metal3, never fit/calibrated. FF Q/QN ownership, SI/SO,
transparent BUF/CLKBUF/INV branches, cell origins and ports exactly Phase-2B.
No routed data in predictors. Reuse phase2a_extract_odb.extract and OpenRCX
reference parser, exact detailed route. Cap = ground + one-times incident
coupling + routed input pin load. Model 0/corner X, threshold 0.1 fF,
cc_model=10, context_depth=5, version=1.0. Fixed die 10x10 bins/all 81 contained
2x2 windows, load assigned to source FF. Targets wire_total, wire_local_peak,
cap_total, cap_local_peak. No energy/power claim. Source definitions are hashed.

H/I. Per-design/per-seed Spearman, Kendall tau-b, secondary Pearson, ascending
ranks and all tied/non-tied pairs via unchanged Phase-2B statistics. EXACT
Phase-2B gate: rho >= 0.7 AND correct non-tied directions >= 75%, on BOTH
endpoints on EVERY design. Apply geometric gate to M5 and capacitance gate
to M3, independently at EVERY registered seed. Undefined statistics fail.
Report worst/mean/median seed rho, pairwise seed ranking stability and pass
fractions; equal-design aggregates are secondary, never rescue a failed cell.
CONFIRMED requires both families pass every seed, complete provenance and
event equivalence. PARTIAL if one family or some seed/design cells pass;
FAIL if neither family has any passing complete design/seed pair. No weakening
of the original endpoint gates. Infrastructure incompleteness blocks a global
positive conclusion but does not relabel observed scientific failures.

J. Equivalence is mandatory: integer counts exact; floating totals/local
peaks rtol=1e-12, atol=1e-10 (double summation reordering only); peak witnesses
must attain the independent maximum within that tolerance. Rank and Spearman
identity required on real evidence. Tied maxima use earliest cycle/window;
record numerical tie ambiguities. Compare every existing primary and available
capture/unload trace and every newly qualified physical weight/bin set.
Scalability gate: median event end-to-end wall time < packed end-to-end wall
time AND median peak RSS <= packed on measured real architectures. Report
score-only separately; sparse synthetic improvement cannot rescue a real-data
performance failure. No mandatory speedup factor invented from Phase-2B.
Benchmark each implementation in separate fresh processes, one BLAS thread,
three repetitions on representative P orders for real designs; synthetic
N=1000,10000,100000, K=2, four patterns, sparse and dense inputs. Synthetic
scaling uses a bounded 1024-cycle stream (not a physical experiment).
100k/1M FF projections must be explicitly analytical, not measured physical scale.

K/L/M. Stop before changing definitions if a legacy bug is demonstrated.
Integrity mismatch stops affected scientific execution; no silent exclusions.
Failures: TOOL_FAILURE, PLACEMENT_FAILURE, ROUTE_FAILURE, TIMING_FAILURE,
EXTRACTION_FAILURE, PROVENANCE_FAILURE, UNSUPPORTED. Require zero DRC and
existing routed structural proof. Report timing as existing global-route STA;
missing/nonfinite timing is TIMING_FAILURE, negative slack is reported (the
inherited flow has no zero-slack acceptance gate). Equivalence failure yields
EVENT_EVALUATOR_EQUIVALENCE_FAIL and PACT_PHASE2C_EVENT_EVALUATOR_FAIL; do not
use event results for conclusions. Genuine unavailable infrastructure yields
PACT_PHASE2C_INFRASTRUCTURE_BLOCKED. Preserve failed attempts and logs.
No optimizer/search/ATPG regeneration, ML, new surrogate, calibration or push.
All data outside compact reports live under D:/PACT_EXPERIMENTS/results/phase2c.
