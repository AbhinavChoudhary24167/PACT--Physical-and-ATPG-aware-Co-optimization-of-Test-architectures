# Final cleanup report

## Executive status

**PACT_CLEANUP_PARTIAL**. Verified archival and substantial storage reduction,
canonical validation and documentation overhaul are complete. Unreconciled tool
source copies/build fixtures and protected cache remnants remain. OpenROAD trees
differ in 1,786 entries; the ORFS content read stalled in WSL, so neither copy
was treated as redundant. The Windows
sandbox still fails setup; virtualization and WSL now work.

## Canonical repository

`C:\Users\Abhinav\OneDrive\Desktop\PACT\PACT`; branch `maintenance/repository-storage-documentation-overhaul`.
Starting commit `c59624176238a2c898b7239988ffa4f81a424936`; report snapshot `8b0875c402fb30bdd1d987ff4ac874fcc2d3cbbb`.
Remote: `git@github.com:wellitsabhinav/PACT--Physical-and-ATPG-aware-Co-optimization-of-Test-architectures.git`.
All reachable commits in the removed historical PACT copies are contained in
canonical refs. The branch retains the five pre-existing Gate10A commits beyond
public main plus this cleanup; no new research campaign was run.

## Storage before/after

| Metric | Before bytes | After bytes | Reduction bytes |
|---|---:|---:|---:|
| Total discovered PACT logical footprint | 79,787,584,213 | 37,334,369,374 | 42,453,214,839 |
| Canonical checkout, including local dependencies and .git | 5,048,281,751 | 4,911,505,685 | 136,776,066 |
| .git | 1,094,276,470 | 1,094,521,254 | -244,784 |
| Known archived raw experiment campaigns | 44,532,566,804 | 0 | 44,532,566,804 |
| Inactive build/scratch ext4 container | 17,179,869,184 | 0 | 17,179,869,184 |
| Compressed archive payloads | 0 | 19,971,445,743 | -19,971,445,743 |
| Historical PACT copies: archived members | 787,293,729 | 88 | 787,293,641 |
| C: PACT footprint | 6,713,905,782 | 5,992,482,961 | 721,422,821 |
| D: PACT footprint | 37,531,518,383 | 5,767,136,357 | 31,764,382,026 |
| E: PACT footprint | 0 | 19,980,643,970 | -19,980,643,970 |
| F: PACT footprint | 18,295,557,598 | 1,115,688,414 | 17,179,869,184 |
| WSL PACT dependencies and raw runs | 17,246,602,450 | 4,478,417,672 | 12,768,184,778 |

Files: **129,357 → 101,731**. Logical reduction: **42,453,214,839 bytes (53.21%)**.

22 verified archives: 62,499,729,717 original bytes → 19,971,445,743 payload bytes; ratio 3.1295:1. 6 historical trees had archived members removed. Quarantine retains 6,475,383 readable bytes plus inaccessible cache entries.

Numbers are measured logical file lengths, not allocated clusters or WSL host-disk reclamation. Windows read errors make discovery totals lower bounds. The unrelated 8,589,934,592-byte game cache is excluded on both sides. Linux dependency files are counted separately; distribution VHDX files are untouched. Archive receipts/index/log bytes are included in E: totals, while the archive-payload row excludes them. Canonical .git and tracked evidence are intentionally retained. Remaining build trees outside the audited inactive container are included in the full footprint. Snapshot timing and limits are in [machine summary](storage_after_summary.json).

| Drive | Free bytes before | Free bytes at snapshot | Change |
|---|---:|---:|---:|
| C: | 12,552,183,808 | 10,739,085,312 | -1,813,098,496 |
| D: | 35,730,161,664 | 60,689,543,168 | 24,959,381,504 |
| E: | 32,233,988,096 | 12,253,204,480 | -19,980,783,616 |
| F: | 21,089,730,560 | 38,231,851,008 | 17,142,120,448 |

Host free-space changes include concurrent unrelated work and are not claimed as PACT-attributable reclamation. No public Git history was rewritten.

## Files deleted

62,499,729,629 regular bytes of fully archived source members were removed from
recorded quarantine only after validation. This includes historical campaign
outputs, six old PACT copy snapshots, the inactive build container and Linux
routing runs. Original unique bytes remain losslessly recoverable from verified
archives. Two campaign-generated interrupted archives were also removed after
verified replacements existed. See [machine-readable actions](cleanup_actions.json).

