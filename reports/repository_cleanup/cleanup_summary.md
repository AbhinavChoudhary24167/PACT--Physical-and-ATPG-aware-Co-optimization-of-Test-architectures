# Repository cleanup final report

**PACT_REPOSITORY_CLEANUP_PARTIAL**: current tracked source/data/documentation cleanup is verified; automatic approval review prevented removal of inventoried ignored local dependency/environment copies. History cleanup is separately recommended and was not performed.

| Measurement | Before | After | Reduction |
|---|---|---|---|
| Tracked checkout bytes | 2,297,638,437 | 75,341,088 | 96.72% |
| Tracked files | 15,509 | 1,045 | 93.26% |
| Tracked text lines (all data/docs/source) | 27,885,967 | 2,639,272 | 90.54% |
| Source/test lines | 44,950 | 30,424 | 32.32% |
| Visible checkout bytes (without .git) | 13,249,306,671 | 3,388,457,868 | 74.43% |
| .git logical bytes | 1,399,485,073 | 1,398,870,744 | 0.04% |
| Total visible bytes | 14,648,791,744 | 4,787,328,612 | 67.32% |

Bytes are logical lengths, not allocated disk usage. The before checkout walk followed one external Windows junction; after it was safely unlinked, its external target still exists. Local checkout reduction must not be read as freed disk space. Tracked size/file/text reductions are separately meaningful. Snapshot values include cleanup audit receipts; source/test LOC counts src/scripts/tests only. New DEF/V, compact active diagnosis, evidence exports and documentation are included. The snapshot uses the staged final audit paths after the source commit, before the small final report commit.

## Largest remaining tracked files

| Path | Bytes | Text lines |
|---|---|---|
| results/pact_candidate_stateful/s15850/baseline_geometry.json | 5979142 | 315971 |
| results/pact_candidate_sensitive/s15850/topology.json | 3750334 | 219656 |
| results/pact_candidate_stateful/s9234/baseline_geometry.json | 3118804 | 165881 |
| reports/repository_cleanup/file_classification.tsv | 2857809 | 15510 |
| results/pact_candidate_stateful/s5378/prior_corpus.json.gz | 2758109 | 0 |
| results/pact_candidate_stateful/s5378/baseline_geometry.json | 2334278 | 121738 |
| results/pact_candidate_stateful/s9234/prior_corpus.json.gz | 2009717 | 0 |
| results/pact_candidate_sensitive/s9234/topology.json | 1957424 | 115277 |
| results/pact_candidate_sensitive/s5378/topology.json | 1466854 | 84511 |
| results/pact_v2/s9234/evaluations.csv.gz | 1433102 | 0 |
| results/pact_v2/s5378/evaluations.csv.gz | 1385090 | 0 |
| results/pact_oss_benchmark/topology_recovery_20261004/stage_a/routes/s15850.json | 1370510 | 39742 |
| reports/repository_cleanup/pre_cleanup_tracked_inventory.tsv | 1315517 | 15510 |
| results/pact_candidate_sensitive/s5378/evaluations.csv.gz | 1295814 | 0 |
| results/pact_candidate_stateful/s15850/prior_corpus.json.gz | 1053449 | 0 |
| results/pact_candidate_sensitive/s15850/physical_model.json | 1030968 | 64224 |
| results/phase2c_repair/freeze.json | 982450 | 43765 |
| artifacts/raw/phase0b/placements/s15850/s11/placed.def | 962818 | 13873 |
| reports/working_solver/final/s15850_300/result.json | 902641 | 39571 |
| reports/physical_effect/s15850/J50/net_mapping.json | 840043 | 46788 |

## Changes and retained implementation

14,533 original paths were removed. [Deletion summary](deletion_summary.md) and [per-file decisions](file_classification.tsv) give exact categories/reasons. Core solver, stateful/Stage-B evaluation, scan/identity/activity/workload/integration/OpenDB adapters and essential regressions remain. Minimal original workloads, mapped designs, hash-bound placed/rewired fixtures, selected orders, current model inputs, full measured summaries and exact baseline repair/source provenance remain.

Canonical documentation: README.md; docs/architecture.md, methodology.md, installation.md, usage.md, experiments.md, benchmarks.md, reproducibility.md, development.md, research_status.md, history.md and stage_b_method.md; CITATION.cff. Phase diaries and chat/planning documents were consolidated. Paths/tool environments are configurable. Source filenames remain stable except retired implementations; exact reused selection/statistics helpers retain their mathematics.

Scientific state: Stage A is physically/external-benchmark complete in saved records (19/19 selected qualified, 27/30 indexed qualified), followed by Stage B with nine qualified selections. The program remains in progress: several hotspot proxy improvements fail to transfer, original-front dominance remains, and complete detected-fault identity equivalence is unresolved. No new real architecture search or physical campaign was performed.

Build/tests/smoke: [exact commands, outcomes and all gates](post_cleanup_validation.md). Editable build and pip check passed; 382 tests pass/one external-evidence skip; synthetic optimizer/topology pass; real s5378 load/unload replay and handoff pass with zero mismatches, while full physical/FAN status remains BLOCKED. Three saved Stage-B bundles and 18 architectures replay against independent scores; retained hashes and all neutral Stage-A export columns are checked. Fresh archive excludes local generated environments/dependencies.

Git-history recommendation: **STRONGLY_RECOMMENDED**. 2,006,773,618 uncompressed historical blob bytes are overwhelmingly experimental/generated material. Local pre-cleanup historical churn is 28,534,631 additions/627,420 deletions; deleting HEAD files does not erase it or fix GitHub code-frequency automatically. [History rewrite plan](history_rewrite_plan.md) describes scoped filtering, backup/reproduction prerequisites and fork/clone/hash/force-push consequences. Main/public history and remote refs were not rewritten or pushed.

Pending local cleanup: 3,110,762,996 logical bytes in seven named ignored dependency/cache/environment directories. See [exact pending inventory](local_cleanup_pending.json). Automatic approval review rejected recursive deletion because the scope could include useful untracked scripts/user work. A separate escalation review for additional WSL input verification exhausted its quota. All unaffected cleanup/validation work was completed without bypassing either rejection. Active untracked diagnostic/contribution output was preserved locally; only compact current evidence/source was committed.
