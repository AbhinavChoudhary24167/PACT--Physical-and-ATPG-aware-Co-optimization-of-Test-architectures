# Post-merge large unseen campaign

**Both large unseen designs completed; six of six frozen candidates qualified.** s38417 CS_C2 reduced E by 0.3164%, H4 by 2.4396%, and H8 by 0.9961%, with 1.0144% more routed scan wirelength. It is a preregistered secondary candidate; the primary balanced roles remain CS_C1. The other five candidates have mixed activity tradeoffs.

This supports the registered large-design generalization question for these two circuits and seed 11. It does not establish universal improvement or independent replication across design families.

PR [#3](https://github.com/AbhinavChoudhary24167/PACT--Physical-and-ATPG-aware-Co-optimization-of-Test-architectures/pull/3) merged at `084db2f9e164b7757597fec1eec73d9c4049a9a4`.

Branch: `development/large-unseen-gate9-20261005`. Status: **END_TO_END_COMPLETE**.

```text
CURRENT_WORK_PR: 3
PR_URL: https://github.com/AbhinavChoudhary24167/PACT--Physical-and-ATPG-aware-Co-optimization-of-Test-architectures/pull/3
PR_STATUS: MERGED
MERGED: true
MERGED_SHA: 084db2f9e164b7757597fec1eec73d9c4049a9a4
POST_MERGE_BRANCH: development/large-unseen-gate9-20261005
WORKTREE_CLEAN: false
STORAGE_BEFORE: {"C:/": {"free": 1099124736, "total": 199569510400, "used": 198470385664}, "D:/": {"free": 25123098624, "total": 125828067328, "used": 100704968704}}
STORAGE_AFTER: {"C": {"total": 199569510400, "free": 20864045056}, "D": {"total": 125828067328, "free": 18869878784}, "F": {"total": 362531516416, "free": 98498113536}}
C_FREE: 20864045056
D_FREE: 18869878784
FILES_RELOCATED: [{"source": "C:\\Users\\Abhinav\\AppData\\Local\\WWE 2K25", "destination": "F:\\PACT_HOST_CACHE\\20261005\\WWE 2K25", "file_count": 583, "bytes_relocated": 8622282983, "state": "RELOCATED_SHA256_VERIFIED_ORIGINAL_PATH_PRESERVED", "original_path_behavior": "Directory junction retains the original application path"}]
FILES_REMOVED: [{"Path": "C:\\Users\\Abhinav\\.cache\\codex-runtimes\\codex-runtime-install-RP37N7", "FilesRemoved": 20079, "BytesRemoved": 1196169716.0, "Classification": "Stale runtime installer download/extraction; installed codex-primary-runtime is retained"}, {"Path": "C:\\Users\\Abhinav\\AppData\\Local\\pip\\cache", "FilesRemoved": 631, "BytesRemoved": 423811311.0, "Classification": "Reconstructible downloaded pip HTTP/wheel cache; installed packages are retained"}, {"Path": "C:\\ProgramData\\NVIDIA Corporation\\NVIDIA App\\UpdateFramework\\ota-artifacts", "FilesRemoved": 1279, "BytesRemoved": 4741442336.0, "Classification": "Downloaded/extracted updater packages; installed drivers and applications are retained"}, {"Path": "D:\\PACT_EXPERIMENTS\\results\\pact_cpu_scalability_20261005\\continuation\\s38417\\REF_B2\\normal\\s38417\\REF_B2\\transitions.u8", "BytesRemoved": 2333115960, "CompleteTraceAndAllScientificReceiptsPreserved": true}, {"design": "s38584", "candidate": "CS_C1", "Path": "/mnt/d/PACT_EXPERIMENTS/results/pact_large_unseen_gate9_20261005/compact_activity/continuation/s38584/CS_C1/normal/s38584/CS_C1/transitions.u8", "BytesRemoved": 3193840720, "CompleteTraceAndAllScientificReceiptsPreserved": true, "Classification": "Derived count cache removed by the frozen workflow after complete exact activity qualification"}, {"design": "s38584", "candidate": "CS_C2", "Path": "/mnt/d/PACT_EXPERIMENTS/results/pact_large_unseen_gate9_20261005/compact_activity/continuation/s38584/CS_C2/normal/s38584/CS_C2/transitions.u8", "BytesRemoved": 3193651062, "CompleteTraceAndAllScientificReceiptsPreserved": true, "Classification": "Derived count cache removed by the frozen workflow after complete exact activity qualification"}, {"design": "s38584", "candidate": "CS_C3", "Path": "/mnt/d/PACT_EXPERIMENTS/results/pact_large_unseen_gate9_20261005/compact_activity/continuation/s38584/CS_C3/normal/s38584/CS_C3/transitions.u8", "BytesRemoved": 3193461404, "CompleteTraceAndAllScientificReceiptsPreserved": true, "Classification": "Derived count cache removed by the frozen workflow after complete exact activity qualification"}, {"design": "s38417", "candidate": "CS_C1", "Path": "/mnt/d/PACT_EXPERIMENTS/results/pact_large_unseen_gate9_20261005/compact_activity/continuation/s38417/CS_C1/normal/s38417/CS_C1/transitions.u8", "BytesRemoved": 2333115960, "CompleteTraceAndAllScientificReceiptsPreserved": true, "Classification": "Derived count cache removed by the frozen workflow after complete exact activity qualification"}, {"design": "s38417", "candidate": "CS_C2", "Path": "/mnt/d/PACT_EXPERIMENTS/results/pact_large_unseen_gate9_20261005/compact_activity/continuation/s38417/CS_C2/normal/s38417/CS_C2/transitions.u8", "BytesRemoved": 2333115960, "CompleteTraceAndAllScientificReceiptsPreserved": true, "Classification": "Derived count cache removed by the frozen workflow after complete exact activity qualification"}, {"design": "s38417", "candidate": "CS_C3", "Path": "/mnt/d/PACT_EXPERIMENTS/results/pact_large_unseen_gate9_20261005/compact_activity/continuation/s38417/CS_C3/normal/s38417/CS_C3/transitions.u8", "BytesRemoved": 2333115960, "CompleteTraceAndAllScientificReceiptsPreserved": true, "Classification": "Derived count cache removed by the frozen workflow after complete exact activity qualification"}]
EVIDENCE_PRESERVED: true
S38584_PREVIOUS_PARTIAL_STATUS: INTERRUPTED_NO_COMPLETION_RECEIPT
END_TO_END_LARGE_DESIGN_STATUS: END_TO_END_COMPLETE
HAS_PACT_LARGE_DESIGN_ROUTED_WIN: true
EVIDENCE: [{"design": "s38584", "candidate": "CS_C1", "classification": "PACT_MIXED_TRADEOFF", "delta_WL": 0.5221809228340923, "delta_E": -0.3077775595157317, "delta_H4": -2.036816604186442, "delta_H8": 0.833072959980452}, {"design": "s38584", "candidate": "CS_C2", "classification": "PACT_MIXED_TRADEOFF", "delta_WL": 0.4719708234723452, "delta_E": -0.4257068424374122, "delta_H4": 0.14199312431735223, "delta_H8": 2.0255748512489014}, {"design": "s38584", "candidate": "CS_C3", "classification": "PACT_MIXED_TRADEOFF", "delta_WL": 0.571610021878266, "delta_E": -0.2976468645997432, "delta_H4": -1.3499863858153716, "delta_H8": 0.7932962265874366}, {"design": "s38417", "candidate": "CS_C1", "classification": "PACT_MIXED_TRADEOFF", "delta_WL": 1.2147297878664087, "delta_E": 0.017852891387426517, "delta_H4": -2.0365274874853845, "delta_H8": 0.11987581893779797}, {"design": "s38417", "candidate": "CS_C2", "classification": "PACT_STRONG_IMPROVEMENT", "delta_WL": 1.014430404140887, "delta_E": -0.31639788190882534, "delta_H4": -2.439633706861122, "delta_H8": -0.9961036649112409}, {"design": "s38417", "candidate": "CS_C3", "classification": "PACT_MIXED_TRADEOFF", "delta_WL": 0.9475779910890658, "delta_E": -0.07748960246384273, "delta_H4": -1.890053548368087, "delta_H8": 0.006313568724691798}]
GATE9_READY: false
GATE9_BLOCKER_IF_ANY: D capacity 18869878784 bytes is below the 26843545600-byte minimum floor; source mapping and reference admission also pending
NEW_SCIENTIFIC_CLASSIFICATION: ["PACT_CPU_SCALABILITY_WORK_MERGED", "PACT_LARGE_UNSEEN_COLD_SEARCH_COMPLETE", "PACT_LARGE_UNSEEN_PHYSICAL_QUALIFICATION_COMPLETE", "PACT_LARGE_UNSEEN_GENERALIZATION_CONFIRMED"]
NEXT_ACTION: Restore D capacity to the fixed floor and admit b14_opt reference under frozen tools; do not launch a heavy stage until both gates pass
S38584_NEW_SEARCH_STATUS: SEARCH_COMPLETE
S38584_LANES_COMPLETE: 3
S38584_CANDIDATES_FROZEN: 3
S38584_PHYSICAL_RESULTS: [{"candidate": "CS_C1", "routed_scan_WL": 97819.24, "delta_WL": 0.5221809228340923, "WNS": 8.49904, "hold_WNS": 0.000728612, "DRC": 0, "fault_coverage": 93.33, "qualification": "QUALIFIED"}, {"candidate": "CS_C2", "routed_scan_WL": 97770.38, "delta_WL": 0.4719708234723452, "WNS": 8.49866, "hold_WNS": 0.000689671, "DRC": 0, "fault_coverage": 93.33, "qualification": "QUALIFIED"}, {"candidate": "CS_C3", "routed_scan_WL": 97867.34, "delta_WL": 0.571610021878266, "WNS": 8.49945, "hold_WNS": 6.77236e-06, "DRC": 0, "fault_coverage": 93.33, "qualification": "QUALIFIED"}]
S38584_FINAL_RESULT: {"status": "CONTINUATION_COMPLETE", "records": [{"candidate": "CS_C1", "status": "QUALIFIED", "classification": "PACT_MIXED_TRADEOFF"}, {"candidate": "CS_C2", "status": "QUALIFIED", "classification": "PACT_MIXED_TRADEOFF"}, {"candidate": "CS_C3", "status": "QUALIFIED", "classification": "PACT_MIXED_TRADEOFF"}]}
S38417_SEARCH_STATUS: SEARCH_COMPLETE
S38417_LANES_COMPLETE: 3
S38417_CANDIDATES_FROZEN: 3
S38417_PHYSICAL_RESULTS: [{"candidate": "CS_C1", "routed_scan_WL": 37289.885, "delta_WL": 1.2147297878664087, "WNS": 8.72304, "hold_WNS": 0.00316436, "DRC": 0, "fault_coverage": 96.0, "qualification": "QUALIFIED"}, {"candidate": "CS_C2", "routed_scan_WL": 37216.09, "delta_WL": 1.014430404140887, "WNS": 8.72282, "hold_WNS": 0.00307385, "DRC": 0, "fault_coverage": 96.0, "qualification": "QUALIFIED"}, {"candidate": "CS_C3", "routed_scan_WL": 37191.46, "delta_WL": 0.9475779910890658, "WNS": 8.72304, "hold_WNS": 0.00316436, "DRC": 0, "fault_coverage": 96.0, "qualification": "QUALIFIED"}]
S38417_FINAL_RESULT: {"status": "CONTINUATION_COMPLETE", "records": [{"candidate": "CS_C1", "status": "QUALIFIED", "classification": "PACT_MIXED_TRADEOFF"}, {"candidate": "CS_C2", "status": "QUALIFIED", "classification": "PACT_STRONG_IMPROVEMENT"}, {"candidate": "CS_C3", "status": "QUALIFIED", "classification": "PACT_MIXED_TRADEOFF"}]}
```

| Design | Reference | Candidate | Routed scan WL | ΔWL % | E | ΔE % | H4 | ΔH4 % | H8 | ΔH8 % | WNS | Hold WNS | DRC | Fault coverage % | Search runtime s | Peak RSS KiB | Qualification |
|---|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|
| s38584 | REF_B3T | Reference | 97311.1 | 0 | 1.78323e+09 | 0 | 2320.401 | 0 | 796.9224 | 0 | 8.49908 | 6.77236e-06 | 0 | 93.33 | — | — | QUALIFIED_EXTERNAL_REFERENCE |
| s38584 | REF_B3T | CS_C1 | 97819.24 | 0.5221809 | 1.777742e+09 | -0.3077776 | 2273.139 | -2.036817 | 803.5613 | 0.833073 | 8.49904 | 0.000728612 | 0 | 93.33 | 4398.995 | 2518736 | QUALIFIED |
| s38584 | REF_B3T | CS_C2 | 97770.38 | 0.4719708 | 1.775639e+09 | -0.4257068 | 2323.696 | 0.1419931 | 813.0647 | 2.025575 | 8.49866 | 0.000689671 | 0 | 93.33 | 4398.995 | 2518736 | QUALIFIED |
| s38584 | REF_B3T | CS_C3 | 97867.34 | 0.57161 | 1.777922e+09 | -0.2976469 | 2289.076 | -1.349986 | 803.2444 | 0.7932962 | 8.49945 | 6.77236e-06 | 0 | 93.33 | 4398.995 | 2518736 | QUALIFIED |
| s38417 | REF_B2 | Reference | 36842.35 | 0 | 1.391035e+09 | 0 | 2094.429 | 0 | 813.5087 | 0 | 8.72304 | 0.00316436 | 0 | 96 | — | — | QUALIFIED_EXTERNAL_REFERENCE |
| s38417 | REF_B2 | CS_C1 | 37289.89 | 1.21473 | 1.391283e+09 | 0.01785289 | 2051.776 | -2.036527 | 814.4839 | 0.1198758 | 8.72304 | 0.00316436 | 0 | 96 | 3887.367 | 2271204 | QUALIFIED |
| s38417 | REF_B2 | CS_C2 | 37216.09 | 1.01443 | 1.386634e+09 | -0.3163979 | 2043.333 | -2.439634 | 805.4053 | -0.9961037 | 8.72282 | 0.00307385 | 0 | 96 | 3887.367 | 2271204 | QUALIFIED |
| s38417 | REF_B2 | CS_C3 | 37191.46 | 0.947578 | 1.389957e+09 | -0.0774896 | 2054.843 | -1.890054 | 813.56 | 0.006313569 | 8.72304 | 0.00316436 | 0 | 96 | 3887.367 | 2271204 | QUALIFIED |

All candidate activity values require complete routed, physical, ATPG and exact-activity qualification. Search estimates remain separate.

Search runtime and peak RSS describe the whole design search worker and are repeated for its candidates; they are not additive candidate runtimes.

s38584 completed 803 exact mutation evaluations (236/256/311 by epsilon lane), with a 4398.99-second search worker and 2518736 KiB peak RSS. s38417 completed 1017 evaluations (310/355/352), with a 3887.37-second worker and 2271204 KiB peak RSS. Each search initialized from its frozen external reference and recorded zero historical-state accesses. Registered loop budgets remained 900 seconds; completion of an in-flight exact evaluation can put observed loop time above that budget.

WNS and hold WNS retain the frozen backend global-route timing stage. Registered capacitance-weighted transition proxies; E is not a joule measurement.

Existing useful-improvement definition: at least one exact E/H4/H8 gain above the fixed tolerance among preselected fully qualified candidates; all activity regressions and routed-wire costs remain reported. Search epsilon bounds predicted wire; it is not a new routed-wire qualification gate. No candidate reselection.

The initial capacity gate passed before the large-design campaign. Every heavy stage used one worker and explicit completion receipts. Current free space is a separate admission decision for the next campaign.

Lossless NTFS compression was applied to completed packages and three retained historical VCDs. All recorded file SHA256 values and modification timestamps remained unchanged. The historical trace compression pass reduced observed D free space by 4384989184 bytes; its cause is unverified. No backup or scientific evidence was deleted to recover that space.

One historical report was restored to its exact gate0 CRLF bytes after Git checkout normalization. The final preservation audit checks the original 1772 historical bindings, the registered merged implementation and tools, the interrupted progress/log, and eight complete compressed activity streams.

Focused pre-PR verification: 74 tests passed in 54.56 seconds; imports, scientific continuation guard, and wheel build passed. Post-merge orchestration checks passed before source freeze. GitHub exposed no required checks; the tested, reviewed CPU branch was merged with a standard merge commit. No historical scientific campaign or reference simulation was repeated.

Gate 9 prospective source intake, fixed protocol, family-dependence policy, admission chain and measurement schema are prepared in `results/pact_gate9_large_scale_unseen_20261005`. No Gate 9 heavy search or reference simulation has launched. The D capacity blocker is reported explicitly.
