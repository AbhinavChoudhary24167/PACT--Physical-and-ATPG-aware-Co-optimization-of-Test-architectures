# PACT candidate-sensitive physical model

## Implementation map (before changes)

Parent: `04d87d60` (successful PACT-v2 milestone). The working tree was clean.
`src/pact/optimizer/implementation_v2.py` contains the frozen-load evaluator,
independent simultaneous FAN replay, transition-diagonal updates and search.
`optimizer/search.py` provides local mutations, location indexes and Pareto archive.
`scripts/pact_v2.py` binds verified FAN BASIC_SCAN PPI/PPO states, frozen FF/port
coordinates, direct Q/QN OpenRCX ground plus Liberty sink loads and existing seeds.
`scan/model.py` provides canonical architecture serialization and hashes.

`scripts/phase0c_rewire_odb.py` changes SDFF_X1 SI pins and scan endpoints only:
successors attach to Q, while QN and functional fanout remain intact. Chain 0 SI
uses the inherited input buffer; chain 0 SO uses the inherited BUF_X1 input.
Additional chains connect directly to their ports. Q is not scan-exclusive.
`reports/physical_effect/<design>/<P|T>` contains qualified routed ODB, mapped
netlist, per-net OpenRCX/Liberty capacitances, source coordinates and measurements.
The ODB supplies driver/sink connectivity, fanout and buffer/inverter descendants;
the Nangate45 Liberty in the existing WSL ORFS installation supplies input caps.
`scripts/physical_effect_export.py` documents the current attribution convention.
`scripts/pact_solver_routes.py` and `scripts/physical_effect.py` remain the route
and measurement implementations. Their topology, functional and FF-transition
checks remain authoritative. `results/pact_v2/{summary.json,<design>/search.json}`
and its measurement manifest identify previously selected architectures and the
measured frontier; these are read-only inputs and additional search seeds.

The extension is `candidate_sensitive` within this backend, with evidence in
`results/pact_candidate_sensitive`. No historical route, ATPG or experiment is
regenerated. Model equations, assumptions and measured outcomes follow below.

## Model and equations

Old v2 uses `sum(i,t) toggle[i,t] * Ceff_baseline[i]` with the entire
direct-Q/QN baseline load at the FF origin. It includes old scan pins/wire,
but omits changed successors, SI-port switching, buffer descendants and logic.

The new implementation reads the qualified baseline ODB once. It verifies that
the sum of actual Liberty sink-pin caps on each net equals the stored measurement.
FF Q/QN roots own their transparent BUF/INV closure. A sink is scan-dependent
when it is an FF SI, a scan-output port, or a transparent branch whose terminals
are exclusively scan-dependent. Thus mixed functional/scan Q nets are split,
and functional QN and shared buffer branches are retained. SDFF scan muxes are
inside the sequential library cell: rewiring changes SI, not functional D.
Canonical `_0` scan-port names are mapped to the physical unsuffixed BTerms.

For each owned baseline net n:

```
F[n] = sum(functional sink Liberty capacitances)
       + Cground_baseline[n] * HPWL(functional terminals + driver)
                                / HPWL(all terminals + driver)
```

The ratio is bounded to [0,1]. A zero-span net retains its ground load only if
it retains functional terminals. The pin partition is exact; the shared-wire
partition is an approximation, not an extraction of individual route branches.
Every original total, retained value, removed scan value, ratio and retained
pin is written to `physical_model.json`. Absent ground data is explicitly listed
and uses the existing pin-only fallback; invalid pin sums/caps fail closed.
Incident coupling is excluded, matching the unchanged final ground+pin metric.

The wire coefficient rho is the median `ground_ff / Manhattan_distance_um`
over extracted, positive-length, scan-exclusive, single-sink nets in the baseline
FF/SI transparent closures. Samples can end at SI, a transparent cell, or SO.
Multi-terminal functional nets cannot calibrate it. Every sample, distance,
capacitance and ratio is recorded. There is no textbook constant or fit to
activity labels. Actual coefficients/sample counts are in the milestone README.

