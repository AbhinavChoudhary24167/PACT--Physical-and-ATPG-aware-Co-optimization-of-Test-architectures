UPSTREAM_IMPLEMENTATION_REPAIR

Affected source: FAN_ATPG `26b2b36c0e9db11a4b6d9e759df6e44357121f39`, `pkg/fan/src/atpg_cmd.cpp`, `ReportFaultCmd::exec`. The repair is isolated on `fix/report-fault-scan-identities` in `scratch/FAN_ATPG-report-repair` and retained as a patch plus standalone regression.

The historical reporter probe exited -11. The same qualified executable now exits zero on the retained minimal reproducer, so a current crash is not claimed. Its output nevertheless contains repeated anonymous `(SDFF_X1)` detected-fault sites and cannot establish identity equivalence. The reporter also suppresses every row without a state filter and indexes negative control-gate sentinels before checking them.

The fix handles sentinel IDs before indexing, maps PPI/PPO to the functional Q/D ports already used by Circuit, restores unfiltered reporting and prints each existing equivalence multiplicity. Extraction, fault collapsing, simulation, ATPG, patterns and libraries are unchanged. `qualification.json` records equal statistics with the original executable on all three frozen workloads and complete unique identity exports. `report_fault_scan.py` additionally checks full/state-filtered identity equality and weighted counts.

Fault identity scope is the complete collapsed SAF target universe with equivalence weights. Individual uncollapsed class-member identities are not enumerated. The original fault extractor premarks certain test-control faults DT; this behavior is preserved.

The source patch and regression are prepared for later upstream submission. No upstream PR or publication was made in this task.
