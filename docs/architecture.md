# Architecture

`ScanArchitecture` (`src/pact/scan/model.py`) contains immutable placed FF records and named SI-to-SO ordered chains. Serialization hashes include physical coordinates; scan-order identity and physical serialization identity are distinct.

The maintained M3/M5 tool is `pact.optimizer.cli`: `io` loads supplied or placed inputs, `costs` constructs repaired architecture-dependent loads, `kernels` computes exact incremental scan activity, and `search` manages spatial construction, mutations, rollback, bounded Pareto admission and checkpoints.

The implementation-aware path uses `implementation_v2`, `candidate_sensitive`, `candidate_physical`, `candidate_stateful` and `stateful_geometry`. Earlier model classes here remain components of the current inheritance/comparison path. They are distinct from the removed historical H_eff8 Optimizer-v1/v2 subsystem. State includes packed Q/QN waveforms, simultaneous fanins, a bounded settled-Boolean cone and shared MMST net geometry calibrated from baseline ground capacitance. Buffers remain anchored to baseline topology.

`stage_b` screens physical feasibility before waveform work. `stage_b_inputs` reconstructs the exact frozen model from portable compressed JSON. E, H4, H8 and balanced lanes retain independent endpoint winners.

`integration` maps FF identities, serializes stored load/capture-response/unload states, independently replays them and emits scan-only patches. Physical adapters rewire in OpenDB, route with ORFS, reconstruct SI-to-SO connectivity and measure extracted-capacitance-weighted switching. `pact.physical_effect` provides measurement primitives.

Shared phase-named modules remain because current code or contract tests import their metric, endpoint-ownership and physical-validation behavior. Renaming them solely for appearance would add risk without reducing storage.
