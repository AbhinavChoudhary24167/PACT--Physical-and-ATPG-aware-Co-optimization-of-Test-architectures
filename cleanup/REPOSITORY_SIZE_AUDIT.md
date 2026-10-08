# Repository size audit

Snapshot commit: `8b0875c402fb30bdd1d987ff4ac874fcc2d3cbbb`.

| Metric | Before bytes | After bytes | Reduction bytes |
|---|---:|---:|---:|
| Tracked working-file bytes | 257,853,505 | 259,338,472 | -1,484,967 |
| Tracked Git blob bytes | 257,811,281 | 259,287,902 | -1,476,621 |
| Tracked file count | 4,005 | 4,041 | -36 |

Working tree excluding `.git`: 3,816,984,431 bytes; ignored: 3,557,645,959; untracked: 0; `.git`: 1,094,521,254. Final report commits add compact documentation beyond this snapshot.

Large tracked artifacts remain because replay/provenance binds their exact bytes. No compiled objects, executables or dependency archives were found tracked.

| Bytes | Tracked path |
|---:|---|
| 5,979,142 | `results/pact_candidate_stateful/s15850/baseline_geometry.json` |
| 3,750,201 | `results/pact_candidate_sensitive/s15850/topology.json` |
| 3,118,804 | `results/pact_candidate_stateful/s9234/baseline_geometry.json` |
| 2,842,299 | `reports/repository_cleanup/file_classification.tsv` |
| 2,758,109 | `results/pact_candidate_stateful/s5378/prior_corpus.json.gz` |
| 2,334,278 | `results/pact_candidate_stateful/s5378/baseline_geometry.json` |
| 2,299,012 | `results/pact_end_to_end_20261004/correctness/s15850/B2/fan/export.json` |
| 2,299,012 | `results/pact_end_to_end_20261004/correctness/s15850/original_workload/export.json` |
| 2,299,012 | `results/pact_end_to_end_20261004/correctness/s15850/s15850_C1/fan/export.json` |
| 2,299,012 | `results/pact_end_to_end_20261004/correctness/s15850/s15850_C2/fan/export.json` |
| 2,299,012 | `results/pact_end_to_end_20261004/correctness/s15850/s15850_C3/fan/export.json` |
| 2,299,012 | `results/pact_end_to_end_20261004/upstream_repair/s15850/repaired/export.json` |
| 2,009,717 | `results/pact_candidate_stateful/s9234/prior_corpus.json.gz` |
| 1,957,291 | `results/pact_candidate_sensitive/s9234/topology.json` |
| 1,544,263 | `results/pact_cold_start_unseen_20261004/physical/s35932/physical_results.json` |
| 1,466,721 | `results/pact_candidate_sensitive/s5378/topology.json` |
| 1,439,987 | `results/pact_large_unseen_gate9_20261005/physical/s38417/physical_results.json` |
| 1,433,102 | `results/pact_v2/s9234/evaluations.csv.gz` |
| 1,417,796 | `results/pact_gate09_open_source_20261005/00_preflight/admission.json` |
| 1,385,090 | `results/pact_v2/s5378/evaluations.csv.gz` |
| 1,366,922 | `results/pact_oss_benchmark/topology_recovery_20261004/stage_a/routes/s15850.json` |
| 1,300,007 | `reports/repository_cleanup/pre_cleanup_tracked_inventory.tsv` |
| 1,295,814 | `results/pact_candidate_sensitive/s5378/evaluations.csv.gz` |
| 1,288,811 | `results/pact_end_to_end_20261004/correctness/s15850/s15850_C2/fan/stdout.txt` |
| 1,288,810 | `results/pact_end_to_end_20261004/correctness/s15850/s15850_C3/fan/stdout.txt` |
| 1,288,808 | `results/pact_end_to_end_20261004/correctness/s15850/s15850_C1/fan/stdout.txt` |
| 1,288,795 | `results/pact_end_to_end_20261004/correctness/s15850/B2/fan/stdout.txt` |
| 1,288,773 | `results/pact_end_to_end_20261004/correctness/s15850/original_workload/stdout.txt` |
| 1,288,772 | `results/pact_end_to_end_20261004/upstream_repair/s15850/repaired/stdout.txt` |
| 1,272,184 | `cleanup/pact_storage_inventory.json` |
