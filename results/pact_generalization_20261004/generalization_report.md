# PACT_V1_GENERALIZATION_BLOCKED_BY_SCALABILITY

The forward campaign is blocked by the fixed-budget physical-metric simulation resource limit and, independently, by the missing unseen-design P0 initialization contract before PACT search. No new PACT candidate was evaluated, preselected, routed, or qualified. Generalization benefit and solver runtime/memory scaling therefore remain unmeasured.

## Frozen core

- Tag: `pact-v1-core-frozen-20261004` at `9cc69bc077171c34d7aa1e45711489ff4bfed969`.
- Integrity: `PACT_V1_CORE_FREEZE_VERIFIED`; no historical search, routing, ATPG, or extraction was rerun.
- [Exact manifest](manifests/pact_v1_frozen_manifest.json), [integrity receipt](manifests/freeze_verification.json), and [additive provenance relocations](manifests/pact_v1_frozen_relocated_manifest.json).
- All original canonical dictionaries and the original primary CSV byte prefix remain unchanged. The relocated bindings recover identical bytes from retained evidence/Git without editing historical receipts.

## Preregistered unseen set

Selected 8; infrastructure-qualified 6; references with qualified extracted activity 4; new PACT designs completed end-to-end: 0.

All eight available unused mapped circuits were selected before outcomes from the pinned FAN ISCAS89 source set. They span 6–1,728 FFs and 21–145 patterns. No selected circuit was removed after outcomes. The available unseen set has a gap between 29 and 1,426 FFs; it supplies no new medium-size circuit.

| Design | FFs | Patterns | Infrastructure | Reference | PACT outcome |
|---|---:|---:|---|---|---|
| s208 | 8 | 29 | PACT_EXECUTION_BLOCKED | — | PACT_EXECUTION_BLOCKED |
| s510 | 6 | 59 | PACT_EXECUTION_BLOCKED | — | PACT_EXECUTION_BLOCKED |
| s953 | 29 | 89 | INFRASTRUCTURE_QUALIFIED | B2 | PACT_EXECUTION_BLOCKED |
| s1196 | 18 | 134 | INFRASTRUCTURE_QUALIFIED | B2 | PACT_EXECUTION_BLOCKED |
| s1238 | 18 | 145 | INFRASTRUCTURE_QUALIFIED | B3T | PACT_EXECUTION_BLOCKED |
| s35932 | 1728 | 21 | INFRASTRUCTURE_QUALIFIED | B2 | PACT_EXECUTION_BLOCKED |
| s38417 | 1636 | 105 | INFRASTRUCTURE_QUALIFIED | B2 | PACT_EXECUTION_BLOCKED |
| s38584 | 1426 | 133 | INFRASTRUCTURE_QUALIFIED | B3T | PACT_EXECUTION_BLOCKED |

`s208` and `s510` hit the unchanged requirement of at least eight FFs per chain with K=2. Their ATPG receipts are retained. K and the guard were preserved.

## External references

Each available reference was selected as the minimum qualified routed scan cost among B0/B1/B2/B3T. The two long-buffer-path failures on s38417 were repaired before final reference selection, using retained routes. Earlier provisional/failing receipts are preserved. [Selection and all-method provenance](baselines/generalization_baselines.json).

| Design | Reference | Routed scan WL (µm) | E (fF transitions) | H4 | H8 | WNS (ns) | DRC | Fault coverage (%) |
|---|---|---:|---:|---:|---:|---:|---:|---:|
| s953 | B2 | 557.39 | 306019.1604 | 141.7918542 | 63.23074092 | 9.34959 | 0 | 97.85344189 |
| s1196 | B2 | 391.125 | 119646.8763 | 47.09376932 | 25.6186611 | 9.1335 | 0 | 98.84020619 |
| s1238 | B3T | 487.945 | 124295.6667 | 47.43622182 | 25.01900066 | 9.07492 | 0 | 96.36255218 |
| s35932 | B2 | 46953.59 | 262385378.2 | 1825.085156 | 577.6583052 | 8.41392 | 0 | 87.57823592 |
| s38417 | B2 | 36842.35 | unavailable | unavailable | unavailable | 8.72304 | 0 | 95.99534691 |
| s38584 | B3T | 97311.1 | unavailable | unavailable | unavailable | 8.49908 | 0 | 93.32968009 |

