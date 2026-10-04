# Deletion and retention summary

Every originally indexed path is classified in [file_classification.tsv](file_classification.tsv); actions include replacements by canonical documents. Current additions are inputs, source, docs, and cleanup receipts.

| Initial class | Paths |
|---|---|
| A | 74 |
| B | 236 |
| C | 663 |
| D | 29 |
| E | 14507 |

14,533 original paths are absent from the cleaned checkout. Major removed categories:

- Historical artifacts/derived/raw campaigns: repeated candidate/proxy dumps, OpenDBs, SPEF, generated route netlists, intermediate metric/debug/qualification output.
- results/phase2c*, phase2d and old experiment workspaces: raw routes, simulator output, huge initial_worktree.patch and repeated physical/source snapshots; repaired graphs and required freeze remain.
- reports/optimizer_v*, obsolete milestone diaries, duplicated figures and full working-solver/implementation route trees; canonical final selections, integration inputs and small physical summaries remain.
- Copied OpenROAD/OpenSTA/test source trees in tracked benchmark experiments; exact source pins, patches and qualification manifests remain.
- Superseded H_eff8 optimizer v1/v2/v2.1/v2.2/v2.3 modules/runners/tests; obsolete full-campaign funnel tests and launch/report code in shared helper files.
- Duplicate freeze receipt and superseded cleanup/AI planning/status documents; scientific conclusions consolidated into canonical docs.

Core retained: src/pact optimizer (exact incremental/reference), candidate-stateful geometry/logic, Stage-B lanes and portable loader; scan/topology/identity models; pattern/activity/replay and fault integration; OpenDB/ORFS adapters; numerical/structural regression suite; frozen configuration/provenance; minimal real DEF/V and FAN fixtures; original selections, positive and negative measured outcomes, hash manifests and compact diagnostic evidence.

Ignored local dependencies/caches totaling 3,110,762,996 logical bytes remain after automatic approval review rejected their recursive removal. See [local_cleanup_pending.json](local_cleanup_pending.json). The external target of the removed Windows junction was untouched. Active untracked diagnostic/contribution work was preserved locally and excluded from Git. The fresh source archive contains none of these workspaces.

New paths are classified separately in [added_files_classification.tsv](added_files_classification.tsv).
