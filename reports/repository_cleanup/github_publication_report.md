# GitHub publication report

PACT_GITHUB_PUBLICATION_COMPLETE_HISTORY_CLEANUP_PENDING

## Git state and publication

- Local starting SHA: `39ab058d7b7fcaa8762c2c469a37cf104557286a` on `maintenance/repository-cleanup`.
- Remote starting SHA: `6a517f058b23d0520d83d2746de82809890b16ee` on `origin/main`.
- Validated published payload SHA: `87a1767aee729b4647103748c97319a6409d931e`.
- Final local SHA: the `main` commit containing this report (`git rev-parse HEAD`).
- Final origin/main SHA: the same report commit (`git rev-parse origin/main`). The final verification checks equality after pushing this documentation receipt. A commit cannot embed its own SHA; the tested payload is pinned explicitly above.
- Route: direct normal fast-forward pushes to canonical GitHub `main`; no PR required, no force push.
- Reconciliation: 19 local-only / two remote-only commits at start; merge `79a2130f` preserves PR #1's method/results and its merge. The current portable-input method description and retained contributor-table reference resolve the two documentation conflicts.
- Publication commits: `f8ec9997` prepares the public entry point and audited metadata; `87a1767a` includes the one historical README initially omitted from staging. The actual clone was updated before validation. The final receipt adds only this report and validation JSON.
- Local checkout is on `main`; no generated outputs are staged.

See [reconciliation](publication_reconciliation.md) and [machine-readable validation](github_publication_validation.json).

## Incorporated and excluded changes

Published all four validated cleanup commits, current source/test/build/configuration work, canonical documentation, exact portable Stage-B inputs/orders, minimal physical/workload fixtures, compact comparison/qualification evidence and provenance. The README now leads with purpose, runnable quick start, measured status, navigation and limitations. Added one [synthetic example](../../examples/synthetic/README.md). GitHub's About description now describes the implemented research software; the rendered landing page and public API were checked.

Publication normalizes 209 receipt/audit path or hostname metadata files. Numeric values, architecture identities, source/tool revisions and original embedded hash bindings are unchanged. [Original/public SHA ledger](path_metadata_normalization.json) supplies exact export identities; original bytes remain recoverable at its pinned pre-publication revision. The reader resolves repository/dependency/experiment aliases. Historical receipt sealers still require their frozen source/input revisions. No measurements were regenerated.

KEEP_LOCAL / IGNORE: local Python environments, numerical/tool caches, OpenROAD/ORFS/FAN installations, PDKs, routing/simulation work directories, raw H8 and fault-identity diagnostics, upstream CI/review workspaces and scratch outputs. These support ongoing work and are not a repository defect. No recursive deletion occurred in publication.

## Canonical documentation

[README](../../README.md), [architecture](../../docs/architecture.md), [methodology](../../docs/methodology.md), [installation](../../docs/installation.md), [usage](../../docs/usage.md), [experiments](../../docs/experiments.md), [benchmarks](../../docs/benchmarks.md), [reproducibility](../../docs/reproducibility.md), [development](../../docs/development.md), [research status](../../docs/research_status.md), [history](../../docs/history.md), [Stage-B method](../../docs/stage_b_method.md) and [CITATION.cff](../../CITATION.cff). Citation and LICENSE both specify MIT for PACT; no DOI/publication metadata was invented. External assets retain attribution. No unsupported badges were added.

## Functional validation

Exact commands run from each repository root in its installed environment:

```sh
python -m pip install -e '.[optimizer,dev]'
python -m pip check
python -c "import pact"
pact --help
pact-optimize --help
pact-integrate --help
python scripts/pact_stage_b_search.py --help
python -m pytest -q --junitxml=scratch/publication_tests.xml
pact-optimize --synthetic 64 --chains 2 --time-budget 1 --output scratch/publication_smoke
pact validate-scan --architecture scratch/publication_smoke/optimized.architecture.json
pact-integrate --design s5378 --optimizer-run reports/working_solver/final/s5378 --output scratch/publication_integration
python scripts/verify_reproducibility.py
```

Fresh-clone output namespaces were `scratch/fresh_tests.xml`, `scratch/example` and `scratch/fresh_integration`. The fresh import additionally asserts that `pact.__file__` belongs to the clone. Separate ignored NumPy/Numba/Matplotlib caches were used; no development source path was injected.