These rows are external references. Primary and alternative PACT candidates, and their changes in WL/E/H4/H8, are unavailable because no search started. The original three-design PACT rows and legitimate alternatives remain in [canonical results](canonical/generalization_canonical_results.json) and [the full table](canonical/generalization_results_table.csv). [The primary comparison CSV](canonical/generalization_primary_comparison.csv) retains the original bytes as its prefix.

## Qualification and repairs

Qualified new references retain topology, exact FF inventory/placement, routing, extraction, timing reporting, zero DRC, serial replay, and FAN correctness gates. All 24 retained reference routes pass the frozen functional source/parity and exact FF-placement export checks. [All-reference gate receipts](physical/reference_export_gates.json). Completed activity measurements additionally check complete FF transition agreement. FAN comparisons cover the complete collapsed target classes, equivalence weights, detected collapsed classes, weighted full/detected counts, patterns, and coverage. Uncollapsed class-member identities are not enumerated.

Engineering repairs were isolated on repair branches and integrated only after focused regressions: direct scan-output endpoint recovery; existing runtime paths; reporting-field lookup; functional FF identity through Q-net renaming; and replacing the arbitrary eight-buffer traversal limit with a finite graph bound; and recognizing SDFF_X2 only after proving its frozen-library state/pin functions identical to SDFF_X1. No FF identities were dropped. The optimizer, metrics, objective, operators, and frozen files were preserved. The traversal repair changes only its guard expression; before/after gate, WL, functional verification, and net/capacitance mapping outputs are exactly equal on a previously passing unseen design. Nineteen focused regression tests passed. A reporting-only schema repair removed a duplicate CSV heading; all 18 row dictionaries and protected canonical/core hashes stayed unchanged. [Table schema receipt](repair_attempts/table_schema_repaired/qualification.json).

## Initialization blocker and scientific conclusion

The frozen loader raises `KeyError("s1196")` because its design table and artifact lookups cover only the historical three circuits. Its Stage-B starts also require a measured representative P0 from an earlier stateful search archive. That archive depends on prior candidate-sensitive/v2 selections and an earlier working-PACT architecture. The repository contains sealed historical endpoints, rather than a complete unseen-input construction rule. [Bound dependency audit](searches/initialization_audit.json); [reproduced loader failure](failures/frozen_initialization_contract.json).

The unresolved protocol must specify the precursor physical-input role, initial working-PACT seed and budget, qualification/seed propagation through the precursor stages, and how those stages fit the per-design routing limit. No P0 was omitted, substituted, or synthesized under an invented rule.

New primary candidates improving E, H4, H8, or all three: **not measured**. Mixed outcomes and negligible-benefit outcomes: **not measured**. No scientific support or rejection of PACT generalization can be inferred from this dataset.

The s38417 B2 reference passed structural, functional, routing, timing, DRC, extraction, and FAN gates, but its Icarus simulation exceeded the fixed 1,800-second measurement limit. Export, extraction, and compilation had completed; simulation and FF-transition/activity analysis had not. The partial VCD is retained by hash and excluded from every activity result. [Localized resource failure](failures/s38417_measurement_localization.json). This is an observed resource block under the campaign budget, rather than evidence against the PACT objective. Other reference routing ran concurrently; the observed wall time is not an isolated solver benchmark.

The s38584 full activity simulation was not started after this resource stop. Its four existing references completed routing, extraction, FAN, functional and FF-placement qualification. The canonical table includes its B3T reference and the s38417 B2 reference with null E/H4/H8, an explicit activity-unavailable status, and no PACT benefit or proxy values.

