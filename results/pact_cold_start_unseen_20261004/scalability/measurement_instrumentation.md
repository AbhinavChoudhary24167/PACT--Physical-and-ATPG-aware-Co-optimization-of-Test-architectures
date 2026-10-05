# Exact activity measurement instrumentation

Each reference/candidate measurement is an independent unit with the registered
1,800-second deadline. The budget covers routed export, extraction, compile,
simulation, VCD analysis and exact metric reduction. A failed measurement cannot
stop another eligible unseen design. At least20GiB free scratch is required.

The frozen exporter, electrical extraction, stimulus, Icarus functional scan
simulation, parser and metric arithmetic are retained. The qualified traversal
guard and sized scan-master recognition adapters apply to all architectures.
The analysis inserts timer contexts/decorators only. Removing those insertions
must reproduce the complete original executable AST. No numeric expression,
operation order, test window, physical attribution or activity scope is changed.

`instrumentation.json` contains these observations:

| Observation | Attribution |
|---|---|
| Export/extraction/compile/simulation/analysis wall and CPU | Separate child stage receipts; Linux `wait4` preserves CPU/RSS on timeout |
| VCD generation | Integrated with the unchanged VVP simulation process; isolated emission wall time is unavailable and explicitly null |
| VCD size | Exact file byte count; completeness records whether functional simulation finished |
| VCD parse | Streaming parser inclusive wall minus separately timed transition-flush wall |
| Transition extraction | The unchanged nested flush routine, including active-window selection and exact alias transition accounting |
| FF transition verification | Separate independent simultaneous chain replay over every FF/cycle |
| E computation | Original per-scope transition totals, capacitance weighting and statistics |
| H4/H8 computation | Original per-scope spatial attribution, bin reductions, peaks and statistics |
| Peak RSS | Maximum per-process lifetime high-water mark across launcher and child stages; not summed simultaneous process-tree RSS |

VCD parse/transition CPU and RSS are attributed to their inclusive shared span.
Their exclusive CPU/RSS fields remain unavailable. Inclusive and exclusive spans
must not be added. Whole-run CPU sums launcher CPU with the sequential child
stage CPU observations. A live analysis receipt identifies the active span if
the deadline terminates parsing or reduction.

Exact retained-waveform checks on the unseen s953/s1196/s1238 references compare
all net/cycle transition counts, the independent FF crosscheck and the complete
decoded activity summary. All three pass with zero tolerance; no historical
design, extra route or extra simulation is used. The focused parser tests also
preserve final-timestamp cycle-marker semantics, physical net aliases and
unknown-active-net rejection. A forced-timeout test verifies retained CPU/RSS.

Incomplete or unqualified waveforms provide diagnosis only. No E/H4/H8 result
is emitted for a failed exact measurement. The retained previous s38417 failure
occurred in simulation and never reached parsing or metric reduction. Its VCD
progress markers do not establish test correctness or scientific activity.