| Gate | Cleaned local | Actual GitHub clone |
|---|---|---|
| Editable installation / dependency check | PASS | PASS in new empty Python 3.12.5 environment |
| Import / installed CLI discovery and help | PASS, all three public commands | PASS, imports originate in clone |
| Essential suite | 382 passed, one skip, zero failures/errors; 45.88 s console / 45.453 s JUnit | 382 passed, one skip, zero failures/errors; 54.38 s console / 53.929 s JUnit |
| Synthetic optimizer | WORKING_SOLVER, 64 FF, K=2, 1.0089 s, 1,818 evaluations | WORKING_SOLVER, 64 FF, K=2, 1.003417 s, 1,880 evaluations |
| Architecture reload / topology | PASS | PASS |
| Saved s5378 integration / ATPG workload | 117 patterns, 20,943 FF states, zero mismatches; permutation/load/unload/export PASS | Same PASS |
| Retained Stage-B evaluation | All three bundles; nine starts + nine selected orders replay against full/reference and incremental scores | Same 18 replay PASS |
| Retained evidence | 674 bindings: 472 original hashes + 202 audited portable metadata exports; all 209 exports checked | Same PASS |

The one skip requires an external full historical Liberty/architecture evidence set. It is unchanged from cleanup. Configuration loading, workload parsing, fixed-capacity Stage-B feasibility and corruption/rollback guards remain in the essential suite. No Stage-B search or new physical campaign was launched.

**EXTERNAL_ENVIRONMENT_REQUIRED:** fresh OpenROAD physical implementation and FAN fault-set replay were not executed. Native doctor reports missing EDA dependencies. The integration CLI correctly retains full-flow `BLOCKED` when those stages are not run; independent transport replay passed. Stored coverage/count agreement does not prove complete detected-fault identity equivalence.

## Actual GitHub clone and presentation

```sh
git clone --depth 1 --branch main https://github.com/AbhinavChoudhary24167/PACT--Physical-and-ATPG-aware-Co-optimization-of-Test-architectures.git FRESH_CLONE
cd FRESH_CLONE
python -m venv FRESH_ENV
# Activate FRESH_ENV; install and run the commands above.
```

The actual run used a separate clone and an environment outside it. Git downloaded all checkout files; no files were copied from the development checkout. A shallow clone intentionally verifies the public current tree without downloading historical bloat. Expected source/docs/fixtures exist; deleted campaigns, environments and copied build/dependency trees are absent. Tracked and untracked status is clean after validation; outputs are ignored.

At the tested payload, all 33 README/docs/example internal file links and all 66 tracked Markdown internal file links resolve. Added receipt links are checked before the final push. Case-sensitive canonical links were checked. All 271 maintained Python files parse as Python 3.11; absolute package imports resolve to present modules. Tracked text and gzip payload scans found no personal absolute paths, credential patterns or copied chat/prompt artifacts. Standard container mounts and generic legacy relocation patterns are compatibility contracts; public author URLs are attribution.

Stage-A tables independently show 30 indexed / 27 qualified and 19 selected / 19 qualified, including seven P0 selections. Stage-B tables show nine qualified selections and nine routed budget passes. Hotspot transfer failures, original-front dominance, coverage/capacitance limits, fault-identity uncertainty and external input requirements remain explicit in current docs.

## Repository health and final gates

- Tracked files after receipt: 1,050.
- Tracked Git blob bytes after receipt: 75,252,281 (~75.25 MB); generated scratch, ignored dependencies and Git history excluded.
- Source/test line count: approximately 30,444 across tracked `src/`, `scripts/`, `tests/`.
- Largest retained files: s15850 baseline geometry 5,979,142 bytes; s15850 candidate topology 3,750,201; s9234 baseline geometry 3,118,804; cleanup classification audit 2,842,299; s5378 compressed prior corpus 2,758,109. They support current inputs/provenance/auditability.
- No compiled/build/dependency tree or ODB/SPEF/GDS/VCD output is tracked. Minimal DEF/V/FAN fixtures are deliberate inputs.
- G1/G2: cleanup ancestry published to main; final local/remote equality and clean status verified after receipt push.
- G3–G8/G10–G16: installation, import, public CLI, tests, synthetic/topology, retained Stage-B evidence, commands/links, tracked-file/privacy/fresh-clone and preserved-core gates PASS.
- G9: independent ATPG integration replay PASS; full physical/FAN stages EXTERNAL_ENVIRONMENT_REQUIRED, not relabeled as pass.

## History status

CURRENT_HEAD_CLEAN

HISTORY_REWRITE_PENDING

The earlier history audit found approximately 2 GB of unique historical blob content. Normal publication preserves those objects, historical source/evidence commits and old receipt paths. No filter-repo, BFG, rebase compaction or force push occurred. History cleanup requires separate explicit authorization. Retained current research data is justified; ignored local installations and diagnostics remain useful.
