# PACT Phase-2C-R preregistered semantic repair and seed-11 requalification

This registration precedes corrected scientific measurements. The independent
bug reproduction passed. The scope is exactly the existing 21 seed-11 Phase-2B
architectures: s5378 (9), s9234 (6), s15850 (6), all K=2. `freeze.json` identifies
every architecture by existing path, file SHA256, canonical architecture SHA,
scan-order SHA, FF inventory and coordinates. No replacement or new architecture.
Preserve FF identities/bijection, chain IDs, membership, ordering and placement.

Frozen FAN patterns and identity mapping remain unchanged. Primary waveform:
all-zero initial FF state; carry-loaded across patterns; leading zero padding
on the shorter chain; shift every chain Lmax times; no capture; no final unload.
Reuse the exact archived primary packed activity and FF counts after hash checks.
The event evaluator is not modified or used to redefine semantics.

The new versioned predictor corrects only selected SI/SO connectivity.
M5_hpwl = sum(toggle_count_ff * owned_tree_placed_HPWL_ff).
M3_load = sum(toggle_count_ff * (input_pin_cap_ff + 0.103981 fF/um *
owned_tree_placed_HPWL_ff)). The coefficient is fixed exactly at 0.103981 fF/um;
no fitting, calibration, routed features, alternate surrogate, ML or optimizer.

Chain 0: identify the inherited BUF_X1 from the placed DEF, detach its unique
input sink and transparent child edge from the original Q root, reattach both
to the selected chain-0 final FF Q root, and add the placed-policy test_so port
to the buffer output net. Preserve all other sinks/edges. No synthetic direct
tail-to-test_so point. Recompute each net HPWL from its corrected point set;
sum uniquely owned transparent nets. Include the Liberty input pin once.
If original owner equals selected tail, preserve single ownership without
duplication. Chain > 0 keeps Phase-2B direct-port semantics. SI links are the
existing selected FF-to-FF links; PI-driven scan-input activity stays excluded.
Use the frozen Phase-0C deterministic edge-port policy from the placed DEF,
including relocation of inherited test_so; never take coordinates from route.

Before all-architecture processing, require the s5378/P numerical witness:
old owner U_n1588gat; tail U_n2121gat; output38/BUF_X1/A; transfer exactly
0.974659 fF once; retain unrelated pin load; recompute geometry from points.
No corrected scalar total is hard-coded. Afterward require topology PASS on
all 21 before any correlations: selected tail = predictor owner = physical
owner, exact architecture/scan order, unique pin/branch/port ownership,
preserved functional sinks and unrelated transparent edges, no routed input.
Historical Phase-2B weights must reproduce exactly. Unexpected changes outside
old-owner/selected-tail cones, ambiguity, hash/identity/pattern disagreement,
leakage or failed witness/topology immediately stop scientific execution.

Existing detailed-route/OpenRCX `physical.json`, `reference_weights.json`,
SPEF and routed ODB evidence are targets only. Verify existing provenance hashes
and reuse exact candidate_metrics targets: wire_total, wire_local_peak,
cap_total, cap_local_peak. Do not reconstruct targets, route, extract, repair,
regenerate ATPG or FAN patterns, or change orders/K. No power, energy or causal claim.

Use unchanged Phase-2B statistics: per-design Spearman rho, Kendall tau-b,
secondary Pearson, ascending average-tie ranks, exact tied/non-tied pair
directions. Preserve the original endpoint pairing: total predictor against
total reference and peak cycle/window predictor (`*_local`) against local
reference, with unchanged 10x10 bins/all 81 contained 2x2 windows. Also retain
cross-comparisons in the statistics artifacts. The gate remains rho >= 0.7 AND
correct non-tied directions >= 75%, BOTH corresponding endpoints per family
(M3 capacitance, M5 geometric). Undefined values fail. No pooled rescue,
new significance cutoff or multi-seed inference.

Quantify old/new total and local scores, pin/HPWL/FF changes, old/new rank
correlation, rank displacements, pair-direction changes, physical-correlation
deltas and gate changes. Distinguish value changes, ranking changes and
qualification changes; no invented threshold of quantitative materiality.

Statuses: PACT_PHASE2CR_BUG_REPRODUCED or BUG_REPRODUCTION_FAIL;
PACT_PHASE2CR_TOPOLOGY_PASS or TOPOLOGY_FAIL. After topology passes,
PACT_PHASE2CR_SEED11_REQUALIFIED iff both families pass on all three designs;
SEED11_PARTIAL if any complete design/family cell passes but not all;
SEED11_INVALIDATED if none passes. This classification is seed-11 only.
Engineering recommendation is MULTISEED_REPAIR_RERUN_JUSTIFIED only with bug
reproduction, 21/21 topology, regression pass and retained scientific signal;
otherwise NOT_JUSTIFIED or BLOCKED as appropriate. Do not launch that work.

Run focused tests then full regression in an isolated temporary directory.
Record counts, runtime, command, environment, failures and final rerun outcome.
Infrastructure failures are distinct from scientific failures. Preserve all
existing dirty/untracked work and all Phase-2B/C functions and artifacts.
Phase-2C remains STOPPED_LEGACY_DEFINITION_BUG. New compact artifacts go only
under results/phase2c_repair; reference large existing evidence by path + hash.
Stop when complete: no additional seeds, Phase-2D, routing, optimization or push.
