# Reproduction and artifact index

This directory is a new experiment. Never rerun the Phase-2C-R continuation or
modify results/phase2c_repair. Seed-11 results and Attempt 1 are immutable inputs.

The one-time execution order is:

1. `scripts/phase2crm_audit.py`: verify the checkpoint and inventory all five seeds.
2. `scripts/phase2crm_register.py`: check exact-order route reuse; freeze the balanced contract and route budget.
3. `scripts/phase2crm_execute.py graphs`: export placed-only graphs with the repaired endpoint exporter.
4. `scripts/phase2crm_execute.py campaign`: at most 20 new routes and four archive-only extractions; two workers.
5. `scripts/phase2crm_execute.py focused` and `regression`: isolated test logs and XML.
6. `scripts/phase2crm_finalize.py freeze`: hash the execution sources before scoring.
7. `scripts/phase2crm_validate.py topology`: retain every repaired assertion, parameterizing only the seed selector and evidence paths.
8. `scripts/phase2crm_validate.py measure`: exact frozen predictor and packed scorer; targets are labels only.
9. `scripts/phase2crm_report.py`: frozen statistics, all-pair deltas, sensitivity analyses, five PNG/PDF figures and final report.
10. `scripts/phase2crm_finalize.py finalize`: verify frozen data and create the final complete SHA256 manifest.

Runtime: Ubuntu-24.04 WSL, `/root/pact-deps/pact-venv/bin/python`, with
`PYTHONDONTWRITEBYTECODE=1`, `OPENBLAS_NUM_THREADS=1` and
`PYTHONPATH=src:/mnt/d/PACT_EXPERIMENTS/cache/phase2a_python`.
OpenROAD export/extraction uses the same installed binary and frozen Nangate45 library.
Use commands.json and raw/**/execution.json for exact commands and timings.
Completed files are not an invitation to rerun physical work; registration,
logs, source freeze and topology/measurement stages refuse replacement.

The original historical Phase-2C results remain stopped for the legacy bug.
This experiment uses the separately qualified repaired implementation unchanged.

Key artifacts:
- SEED_INVENTORY.md / seed_inventory.json: exact usable data and upstream hashes.
- MULTISEED_CONTRACT.md / multiseed_contract.json / freeze.json: pre-outcome choices.
- ROUTE_BUDGET.md: full-campaign cost and balanced subset justification.
- coordinate_replica_audit.json: actual FF-coordinate differences between all selected seed pairs.
- topology_audit.json / ownership/: scan/FF/geometry/electrical ownership witnesses.
- per_architecture_results.csv: raw predictor/target scores and average-tie ranks.
- per_seed_results.csv: raw Spearman/Kendall/Pearson, exact pair counts and gates.
- pair_direction_results.csv / pair_consistency.json: exact pairs, signed deltas, percentages, ties, reversals and descriptive materiality.
- results.json: primary classification and mandatory leave-seed-11-out conclusion.
- sensitivity_analysis.json: descriptive deletions; none change the primary gates.
- figures/: five reproducible publication-oriented panels, each as PNG and PDF.
- tests.json / commands.json / result_provenance.json / manifest.sha256: execution and preservation audit.

The physical seeds are coordinate perturbation/legalization realizations sharing
one global placement per design. They do not establish independent global-placer
or broader technology/design/optimization/power generalization.

Audit-summary clarification: after topology, clarify_topology_scope.py preserves the raw audit and marks the inherited legacy_weights_exact summary field as not applicable to new seeds. This field assumed a seed-11 archive caller. Every reused topology assertion remains unchanged and passed; no predictor, scoring, threshold or target change was made.


After report generation, finalize_presentation.py corrects the exact family-stability tie in the prose and produces the readable seed-comparison panel. It changes no scientific values or classification. presentation_audit.json records this review.
