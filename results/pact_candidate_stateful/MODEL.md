# candidate_stateful implementation contract

Parent commit: `70b7d06a`, clean working tree before changes. All earlier compact
and raw scientific evidence is read-only. This is an additive mode; historical
v2 and candidate-sensitive evaluators and the physical measurement pipeline are
unchanged. Production depth is fixed at three nontransparent levels before
reading the diagnostic outcomes. No depth/seed sweep or outcome-based tuning.

## Implementation map

`optimizer/implementation_v2.py` supplies the existing search, legality, archive
integration, incremental diagonal coefficients and strict reference hooks.
`optimizer/search.py` supplies proposals, location indexes and Pareto archive.
`scripts/pact_candidate_sensitive.py` and its retained topology export supply
verified FAN inputs, baseline capacitance, actual Liberty truth functions,
driver positions, sink identities, fanout and measured seed architectures.
`scan/model.py` remains the canonical identity/serialization contract.

`phase0c_rewire_odb.py` establishes SI reattachment to Q and the chain-0 output
buffer/other-chain direct-port semantics. `physical_effect_export.py` establishes
net capacitance attribution at drivers. `pact_solver_routes.py` and
`physical_effect.py` remain the unchanged route and measurement adapters.

New code: `optimizer/candidate_stateful.py`, `optimizer/stateful_geometry.py`,
`scripts/pact_candidate_stateful.py`, `scripts/pact_stateful_corpus.py` and
`scripts/pact_stateful_report.py`. New evidence lives only in this namespace.

## Exact bounded state semantics

Each measured shift cycle has three settled snapshots: before scan-input change,
after scan-input change, and after the simultaneous FF clock update. The field
counts both adjacent differences. This captures two settled transitions where
SI and FF changes affect the same cone, without counting initialization, capture,
or between-pattern PI changes. PI1 is held at the exact FAN value in load and
unload; SE is one. SI retains its final load bit across capture and becomes zero
on first unload. Leading padding and zero-filled unload retain existing semantics.

FF Q states are generated from the exact shift ordering, with QN as its logical
complement. Waveforms are bit-packed. Liberty functions evaluate all simultaneous
fanin values with bitwise operations. BUF/INV consume no depth; nontransparent
gates consume one level. A gate is represented only if all functional fanins
have represented exact states and its maximum fanin depth plus gate depth is
at most three. Unrepresented/deeper fanins are excluded explicitly, never given
guessed boundary states. The graph is levelized once and its coverage recorded.

Local moves update existing transition diagonals and packed scan states in the
changed chains, compare FF waveforms, and enqueue only consumers of changed
waveforms. Topological queue order guarantees that all changed inputs arrive
before evaluating a gate. Unchanged fanins use cached values. Equal outputs
stop propagation and increment cancellation counters. Spatial fields update
only for changed output waveforms or changed net capacitance. The transaction
saves affected old waveforms, diagonals, order positions, caps and endpoints;
rollback restores them, including cross-chain/tail effects.

The independent reference uses an unpacked simultaneous scan simulator and
truth-table lookup over the full represented bounded graph, then constructs
the field independently. It does not use packed waveform generation, diagonal
updates, incremental Boolean evaluation or field-update kernels. Search checks
every 25 evaluations and every retained archive score at rtol=1e-9, atol=1e-6;
any mismatch aborts. Focused tests cover all mutation types and rejection.

Exactness is limited to settled Boolean states in this represented graph. It
does not imply event-delay simulation, delta-cycle glitches, or full-design
switching coverage. Captured FF response states remain supplied by FAN.

## Shared-net geometry and physical assumptions

Terminals contain actual baseline driver/cell origins, sink pin identities and
capacitances, and physical port centers. MMST is deterministic Prim over sorted
unique Manhattan coordinates, with stable ties and no routing dependency.
For nonzero baseline span with measured ground capacitance:

```
rho[n] = ground_baseline[n] / MMST(baseline_terminals[n])
ground_candidate[n] = rho[n] * MMST(candidate_terminals[n])
C[n,pi] = ground_candidate[n] + sum(actual candidate sink-pin caps)
```

Every valid per-net coefficient is retained, including zero coefficients.
Zero-span nets retain their measured ground term and use the previously derived
global scan-only rho only for new span. Missing-ground nets use that same global
rho as an explicit fallback. Each fallback is named in the geometry audit.
Baseline terminal reconstruction and measured-ground reproduction are checked
before any diagnostics/search. Two terminals reduce exactly to L1.

The model freezes the baseline buffer skeleton: an FF's existing scan SI leaf
net becomes its scan carrier; SI port paths retain their baseline leaf net. New
SI terminals join those nets together with retained functional terminals. A
baseline tail uses its original SO attachment net as its carrier. Pure terminal
SO buffer branches remain physically anchored and move their input endpoint to
the candidate tail carrier. Their exact waveforms follow the candidate tail Q,
including inverter polarity. Direct SO ports move directly. This reconstructs
the baseline exactly and keeps mixed-net sharing explicit at the attachment.

This is a baseline-anchored implementation estimate of the placed rewiring, not
a prediction of future buffer removal/insertion/resizing. Candidate routing may
replace those anchors. All Q/QN/port nets retain fixed transparent terminals where
appropriate; no separate rho*L1 branch is added atop functional wire. Per-trial
geometry logs record baseline and candidate terminals, both MMST lengths,
ground, per-net rho, estimated ground/pin totals and fallback reason for every
changed net. Baseline and selected full-net audits are also retained.

## Objectives and provenance

For represented nets, delta[n,t] is the sum of the two settled state differences.

```
D[b,t] = sum(n whose driver is in b) C[n,pi] * delta[n,t,pi]
E_stateful = sum(b,t) D[b,t]
H8_stateful = max(b,t) D[b,t]             # 8x8 grid
H4_stateful = max(coarse_bin,t) sum(four fine bins) D[b,t]
```

Wire remains the original port-inclusive Manhattan objective. Search uses
separate wire/E/H8 Pareto coordinates, the original maximum-edge guard, legal
K=2 capacities, existing mutation family, seed 11, 180-second loop ceiling and
20,000-evaluation limit. Initialization and mandatory reference checks have
separately reported overhead. No runtime tuning campaign.

Historical traces are reconstructed using their recorded scores/acceptance
only, reproducing every order/parent SHA256 and retained canonical hash; no old
objective calculation, experiment or route is rerun. This produces a complete
canonical hash corpus for novelty. Production logs record canonical architecture
hashes directly. All previous measured points are rescored before any new route.
The diagnostic outcomes are not used to select coefficients, depth or structure.

Only novel predicted nondominated points may be selected, at most two per design.
Available routes and their qualification remain unchanged: route, zero DRC,
nonnegative available setup/hold, topology, functional and FF-transition checks.
Implementation completion and measured frontier outcome are classified separately.
Absolute errors, pair order changes, Q/QN contributions, coverage, profiler data,
accepted/rejected propagation counters, commands, tool versions and historical
evidence hashes are retained. `summary.json` identifies the parent commit; the
delivery response and Git history identify the exact final commit (a commit
cannot contain its own hash without self-reference).
