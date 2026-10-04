# Reproducibility and retention

## Clean-checkout verification

Stage-B bundles contain exact architectures, load/response arrays, topology, primary inputs, baseline C/physical arrays and labelled B2/B3T/P0 starts. Saved selected orders and measured CSVs preserve the complete current comparison, including negative/dominated outcomes. `python scripts/verify_reproducibility.py` independently replays starts/selections, validates topology and checks retained original input hashes. It does not reconstruct routed measurements from predictor values.

`scripts/fetch_data.py` fetches known pinned ORFS/FAN sources without inventing artifact URLs. Minimum retained inputs include original FAN patterns, mapped netlists/identity maps, placed DEFs, B0/P/A/J50/T orders, repaired graphs and small structural fixtures. Current physical configuration/adapters generate outputs under explicit scratch paths.

## Exact physical reproduction

Exact reruns also require frozen placed ODB/SDC, technology libraries, common backend and B3T build/submodule bindings. Their hashes remain in protocol/method/repair manifests and completion receipts.

Public receipt metadata uses `repo://`, `dep://` and `run://` aliases for repository, dependency and experiment roots. Readers resolve these using the checkout and `PACT_DEPENDENCY_ROOT` / individual dependency overrides / `PACT_EXPERIMENT_ROOT`. Historical Python environments and maintenance archives use descriptive `env://`, `archive://` and `maintenance://` aliases and are not distributed inputs. Standard container mount paths describe the adapter contract, not a personal machine.

[The normalization ledger](../reports/repository_cleanup/path_metadata_normalization.json) records original/public byte identities for path and hostname metadata exports. Numbers, architecture identities, source/tool revisions and embedded historical hashes are unchanged. Embedded hash bindings describe the original receipts; recover their original bytes from the ledger's `original_revision`. The verification script checks both unchanged original inputs and the audited public exports. Publication did not rerun or relabel scientific measurements.

Full ODB/VCD/DEF/SPEF and compiled simulation trees are excluded. No public download location for private physical records is established. Obtain hash-bound inputs from the experiment custodian, or recover tracked originals from pre-cleanup revision `f2569d498cd5f26a88c4954ec163498eb3cf7d91` before an approved history rewrite. Some outputs existed only externally; Git recovery cannot supply them. A newly generated placement is a new physical realization unless hashes match.

`git show f2569d498cd5f26a88c4954ec163498eb3cf7d91:PATH > recovered-file` retrieves a tracked original. Validate its identity/checksum against the inventories and manifests. Dependency checkout alone does not provide frozen physical inputs. Full physical reruns were not launched during maintenance.

## Artifact policy

Retain source, configuration/schemas, essential fixtures, small inputs, exact selected orders, final metrics, hashes and conclusions. Delete build trees, copied snapshots, repeated logs/databases and intermediates after documenting relevant failures. Do not discard results because they disagree with preferred conclusions.

Original retained input hashes are in `reports/repository_cleanup/retained_evidence_sha256.json`; the new export has a separate checksum manifest. Original paths/classifications remain auditable. External Windows junction targets were untouched; needed small inputs were copied into real directories before unlinking. No public history rewrite or remote force-push occurred.
