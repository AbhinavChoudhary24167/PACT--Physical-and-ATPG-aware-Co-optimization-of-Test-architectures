# Gate 9 prospective benchmark

Scientific entry passed after both large designs completed and six of six candidates qualified. **Preparation complete; heavy launch held by D capacity and pending reference admission.**

| Design | Source assignments | Source FFs | Family role | Admission |
|---|---:|---:|---|---|
| b14_opt | 5592 | 245 | base family | Pending |
| b15_opt | 7471 | 449 | base family | Pending |
| b17_opt | 24171 | 1414 | composition scaling stress | Pending |
| b18_opt | 73183 | 3270 | composition scaling stress | Pending |

These are unmapped source counts. The composed circuits share base families and will be reported as scaling stress, with family dependence retained.

[Official source](https://github.com/cad-polito-it/I99T/tree/8a2c3b500ee7ff20e7031de92592b737bedc6d8c) pinned at `8a2c3b500ee7ff20e7031de92592b737bedc6d8c`; license and source SHA receipts retained externally. Raw sources: `D:\PACT_EXPERIMENTS\results\pact_gate9_large_scale_unseen_20261005`. No raw netlist enters Git.

The preregistration freezes K=2, seed=11, epsilon 0.02/0.05/0.10, 900 seconds per mutation loop, 7200 seconds per search worker, the existing reference rule, objectives, role ordering, maximum three pre-route candidates, FAN workload and exact activity definitions.

Run order: source admission → complete external reference qualification → reference freeze → cold search → candidate freeze → physical/topology/routing/DRC/timing → FAN → exact activity → measured comparison. Unsupported imports remain explicit admission blockers.

Current capacity: C 19.46 GiB, D 17.57 GiB. Heavy admission requires C ≥6 GiB and D ≥25 GiB, with a higher per-design margin when measured sizes require it. One heavy CPU worker; no GPU or distributed execution.

The measurement schema includes size, patterns/cycles/nets, exact throughput, runtimes, RSS, trace bytes, routed cost, timing, DRC, fault coverage, E/H4/H8, and qualification/success rates. Missing stages remain null with a reason, never zero.

Restore D capacity to the fixed floor and admit b14_opt reference under frozen tools; do not launch a heavy stage until both gates pass.