## Files compressed

62,499,729,717 bytes → 19,971,445,743 bytes across 22 verified archives.
Source/platform libraries were excluded from Linux run archiving. Negative,
failed and timed-out outcomes are preserved. The image is exceptionally retained
because source reconciliation is incomplete, not as a routine build-cache policy.

## Duplicates removed

Six historical PACT trees had archived members removed. Commit-set superset proof
and exact snapshot recovery protect unique local modifications. Mappings and
exceptions are in [deduplication map](PACT_DEDUPLICATION_MAP.csv).

## Archives

[MANIFEST.csv](../archives/MANIFEST.csv) records names, categories, absolute paths,
original/compressed sizes, ratios, SHA256s and full member-manifest paths/hashes.
[Verification summary](../archives/verification.json) records complete stream
decompression, per-member hashes/counts/link checks and completed source actions.
Bulk payloads remain external on E:, outside public Git.

## Repository changes

Improved ignore/retention rules, exact patch byte attributes, archive indices,
upstream source exports and cleanup provenance. Existing source paths remain
stable. No source, script, test, config or package behavior changed.
Tracked size: 257,853,505 → 259,338,472
working-file bytes in the measured snapshot. Current receipt-bound evidence was
retained; Git history was not rewritten. See [repository audit](REPOSITORY_SIZE_AUDIT.md)
and [separate history recommendation](GIT_HISTORY_REWRITE_RECOMMENDATION.md).

## Documentation overhaul

README rewritten around actual implementation, metrics and scientific limits.
Architecture, physical/activity objectives, ATPG, search, environment, canonical
reproduction, history, negative findings, troubleshooting and upstream work now
have focused guides. CONTRIBUTING and CHANGELOG added; obsolete postmerge wording
clarified. The negative static-IR result remains explicit; thermal benefit is
not claimed. See [consistency audit](DOCUMENTATION_CONSISTENCY_AUDIT.md).

## GitHub status

Branch not yet pushed; PR creation follows this report commit

## Validation

Before and after quarantine: **578 passed, 1 skipped** in the Linux harness.
Three CLI help checks passed. The saved-input verifier passed all **674 evidence
bindings** (472 unchanged hashes, 202 audited portable exports) and **18 architecture
replays** across s5378/s9234/s15850. The documented 64-FF/two-chain, one-second
numerical quickstart and topology validation passed. Maintained configs,
pyproject and compact manifests parsed; imports and guide links passed.
Source/config diff from the starting commit is empty. Initial Windows collection
fails on Linux-specific `resource`/harness imports, so full harness validation is
documented and performed in WSL. No expensive historical experiment was rerun.

## Quarantine

The manifest records all 22 original/quarantine/recovery mappings. Readable
remaining quarantine bytes are recorded above; access-denied excluded cache
entries remain protected. The changed publication worktree `.git` pointer is
retained as administrative metadata. Uncertain source/debug trees remain at
their original locations. No uncertain material was permanently destroyed.

## Remaining risks

Windows OpenROAD/ORFS copies and source/build scratch require further source
reconciliation; the inactive build image has unreconciled unique source.
Windows inventories include nine project-cache and 75 D: link/access errors,
and broad discovery deliberately excludes system/installation/private cache
roots. Totals are therefore measured lower bounds. Compression conserves exact
bytes but is not a replacement for reviewing upstream source provenance.
WSL file removal does not establish host VHDX shrinkage. Windows sandbox setup
still fails at its locked runtime ACL refresh; no other chats were terminated
and sandbox permissions were not weakened.

## Largest remaining files

The largest is the 5,005,202,962-byte verified inactive-image archive; its unique
source recovery role is explicit. Historical raw campaign archives follow.
[Top 100 with reasons](LARGEST_REMAINING_FILES.md) also explains retained Git
packs, tool libraries, qualified environments and scientific inputs.

## Final machine state

[Final remnant audit](FINAL_MACHINE_AUDIT.md) records surviving locations and
classifications. Canonical PACT is usable; archive/source recovery and all
negative-result evidence remain available. Remaining ambiguity is retained and
reported under PACT_CLEANUP_PARTIAL.
