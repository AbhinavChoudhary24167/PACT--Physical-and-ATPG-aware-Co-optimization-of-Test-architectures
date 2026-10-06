# Gate 09 execution and evidence

The primary campaign evaluates frozen PACT on the preregistered b14/b15/b17/b18 cohort, with B0–B5 under a common implementation backend. The two base families are b14 and b15; the related compositions supply scaling evidence.

- [Preregistration and frozen file hashes](../results/pact_gate9_large_scale_unseen_20261005/benchmark_preregistration.json)
- [Competitive definitions and fixed numerical/runtime configuration](../results/pact_gate09_open_source_20261005/manifests/competitive_method_definitions.json)
- [Completed b14 comparison, including every alternative and baseline](../results/pact_gate09_open_source_20261005/final/b14_opt/report.md)
- [Completed b15 comparison, including all mixed tradeoffs](../results/pact_gate09_open_source_20261005/final/b15_opt/report.md)
- [Terminal campaign A–N report and complete cohort table](../results/pact_gate09_open_source_20261005/final/campaign/report.md)
- [Focused tests and final read-only qualification](../results/pact_gate09_open_source_20261005/publication/final_qualification/qualification.json)
- [Qualified generic FAN repairs and regressions](../results/pact_gate09_open_source_20261005/dependency_repairs/FAN_ATPG/compound_reporter_qualification.json)

The scientific cohort is terminal: b14 and b15 each qualified all six baselines and three preselected PACT candidates. Neither primary dominates or is dominated by any baseline across routed scan WL, E, H4 and H8. b14 improves all three activity coordinates versus B3T with +0.044% scan WL; b15 trades +1.336% scan WL and +2.618% H4 for −1.267% E and −1.683% H8 versus B2. The competitive classification is `PACT_GATE09_MIXED_GENERALIZATION`; generalization remains admission-limited.

b17 passed source/mapped equivalence and capacity admission but ATPG timed out at the frozen 900-second limit. Placement and PACT search never started. b18 was deferred by the fixed-order stop policy; it is not a source failure or PACT loss. The [precise admission diagnosis](../results/pact_gate09_open_source_20261005/admission_diagnostics/b17_opt.json) binds the source, capacity, preparation and timeout evidence. This primary campaign was not extended or rerun.

## Stages

`pact_gate09_source_admit.py` checks the pinned source, BENCH/BLIF all-state next-state equivalence, mapped all-state equivalence and FF inventory. Its generic library adapter rejects actual use of the known unmodeled library cell.

`pact_gate09_cohort_reference_registered.py` delegates preparation and physical references to the preserved reference harness. The prospective registration adapter binds a prior failed preparation only when one exists. The qualified FAN repair, mapped source, fixed placement policy, clock, seed, endpoints and backend remain common.

`pact_gate09_competitor_measure.py` prepares and measures admitted architectures through the frozen CPU exact evaluator. Full trace completion and every FF-Q/cycle crosscheck are required.

`pact_gate09_campaign.py` freezes definitions, generates one B4 and one B5 architecture, routes registered architectures, builds reference-only PACT input, and runs the fixed search. Each epsilon loop has 900 seconds; the search worker ceiling is 7200 seconds. The sole budget bridge changes the legacy seconds expression and its receipt text to the existing preregistered budget. Exact mutations and independent winner replays are reported separately from final routed-netlist replays.

`pact_gate09_finish_design.py` freezes at most three distinct candidates before routing and exact measurement, then writes a complete per-design comparison. The balanced primary candidate remains primary after qualification. Failed outcomes and alternative candidates remain in the results.

`pact_gate09_input_recovery.py` separates prospective cold input into a fresh `PACT_primary` child beneath the source-preparation directory. It rejects existing primary-input/search artifacts, preserves the original failed receipt and runs the original complete input validation before search. Its continuation reuses all completed b15 baseline results and retains the fixed cohort order.

`pact_gate09_report.py` computes four-objective Pareto relationships at relative tolerance 1e-10. Timing, DRC, topology and workload/exact correctness remain qualification gates. Its A–N report includes control and heuristic contrasts without collapsing the comparison into a scalar score.

`pact_gate09_campaign_report.py --ledger PATH --output FRESH_DIRECTORY` consumes the explicitly selected terminal cohort ledger and retains held/deferred designs as unexecuted rows. The original and continuation ledgers remain separately preserved. `pact_gate09_validate.py` performs the final read-only hash, receipt, historical-preservation and tracked-bulk audit.

## Preserving interruptions

Existing outcome paths are immutable. The initial b15 registration failure occurred before ATPG or placement launched. Its dedicated continuation reused the qualified source; the later capacity continuation requires the identical FAN binary/revision, source, patterns, placement and preparation receipt. A changed backend or workload is rejected. Capacity remains 20 GiB scratch plus the registered per-design margin, with the original 25 GiB minimum retained.

The subsequent b15 input-directory collision also occurred before search. The current explicit continuation ledger is `cohort_execution_input_namespaced.json`; its predecessor ledgers remain preserved. The complete production audit is `dependency_probes/input_namespace_production_qualification_v2.json`, which adds the artifact binding list omitted by the preserved first audit record.

The FAN construction defects were published as [upstream issue #5](https://github.com/NTU-LaDS-II/FAN_ATPG/issues/5) after the original connector returned 403. The [submission receipt](../results/pact_gate09_open_source_20261005/publication/FAN_upstream_issue.json) binds the public body and visible screenshot. The separate fault-identity reporting defect is [issue #6](https://github.com/NTU-LaDS-II/FAN_ATPG/issues/6), with its own [submission receipt](../results/pact_gate09_open_source_20261005/publication/FAN_reporter_upstream_issue.json). The original failed attempt and previously qualified reports remain unchanged.

The public descriptions were subsequently simplified at the user's request: displayed commit hashes became labeled upstream-source links, and local artifact-preservation wording was removed. Reproducer paths remain relative to the upstream repository. The original submissions remain evidence; the [construction revision](../results/pact_gate09_open_source_20261005/publication/FAN_upstream_issue_revision.json) and [reporter revision](../results/pact_gate09_open_source_20261005/publication/FAN_reporter_upstream_issue_revision.json) bind the revised bodies and screenshots.

Raw route, extraction, simulation and complete trace evidence stays on the experiment drives. Compact receipts, architectures, selection records, reports and execution-source snapshots are versioned. The storage receipts record verified cache copies, rehashes, duplicate removal and retained original-path aliases.

Scientific execution uses the recorded Linux environment with `PYTHONPATH=.optimizer-deps:src:scripts`. Publication integration is performed after scientific completion; its record distinguishes the sealed execution versions from later repository compatibility changes. Reproduction uses the recorded execution commit and input/tool hashes.

The scientific checkout is sealed at `e8c2f5da298f073c231b5798561ffadce6355ec2`. Main's two receipt/output-path portability changes were integrated afterward, with the original execution sources archived and the remaining 282 frozen files rehashed unchanged. Thirteen compatibility tests and all Gate-09 module imports passed. The [integration resolution](../results/pact_gate09_open_source_20261005/publication/integration_qualification/resolution.json) preserves the initial audit's false flag for five CRLF README files and verifies that their exact bytes still match the original historical manifest. No scientific result was modified or rerun.
