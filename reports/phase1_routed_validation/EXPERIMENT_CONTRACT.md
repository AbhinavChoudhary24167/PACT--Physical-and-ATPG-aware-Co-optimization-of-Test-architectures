# Phase-1 frozen experimental contract

Frozen before any new routing. Designs s9234 and s15850; physical seed 11; K=2.
s5378 is reference evidence only and must not be rerouted. Optimizer-v2.3 is unchanged.

Selection population: union of final retained architectures from all six qualified
v2.3 runs per design (equal evaluations and equal wall, W=1/2/4). Deduplicate by
canonical SHA256, then exact nondominance on authoritative physical proxy and H_eff8.
Physical extreme minimizes (physical,H,hash); activity extreme minimizes (H,physical,hash).
Balanced minimizes sum_i ((f_i-min_i)/(max_i-min_i))^2 over that global frontier;
zero ranges contribute zero; ties use (physical,H,hash). Overlapping roles share a
route; never substitute another point. No routed result enters selection.

Physical proxy: existing fixed FF-origin Manhattan scan-path cost, including fixed
SI/SO links. H_eff8: frozen 8x8 bin direct-sink-weighted toggle field, fixed 3x3
1/(1+Manhattan distance) kernel, peak over bins and fully clocked parallel shift
cycles. Existing FAN PPI vectors, carry-loaded/no-capture semantics, placed DEF/V,
identity mapping, weights and definitions are hash-frozen in provenance.json.
No ATPG, placement, activity database, baseline campaign, or optimizer regeneration.

Flow: qualified Nangate45 ORFS 5e8b1450d19263f797a27c4f371b9dd19f32a3aa;
OpenROAD 26Q2-1164-g08f67ee5ec in Ubuntu-24.04 WSL. Same design configs and SDCs,
seed-11 B0 3_place.odb/sdc, phase0c_rewire_odb.py, make route GRT_SEED=11,
OPENROAD_EXE=/usr/bin/openroad, YOSYS_EXE=/usr/bin/yosys. Only output locations
and variant names differ. WORK_HOME and all large/transient data use D:/PACT_EXPERIMENTS.
600-second route timeout, 120-second rewire, 90-second verification. One route
attempt per selected architecture, at most three per design, SIX total; ZERO new
baseline routes because all six compatible methods exist. Failures stay visible.

Baselines: all qualified seed-11 K=2 B0/P/A/J50/T/R routes, reused after archive
hash and structural proof checks; current P materialization must reproduce the
historical ODB hash. B0 is conventional supplied order; P physical; A activity;
J50 joint; T long-edge-risk; R randomized. B1 native is K=1 and excluded.

Primary routed objective: existing routed_full_scan_path_net_length_upper_bound_um,
paired with authoritative pre-route H_eff8. It includes shared functional branches
and may count shared net lengths per link; it is not exclusive scan wirelength.
Exact scan-only cost is reported only if available. Full-design detailed wirelength,
DRC, vias, existing congestion, timing and reported area are descriptive metrics.
Timing is GLOBAL-ROUTE timing as in the qualified flow, not signoff detailed-route STA.

Test quality: frozen coverage/pattern counts, FF bijection, K=2, minimum length 8,
maximum chain difference 2, exact parallel load/unload reconstruction and frozen
architecture identity; verify all routed scan links through transparent buffers.
Re-evaluation of selected immutable architectures is verification, never search.

Pareto survival requires a qualified PACT point nondominated against ALL compatible
baselines and not simply equal to an existing baseline objective pair. Use exact
two-objective dominance, with no weighted score. Report pairwise rank concordance
and inversions between proxy and routed path cost. Balanced usefulness requires a
distinct routed nondominated point representing a tradeoff against at least one
extreme; report otherwise. No minimum effect threshold is invented after results.

CONFIRMED requires sufficient valid comparisons, preserved test quality and routed
nondominated improvement/tradeoff on BOTH new designs. MIXED: only one supports it.
ADVANTAGE_NOT_REPLICATED: neither supports it with sufficient valid evidence.
INCOMPLETE: insufficient implementation evidence (including any missing selected
route or structural/test-quality failure). Full classification prefix is
PACT_PHASE1_MULTI_DESIGN_ROUTED_VALIDATION_ except the negative label, which is
PACT_PHASE1_MULTI_DESIGN_ROUTED_ADVANTAGE_NOT_REPLICATED.
No universal generalization, measured-power or IR-drop claim follows.