Candidate scan capacitance is:

```
S[i,pi] = C_SI[successor] + rho * L1(FF_i, successor)  (internal edge)
S[tail,pi] = C_SO_buffer_inputs[chain] + rho * L1(tail, SO_port)
I[chain,pi] = C_SI_buffer_inputs[chain] + C_SI[first]
             + rho * L1(SI_port, first)
```

The port-buffer terms retain actual baseline transparent input-pin loads along
the port paths (zero when no buffer exists). These collapse each port path to
one Manhattan span; they do not predict candidate-specific detours or new
buffer insertion. Other scan-exclusive repair buffers are removed from the
invariant model and are not individually predicted. Candidate scan branches
are added independently to retained functional wire; shared trunk reuse is
not modeled and can overestimate changes.

Each FF receives its retained functional transparent-net capacitance at each
net's actual baseline driver location. One further nontransparent combinational
level is included. Liberty truth functions yield uniform Boolean input
sensitivity `s[p] = Pr(f(x) != f(x xor e_p))`, enumerated once during initialization.
Sensitivities reaching a gate from the same FF are summed and capped at one;
they are normalized across represented FF sources by `max(1, sum(s))`.
Each gate's output net and its transparent descendants contribute that fraction
of actual baseline ground+pin capacitance. Reconvergent duplicates for the same
source/net use the maximum contribution. This bounds double counting, but it
does not model joint state correlation, cancellation, glitches or deeper logic.
Q and QN have identical transition counts; their opposing logic states are not
propagated through this sensitivity approximation.

Let `A[i,b]` be these precomputed functional and one-gate contributions in bin b.
Let `q[i,t]` be exact FF toggles and `u[c,t]` exact scan-input toggles:

```
D[b,t,pi] = sum_i q[i,t,pi] * (A[i,b] + 1[b=FFbin(i)] * S[i,pi])
           + sum_c 1[b=SIportbin(c)] * u[c,t,pi] * I[c,pi]
E_candidate(pi) = sum_b,t D[b,t,pi]
H8_propagated(pi) = max_b,t D[b,t,pi]       (8 by 8 grid)
```

H4 aggregates the same field into 4 by 4 bins. Source-localized candidate H8
instead assigns `sum_b A[i,b] + S[i,pi]` to the FF origin, retaining SI at its
port. Both candidate H8 forms and frozen v2 H8 are explicitly named and saved.
Search uses propagated H8, candidate E and the original port-inclusive wire
objective as separate Pareto coordinates. The existing maximum Manhattan edge
guard remains: stored STA does not provide reliable per-edge criticality.

## Exact workload and incremental algorithm

The original `fan_workload` identity remap and binary-bit rejection policy are
used without generating patterns. PPI loads, capture PPO responses, chain
capacity, leading padding and zero-fill unload remain identical. SI retains
the last loaded bit across capture and transitions to zero at the first unload
cycle, matching the existing stimulus. Capture/init remain outside the objective.

The extension uses v2's transition-diagonal coefficients, mutations, location
indexes, archive and search loop through optional evaluator hooks; default v2
behavior is unchanged. Sparse source-to-bin arrays are precomputed. A local
mutation updates only diagonal coefficients adjacent to moved state positions.
Its moved positions and immediate predecessors refresh scan loads; this includes
stationary FFs with new successors and tail/SO changes. The changed diagonal
deltas update the old spatial field, followed by subtract/add of affected source
contributions. Only changed chains refresh their SI vectors. Rollback applies
the inverse patch through the same transaction. No per-candidate topology walk,
gate simulation, extraction or route occurs.

Work is proportional to changed diagonals/positions times pattern count, chain
length and sparse bin width, plus the existing global field reduction and O(N)
wire/legality checks. Initialization and final packaging may be more expensive.
The slow reference independently replays simultaneous FF and SI states and
rebuilds the dense spatial field; it does not use the incremental kernels.
Every 2,000 evaluated moves and every final archive score must match it within
`rtol=1e-9, atol=1e-6`; a mismatch aborts instead of accepting drift.