## Scalability

Solver: `PACT_SCALABILITY_NOT_MEASURED`. Physical metrics: `PHYSICAL_METRIC_SCALABILITY_BLOCKED_AT_s38417`. Exact candidate evaluations, solver CPU/RSS, evaluations/s, evaluator time, overhead, stagnation/restarts, and candidate-selection time have no new observations. [The scalability JSON](scalability_results.json) has an empty search dataset; [the CSV](scalability_results.csv) contains its header only. Measured route and reference activity times/resources are separate physical-stage records. No scaling model or size-of-impracticality claim is supported.

The preregistered search remains seed 11, K=2, epsilon 0.02/0.05/0.10, balanced weights (1,1,1), 20,000 maximum evaluations, and the fixed runtime rule 300×max(1,ceil(FF/600)) seconds. Neighborhood, segment, archive, lane, and stagnation settings remain frozen. [Exact configuration](searches/exact_configuration.json).

Qualified reference activity measurement wall time: 9.503–927.062 s; maximum RSS across those subprocess trees: 161.168–1253.488 MiB. These observations include extraction, simulation, and activity analysis; they are separate from solver cost.

## Measurement scope

Routed scan WL remains the connected scan-path net-length upper bound, including shared functional branches. E remains ground-plus-pin capacitance times transitions; H4/H8 remain source-localized peak bins per cycle over all data nets. These measurements do not establish watts, IR drop, signoff timing, or silicon reliability. The hotspot definitions were preserved and no ablation was run.

## Repository and retained evidence

Starting SHA: `9cc69bc077171c34d7aa1e45711489ff4bfed969`. Branch: `experiment/generalization-scalability-20261004`. Commit at report assembly: `d99c8a886a0630d2223c9efa3135bcc4132263c0`. The final response identifies the commit containing the report.

[Commit/file inventory](repository_state_at_report.json); [changed files](repository_changes.txt). Heavy new inputs, tools already present, routed databases, SPEFs, VCDs, and detailed execution logs remain at `D:\PACT_EXPERIMENTS\results\pact_generalization_20261004`; repository receipts bind them by exact hash. No duplicate installation or temporary build tree was committed.

[Final checkpoint inventory](repository_final_checkpoint.json) and [final changed files](repository_final_changes.txt) include the sealed report and table-schema repair. The ending commit is tagged `pact-v1-generalization-blocked-20261004`; resolve its exact SHA with `git rev-parse pact-v1-generalization-blocked-20261004`. The final response also supplies that SHA.

```text
6144db47 experiment: freeze qualified PACT v1 and preregister unseen benchmark campaign
659e0bcc repair: accept a verified direct terminal scan-output connection
81ddc2d8 experiment: preserve new benchmark preparation and first reference attempts
32c3e29e repair: restore frozen runtime paths and exact retained provenance bindings
de2cbb5e experiment: retain completed reference measurement and reporting failure
10199d64 repair: reconcile measurement receipt using frozen summary schema
e1a6d7f2 experiment: record frozen initialization limitation and reference qualification progress
9da8f82c repair: prove functional FF identity across placed net renames
4e3e015f repair: bound new-design scan traversal by the finite buffer graph
ae98e488 experiment: retain large-reference outcomes and audit frozen warm starts
8bfc4ca0 experiment: qualify all s38417 references without rerouting
76b6e2e0 repair: recognize only proven-identical resized scan FFs
b5fae534 experiment: retain large-reference activity and simulation resource failure
d99c8a88 Complete all-reference functional gates and blocked campaign assembly
```

## Remaining work

Resolve a reproducible unseen-design P0 construction protocol that retains frozen warm-start semantics, and the localized physical-metric simulation resource limit with evidence that preserves measurement semantics. Then run the preregistered searches, preselect at most three distinct candidates per design before route, qualify every selected candidate, and collect solver-only scalability data. The present artifacts are a reproducible blocked campaign checkpoint, not a completed generalization result.
