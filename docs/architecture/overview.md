# Architecture and supported interfaces

`scan/model.py` represents immutable placed FFs and named SI-to-SO chain orders. Coordinate-dependent serialization identity differs from scan-order identity. Qualified maps connect ATPG, placed and exported-netlist names. Validators require every FF once, capacities, clock domains, fixed endpoints and complete traversal without cycles/forks/orphans.

| Layer | Implementation under `src/pact/` | Responsibility |
|---|---|---|
| Numerical solver | `optimizer/io.py`, `costs.py`, `kernels.py`, `search.py` | Repaired M3/M5 loading, exact incremental activity, legal mutations, rollback and checkpoints |
| Candidate physical model | `implementation_v2.py`, `candidate_sensitive.py`, `candidate_physical.py` | Stored trajectories, architecture-dependent shared-net geometry/loads |
| Stateful model | `candidate_stateful.py`, `stateful_geometry.py` | Simultaneous settled logic through a bounded cone and spatial accumulation |
| Constrained/CPU flows | `stage_b.py`, `stage_b_inputs.py`, `cold_start.py`, `cpu_incremental.py` | Feasibility screening, independent endpoint lanes, portable bundles and exact CPU evaluation |
| Integration | `integration/` | Identity, pattern permutation, serial replay, export and fault/physical qualification |
| Measurement | `physical/`, `activity/`, `physical_effect.py` | Implemented connectivity, route/extraction and transition measurements |
| Practical impact | `gate10a_decision.py`, `gate10a_spatial.py` | Registered power/IR parsing, spatial comparison and deterministic decisions |

`pact-optimize`, `pact-integrate` and `pact` are installed entry points. Scientific campaigns use their registered scripts. Shared phase-named modules remain because current code/tests import their contracts; maintenance makes no cosmetic source moves.

## Dependency map

Numerical reproduction needs source/package dependencies, architecture/placement identities, stored workloads and model config. Saved Stage-B replay adds compressed portable bundles and selected-order JSON. Full physical reproduction adds hash-matched ODB/SDC, legal library/PDK inputs, pinned backend/submodules, patches and simulator/FAN binaries. Gate 10A consumes frozen physical artifacts and measured activity rather than a new search.

Compiled objects, builds and caches are regenerable. Route/extraction/VCD outputs are generated but may be unique evidence; verified campaign archives protect their exact bytes. See [canonical reproduction](../reproduction/canonical_results.md) and [archive policy](../../archives/README.md).