Profiler output separates transition updates, candidate-load updates, spatial
updates, reduction/geometry, mutation generation and archive insertion. Update
times include rollback; initialization/JIT and final reference checks are reported
separately or included in the clearly labeled search/runtime totals. RSS is the
Linux process peak, not a per-candidate allocation. No runtime tuning campaign
was performed.

## Search, selection and physical qualification

One run per s5378/s9234/s15850 uses the established seed-11 placement, original
FAN workload, 180-second mutation budget and 20,000-evaluation ceiling. Starting
points include P/T, J50, previous PACT and every qualified selected v2 candidate.
All legal starts can be mutated, including geometrically infeasible starts
through the existing repair acceptance. Deterministic replay uses an evaluation
ceiling and a nonbinding wall budget; wall-limited production counts depend on
machine scheduling and are recorded rather than claimed bitwise repeatable.

Route selection excludes all seed hashes and any candidate predicted dominated
by or equal to any stored measured architecture. It prioritizes strict predicted
dominance improvements, followed by genuinely new predicted tradeoffs, at most
two per design for this run. It does not fill the quota with dominated points.
The selection preference is not the search objective. Stored actual measurements
are never used to fit electrical weights.

Only newly selected architectures pass through the existing routing and
measurement adapters. Final eligibility requires route qualification, zero DRC,
nonnegative available setup/hold values and passing topology, functional and
FF-transition checks. The measured Pareto space remains routed scan-path upper
bound, all-data C·N and all-data H8. All existing measured v2 architectures join
the comparison; no historical evidence is overwritten or rerouted.

Prediction comparisons include absolute values and paired percentage changes
against prior frontier points. Different coverage makes absolute frozen/new E
scales differ; relative changes are the more useful diagnostic. A successful
new measured frontier point demonstrates architecture quality, but a selected
sample alone cannot establish a general predictor accuracy or causal advantage
over a new frozen-model search. Full outcomes are in the result README/summary.

## Entry points and retained evidence

The production run used the existing WSL environment:

```sh
export PYTHONPATH=.optimizer-deps:src OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1
PY=/root/pact-deps/pact-venv/bin/python
# Use a fresh namespace for a future replay; existing evidence cannot be overwritten.
OUT=results/pact_candidate_sensitive_replay
for d in s5378 s9234 s15850; do
  $PY scripts/pact_candidate_sensitive.py export --design "$d" --output "$OUT"
  $PY scripts/pact_candidate_sensitive.py search --design "$d" --output "$OUT" \
      --seconds 180 --max-evaluations 20000 --route-limit 2
  $PY scripts/pact_candidate_sensitive.py route --design "$d" --output "$OUT" --route-seconds 600
  $PY scripts/pact_candidate_sensitive.py measure --design "$d" --output "$OUT"
done
$PY scripts/pact_candidate_sensitive.py report --output "$OUT"
```

These are reproduction instructions, not an additional campaign performed in
this milestone. `inputs.json` binds each actual production invocation and source
revision; export, route and measurement execution records contain their commands.
`comparison.csv` reports retained predictions and measured implementations;
`evaluations.csv.gz` records every trial order/parent and its disposition.
Canonical retained architectures are in each design's `architectures/` directory.
The summary also compares novelty against *all* previous v2 evaluation hashes,
not merely supplied seeds. The original seed-relative count remains separately
available. Timing rates include reference checks, with mutation-loop-only rates
also reported to avoid confusing reference overhead with inner evaluation cost.

`pact_candidate_check.py` reconstructs physical models, replays every selected
architecture with both predictors, verifies physical bindings/checks, validates
the single repository suite result, and hashes every prior v2 compact artifact.
It seals compact new evidence while indexing ignored raw waveforms/databases
and retaining compressed stimuli, cycles and per-cycle results. Git ignores
raw ODB, SPEF, simulation binaries, VCD, ORFS work trees and uncompressed logs
of all evaluations. Prior v2 outputs and final physical-measurement code remain
unchanged.
