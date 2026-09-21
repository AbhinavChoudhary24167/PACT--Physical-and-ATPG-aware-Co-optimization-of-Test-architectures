# PACT Optimizer-v2 pre-design bottleneck note

This note records the implementation audit completed before Optimizer-v2 was
designed. It describes the code as it existed at the start of
`PACT_OPTIMIZER_V2_SCALABLE_SEARCH`; it is not a proposed redesign.

## Current optimizer behavior

The artifact boundary represents an architecture as an immutable
`ScanArchitecture`: a tuple of fixed `ScanCell` records and a tuple of
`ScanChain` records, each containing an ordered tuple of FF names. Optimizer-v1
builds five complete architectures with cheapest/regret insertion, then runs a
bounded large-neighborhood search. An LNS proposal removes 5, 10, or 20 percent
of the FFs using one of five destroy rules and reinserts every removed FF by a
physical/activity scalar ranking. Every unique child is structurally checked,
evaluated with the qualified port-aware Manhattan scan HPWL proxy and exact
H_eff8, and offered to a two-objective unbounded Pareto archive. The activity
ranking used during construction/repair is explicitly a heuristic and is not
reported as H_eff8.

The qualified physical objective is the sum of SI-to-head, consecutive FF-to-FF,
and tail-to-SO Manhattan distances. `PhysicalCostModel.replacement_delta`
recomputes every changed chain and is exact, but it does not isolate the small
set of edges changed by a local move. Exact H_eff8 is the maximum, over all
pattern shift cycles and 8x8 spatial bins after the fixed radius-one
convolution, of direct-sink-weighted FF toggles.

## Code-derived bottlenecks and complexity

Let `N` be FF count, `K` chain count, `P` ATPG pattern count, `L` maximum chain
length, `R` the number of FFs removed by LNS, and `E` the number of evaluated
candidates.

| Operation in the audited code | Time | Extra memory / copying |
| --- | ---: | ---: |
| `ScanArchitecture.canonical_dict` / `sha256` | O(N log N) from sorting plus O(N) JSON | O(N) complete serialized content |
| `validate_scan` | O(N) expected | O(N) names, visited cells, counters and sets |
| `phase0d_operators.apply_operator` | O(N), even for a local move | Copies every chain to lists, copies them again as `before_groups`, rebuilds every chain tuple, builds complete before/after edge sets, and hashes complete architectures |
| Full qualified physical proxy | O(N) | O(N) edge-length list in `phase0c_scan_geometry` |
| v1 `replacement_delta` | O(length of every changed chain), worst O(N) | No dense matrix, but not changed-edge local |
| One `_insertion_options` call | O(N log N) because every legal position is generated and sorted | O(N) option tuples |
| v1 full constructor | O(N^3 log N) as implemented: at each of N insertions every remaining FF is tested at O(N) positions | O(N) working architecture plus O(N) option/ranking lists per iteration |
| v1 repair of R removed FFs | O(R^2 N log N) as implemented; R=qN gives cubic worst-case growth | O(N+RN) transient ranking/options, depending on iteration |
| region/hotspot destroy | O(N log N) | O(N) flat lists, coordinates, ranking, partial-chain copies |
| structural proof without patterns | O(N) plus full hashes | O(N) |
| structural proof with all patterns | O(P L N) | Repeated full state dictionaries and schedules |
| exact `parallel_activity_metrics` / H_eff8 | O(P L N) for shifting and mapping, plus fixed-grid convolutions | O(LN) batch per pattern plus per-grid cycle tensors |
| exact Pareto insert in v1 | O(A) dominance scans, where A is archive size | Archive is unbounded |
| generic Phase-0D hypervolume/crowding paths | O(A^2) nondominance, with additional sorting | O(A) to O(A^2) transient lists |

There is no dense `N x N` physical matrix in v1, which is a useful property to
preserve. However, v1 has no spatial index: physical construction discovers
good neighbors by scanning all possible insertion locations. The existing
Phase-0D operator sampler does not enumerate a full neighborhood, but generating
one sampled child still invokes the complete-copy/apply/validate/edge-set/hash
path.

## Complete architecture copies

Complete or near-complete architecture materialization occurs in:

1. `phase0d_operators.apply_operator`: all chain tuples become lists,
   `before_groups` duplicates them, and every chain is rebuilt into tuples.
2. `optimizer_v1.destroy`: all chains and the flattened inventory are copied;
   another complete partial-chain collection is produced.
3. `optimizer_v1.repair_groups`: all partial chains are copied before repeated
   list insertion.
4. `_architecture_from_groups`: every final chain is converted to a tuple.
5. `ScanArchitecture.canonical_dict` and `sha256`: all cells and chains become
   dictionaries and JSON. Search invokes hashes multiple times per proposal.
6. Search state and cache artifacts retain complete boundary architectures or
   paths plus large per-candidate records rather than compact move states.

The immutable `cells` tuple itself is normally shared when a child is created,
but serialization reconstructs every cell record.

## Complete objective recomputation

`FrozenProxyContext.evaluate` performs a full structural/ATPG proof, full
`parallel_activity_metrics`, full `phase0c_scan_geometry`, and full chain
statistics for every cache miss. The physical model calculates an exact
replacement delta for LNS records, but the authoritative physical objective is
still recomputed in the evaluator. Exact H_eff8 is always recomputed from zero.

H_eff8 is not an edge-additive objective. A changed order changes scan state
propagation along each affected chain for potentially every cycle of every
pattern. Its final value is also a global maximum after spatial accumulation
across all chains. Therefore it is not valid to update H_eff8 from only the
few changed scan edges. At minimum, exact reuse requires retaining cycle/bin
contributions and recomputing the complete affected chain trajectory; a simple
bounded-radius order-window delta is not justified by the current definition.

## Growth with evaluated candidates

The v1 runner keeps a record for each unique evaluation in its JSON state,
including objectives, move details, descriptors, and paths. It also writes a
complete architecture, proof, and proxy record for each new exact evaluation.
The in-memory state, trace, seen-hash set, and on-disk cache therefore grow with
`E`; stored architecture/proxy material grows approximately O(EN). The primary
archive is not capped, so its storage is O(A) and dominance/update cost grows
with A. This is acceptable for the frozen 128-evaluation Phase-0D limit but is
not a scalable inner-loop representation.

These observations define the v2 redesign boundary: keep `ScanArchitecture`
for compatible input/output, but make the inner loop mutable and integer-indexed;
make local moves transactional; update physical cost from exact changed edges;
use a sparse spatial candidate graph; bound neighborhood, archive, evaluations,
moves, and wall time; and keep exact H_eff8 authoritative without pretending it
is locally edge-decomposable.
