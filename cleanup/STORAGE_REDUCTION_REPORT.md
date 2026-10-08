# Storage reduction report

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
