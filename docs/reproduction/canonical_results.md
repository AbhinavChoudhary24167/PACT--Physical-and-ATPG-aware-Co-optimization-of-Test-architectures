# Canonical reproduction

```sh
python scripts/verify_reproducibility.py
```

This verifies 674 original/export bindings, Stage-A table exports and 18 Stage-B starts/selections against independent reference and incremental scores. It does not launch ATPG/EDA/search or reconstruct routed measurements from predictor values.

| Result | Exact evidence / protocol |
|---|---|
| Stage A | `results/stage_a/`, `results/pact_oss_benchmark/topology_recovery_20261004/completion.json`, `benchmarks/manifests/` |
| Stage B | `results/pact_stage_b/REPORT.md`, `candidate_results.csv`, `inputs/*.json.gz`, `architectures/`; [method](../stage_b_method.md) |
| End-to-end gate | `results/pact_end_to_end_20261004/REPORT.md`, `final_verification.json`, correctness/repair records; [scope](../end_to_end_qualification.md) |
| Prospective / CPU | [Cold start](../pact_cold_start.md), [CPU contracts](../cpu_scalability.md), corresponding `results/pact_cold_start_unseen_20261004/` and `results/pact_cpu_scalability_20261005/` |
| Gate 09 | `results/pact_gate09_open_source_20261005/final/campaign/report.md`, b14/b15 tables, execution/admission ledgers and frozen competitive definitions; [protocol](../gate09_open_source_campaign.md) |
| Gate 10A | `reports/gate10a/preregistration.md`, `protocol.json`, `selected_architectures.json`, `tool_provenance.json`, `artifact_reuse_manifest.json`, `final_comparison.csv`, `decision.json`, `machine_summary.json` |

Full physical reproduction needs frozen ODB/SDC, workload/FF maps/orders, technology hashes and exact tool binary/submodule/patch identities. [Archive manifest](../../archives/MANIFEST.csv) indexes complete raw campaigns. Verify compressed and extracted-member hashes and restore their relative layouts before use. Relocation does not relabel a frozen physical realization.

Originally tracked historical inputs can be recovered from pre-cleanup revision `f2569d498cd5f26a88c4954ec163498eb3cf7d91`; some outputs existed only externally. No public private-data URL is promised. Source pins alone do not recreate a frozen placement. Existing normalization ledgers, scientific hashes, values and negative outcomes remain unchanged. Gate 10A reused Gate 09 artifacts; maintenance does not repeat measurements.
