# Phase-2B physical activity model qualification contract

Freeze before collection. Retain all 21 Phase-2A architectures: 9 s5378,
6 s9234, 6 s15850. Fixed seed 11, K=2. No optimizer/search/ATPG/placement/
routing runs; no changes to any earlier evidence. Exact ODB archive and
decompressed hashes checked before extraction, copied to D: experiment area.

Primary waveform remains the exact Phase-2A zero-initial, carry-loaded,
no-capture/no-final-unload stable-state shift sequence, enabling direct comparison.
Audit all seven FAN fields and upstream BASIC_SCAN writer. If complete capture
states can be independently validated, record a separate load/capture/next-load/
final-zero-unload FF sequence; never mix its measurements into primary labels.
Zero final-unload SI is an explicit protocol choice, not recovered tester history.
Missing/unknown capture bits or unverifiable correspondence =>
FULL_TEST_WAVEFORM_UNQUALIFIED. No inferred glitches or cell internal switching.

Extraction: installed ORFS Nangate45 rules, model index 0, corner X, OpenRCX
on exact 5_2_route ODB copies. Preserve originals and do not invoke ORFS finish
(which deletes obstructions). Explicit coupling_threshold=0.1 fF; cc_model=10,
context_depth=5, version=1.0; inspect installed API. SPEF ground-only and
ground+one-times-coupling endpoint-load sensitivities. Main capacitance label
uses ground+one-times incident coupling, plus actual routed sink pin loads.
This is a load-weighted transition count, fF-transitions, NOT energy or power;
coupling does not model aggressor correlation or Miller switching. Sum owned
Q/QN nets through existing BUF/CLKBUF/INV paths, uniquely per FF; excludes other
logic, clock/PI/SE driven nets and cell internals. Investigate all-net metric
scope but do not invent missing combinational waveforms. Capacitance targets
exist only if every selected architecture passes nonzero RC, all owned nets
covered, finite values, SPEF accounting and exact route checks. Otherwise
electrical validation BLOCKED; continue geometric labels unchanged.

Fixed predictors: M0 raw toggles; M1 frozen H_eff8; M2 internal scan-link
Manhattan and port-aware FF-source output link distances (SI is not FF-driven);
M4 connected input count and Liberty pin capacitance; M5 sum of owned-net HPWL
and driver-to-sink Manhattan star length; M3 pin fF + 0.103981 fF/um * HPWL.
Metal3 coefficient comes from installed technology setRC.tcl, never fitted.
Functional-only M4/M5 variants omit added SI/SO loads. Start from pre-route
placed DEF graph, remove original SI/test_so connections, append selected
scan links and fixed output ports, traverse only pre-existing transparent
cells. Geometry uses cell origins and placed output-port locations; no route
length, routed placement, inserted route buffers or target enters predictors.
M6: local peak for every nonnegative per-FF weight using fixed Phase-2A bins.
No fitted coefficients, ML, per-design tuning or leave-one-out fitting needed.

Targets: raw total; frozen routed wire-weighted total and local peak;
qualified capacitance total/local peak only when available. Report every
predictor vs every target: Spearman, tau-b, Pearson, exact ascending rankings,
all pair directions with ties, equal-design mean-normalized and fractional-rank
pooling using Phase-2A implementation. No statistical significance claim.
Plots: two geometric scatter grids with ranks, optional two capacitance grids,
one compact design-by-metric heatmap. No retrospective binning or selection.

Decision: qualification requires a total/local metric family with rho>=0.7
and >=75% correct direction among non-tied pairs for BOTH geometric endpoints
on EVERY design, with no target leakage. If capacitance qualifies, require
the same electrical endpoint gate for joint qualification, report separately.
Partial if a family raises rho by >=0.2 over H_eff8 on BOTH geometric endpoints
on at least two designs but fails qualification; otherwise fail. These are
descriptive finite-set thresholds, not population validation. Preserve all
negative results. No automatic Phase-2C integration.

Measure graph/weight construction and scoring wall time, peak RSS, dimensions.
Use sparse/per-FF arrays; no dense FF-by-FF matrices. Focused analytic tests,
then full PACT regression. Hash prior evidence after execution, all inputs,
scripts and outputs. Large inventories/SPEF/traces/logs under
D:/PACT_EXPERIMENTS/results/phase2b_activity_model. No raw experiment data in git.
