# PACT Implementation-Aware Backend v2

## Implementation map

The parent milestone is `646355f191c840e1c6809cb8dbee9815d2b3345a`.
`pact.scan.model.ScanArchitecture` remains the architecture/identity format;
`pact.integration.patterns.fan_workload` supplies the verified FAN load and
capture-response states. `pact.optimizer.search` supplies the existing swap,
reversal, insertion, segment-exchange operators, location index and bounded
Pareto archive. Frozen DEF port centers and FF placement supply wire geometry.
`reports/physical_effect/<design>/<P or T>/net_activity_capacitance.csv` supplies
OpenRCX grounded capacitance plus Liberty sink-pin capacitance. The existing
rewire, ORFS route, routed topology verification, stimulus, extraction and VCD
analysis scripts qualify and measure only selected new architectures.

## Formulation and approximations

For each FF i, Ceff[i] is the sum of ground_ff + pin_ff over its directly
driven Q/QN nets in the physical baseline. Every FF must have a mapped Q net.
Missing extracted ground capacitance falls back to the measured sink-pin
capacitance and is individually recorded; absent/invalid pin data is an error.
No invented capacitance or random workload is used. These frozen loads include
the baseline scan sinks. They do not predict candidate-specific rerouted loads,
buffer descendants or combinational switching. Final measurements include the
entire non-clock data network and newly extracted candidate capacitances.

The exact reference evaluator simulates simultaneous FF updates. Each pattern
loads the identity-remapped PPI state from zero with leading zero padding for
short chains, installs the original PPO response at capture, then unloads with
zero fill. Both phases last the longest chain length, so every subsequent load
starts at zero. Capture and initialization are excluded, as in the established
physical-effect schedule. Unknown state bits are rejected, never filled.

The search objectives, all minimized, are:

* C_wire = sum of Manhattan lengths of SI-to-first, adjacent FF and last-to-SO
  edges using frozen port centers (the existing port-aware HPWL estimator).
* E = sum over pattern, phase, cycle and FF of Ceff[i] times its binary toggle.
* H8 = maximum over pattern, phase, cycle and 8×8 die bin of weighted toggles.

H4 is also reported with the existing 4×4 bins. It is not a post-hoc alternative
objective. Entire FF weights are attributed to FF origins, using the exact
`pact.physical_effect.spatial_bin` boundary convention.

The timing guard C_timing is maximum Manhattan scan edge length, including
ports: a distance-sensitive timing-risk constraint, **not slack or delay**.
The default ceiling is 1.1 times the physical baseline's maximum edge and is
configurable independently of the wire allowance. This prevents introducing
long outlier connections; it cannot establish setup/hold feasibility. Existing
route STA setup/hold metrics and DRC are recorded after implementation.

The wire ceiling is (1 + wire_allowance) times the specified physical baseline,
with the existing 0.10 engineering default exposed in configuration. FF inventory,
placement, clock-domain legality, K and each chain capacity are fixed. Cross-chain
swaps are allowed when legal; chain membership itself is not frozen here.

## Evaluation and search

A slow simultaneous replay is the independent reference. The search evaluator
retains per-chain transition diagonals and a global cycle-by-bin field. A local
mutation changes only diagonals adjacent to changed state positions, plus the
spatial/capacitance columns of moved FFs. Update work is O(patterns × chain length
× changed positions); unchanged chains and workload portions are retained.
Rejected moves are inverted. Final retained scores are rebuilt and compared
against the reference, preventing accumulated floating error from selecting a
candidate. No fast-math is used.

Existing Pareto archive/crowding and local mutation operators are reused.
Search rotates activity, spatial and wire improvement preferences under the
explicit constraints and periodically restarts from retained candidates or
provided P/T, J50 and PACT seeds. A deterministic evaluation limit and a wall-time
budget are configurable. Seed scoring/compilation are recorded separately from
the mutation budget. The archive uses separate objectives, not a weighted score.
`runtime_seconds` includes initialization and final reference checks;
`search_seconds` includes the mutation loop and final reference checks. The last
timestamp in `evaluations.csv.gz` records the mutation-loop duration itself.

Select at most three new feasible nondominated candidates: lowest activity,
lowest H8 and a balanced candidate minimizing the worst baseline-normalized
objective among the remaining frontier. This last rule only allocates the small
route budget; it does not define success. Deduplicate architecture hashes and
exclude every supplied baseline from physical implementation.

Final nondominance uses measured routed scan-path upper bound, all-data C·N
total and all-data 8×8 weighted peak among DRC/topology-qualified implementations.
Raw transition metrics, 4×4 peaks and STA are also reported. This comparison
does not imply watts, IR-drop, signoff timing or silicon reliability improvement.

## Provenance

`results/pact_v2` is a new namespace. Search records parent commit, exact input
hashes, baseline and generated identities, configuration, seed, commands, tool
versions, wall time and evaluations. Every evaluated architecture has an order
ID and metrics in the compact evaluation log; retained candidates have canonical
architecture files. Route and measurement manifests bind the actual inputs.
Prior evidence is read only; raw databases/waveforms remain locally ignored.
