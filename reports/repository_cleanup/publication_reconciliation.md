# Publication reconciliation

Snapshot: 4 October 2026, before publication edits.

- Local branch: `maintenance/repository-cleanup`.
- Local starting HEAD: `39ab058d7b7fcaa8762c2c469a37cf104557286a`.
- Fetched remote main: `6a517f058b23d0520d83d2746de82809890b16ee`.
- Merge base: `9d9103027918b1d4af2b209e6d36133ad82d4a4e`.
- Ahead: 19 commits; behind: 2 commits; histories diverged.
- Tracked modifications and untracked files at start: none.

Remote main contains PR #1's Stage-B method/results commit and its merge. Its source, tests and result tables match the maintained local versions. The two add/add conflicts were documentation: the local method page reflects newly distributed portable inputs, and the local report references the retained contributor table. Preserve those current descriptions and both parent histories through merge commit `79a2130f`.

## Classification and strategy

| Category | Decision |
|---|---|
| Current source, tests, documentation, configs, compact scientific evidence and cleanup commits | COMMIT / publish |
| Portable receipt metadata, public README/example and publication audit | COMMIT after validation |
| `.venv/`, `.optimizer-deps/`, tool installations under `external/` | KEEP_LOCAL, ignored |
| `.optimizer-cache/`, `.pytest_cache/`, Python/Numba caches, egg metadata and `scratch/` | IGNORE / KEEP_LOCAL |
| Fault-identity and H8 raw diagnostics; upstream CI/review workspaces | KEEP_LOCAL, ignored |
| Historical Git objects | KEEP; no rewrite or force push |
| Uncertain local material | KEEP_LOCAL; no recursive deletion in this task |

Merge remote history without discarding remote work, audit publication paths/credentials/links, validate installation and supported interfaces, and push the resulting descendant normally to `main`. If branch protection requires a PR, use that route. Validate an actual GitHub clone before final completion. Local ignored tools/PDKs/data are useful working material, not a public repository defect.

Metadata exports replace personal execution prefixes with documented portable aliases. Original numeric results, architecture identities, tool/source revisions and embedded historical hash bindings remain unchanged; original bytes remain in pre-publication Git history. The separate normalization ledger records original and public checksums. No scientific search or physical campaign is part of this publication.

A local `opensta420_round3_20261004/` tool-build/provenance capture appeared under the Verilog-alias contribution workspace during final publication. Its capture script, current tool-state JSON and build log are REVIEW / KEEP_LOCAL. A scoped `opensta*_round*/` ignore rule excludes this diagnostic class; no contents were deleted or published.
