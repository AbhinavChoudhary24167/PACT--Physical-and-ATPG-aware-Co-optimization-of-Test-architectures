# Final machine/remnant audit

Discovery inspected 195294 directories across C/D/E/F after removal; 100 access errors and 954 exclusions were recorded. System/install/cache roots and links are skipped deliberately. Additional user-owned WSL dependency roots were inventoried separately.

| Significant retained path | Bytes | Classification / purpose |
|---|---:|---|
| `C:\Users\Abhinav\OneDrive\Desktop\PACT\PACT\scratch` | 152,702,279 | KEEP_REPRODUCIBILITY: qualified environment or source repair workspace |
| `C:\Users\Abhinav\OneDrive\Desktop\PACT\PACT\external\OpenROAD-flow-scripts` | 1,615,062,249 | UNKNOWN_KEEP: source/build copy or scratch needs reconciliation |
| `C:\Users\Abhinav\OneDrive\Desktop\PACT\PACT\external\OpenROAD` | 1,283,893,608 | UNKNOWN_KEEP: source/build copy or scratch needs reconciliation |
| `C:\Users\Abhinav\OneDrive\Desktop\PACT\forensic-quarantine` | 6,475,383 | QUARANTINE: excluded caches/administrative pointer |
| `C:\Users\Abhinav\OneDrive\Desktop\PACT\.pact-validation-env` | 502,648,296 | KEEP_REPRODUCIBILITY: qualified environment or source repair workspace |
| `C:\Users\Abhinav\OneDrive\Desktop\PACT\.github-publication-env` | 502,672,362 | KEEP_REPRODUCIBILITY: qualified environment or source repair workspace |
| `D:\PACT_EXPERIMENTS\tmp` | 5,704,711,928 | UNKNOWN_KEEP: source/build copy or scratch needs reconciliation |

Active PACT development is the canonical checkout. Historical copy members are removed; archives are on E:. D: retains source/debug scratch; F: retains Gate09 source fixtures. WSL retains tool source/platforms and the qualified Python environment, with generated Phase0B/0C runs removed. The quarantined publication worktree retains its small administrative pointer and excluded caches; its Git branch/history remains canonical. This remnant is not a usable development checkout. The unrelated game cache is untouched.

The archived inactive image contains unique source not fully reconciled with standalone exports. Its compressed image remains the lossless recovery authority. The Windows OpenROAD index has staged deletions and untracked files, so HEAD equality alone is not sufficient for deletion. OpenROAD/ORFS content comparison results are retained locally and summarized in the final report. No uncertain source tree was discarded.

The completed OpenROAD content comparison found 9,015 candidate and 10,800 retained entries, with 1,786 differences and no candidate-only entries. These trees are not byte-identical. The ORFS comparison stalled during a WSL filesystem read and was interrupted without modifying source. Neither copy was discarded.
