# PACT end-to-end integration milestone

**PACT_END_TO_END_INTEGRATION_COMPLETE_FAULT_REPLAY_PENDING**

The three qualified seed-11, K=2 recommendations now produce concrete scan
implementations and remapped ATPG workloads. All mandatory permutation,
implementation, load replay, unload replay and physical-consumability checks
passed. Original and recovered FAN workloads have identical simulated coverage
and detected-fault counts. Complete detected-fault **set** comparison is blocked
by a SIGSEGV in the existing FAN detailed reporter, so it is not claimed.

## Results

| Design | FF count | Patterns | K | Permutation valid | Load replay | Unload replay | Fault equivalence | Implementation emitted | Physical-flow consumable | Overall |
|---|---:|---:|---:|---|---|---|---|---|---|---|
| s5378 | 179 | 117 | 2 | PASS | PASS | PASS | BLOCKED (coverage PASS) | PASS | PASS | PASS |
| s9234 | 211 | 156 | 2 | PASS | PASS | PASS | BLOCKED (coverage PASS) | PASS | PASS | PASS |
| s15850 | 534 | 133 | 2 | PASS | PASS | PASS | BLOCKED (coverage PASS) | PASS | PASS | PASS |

Overall is the mandatory integration-stage result, not a claim of complete
fault-identity verification. `PACT_END_TO_END_S5378_PASS` was established first;
the same pipeline then established the other two cases. Final bundles are
[`s5378/integration_v1`](s5378/integration_v1/summary.json),
[`s9234/integration_v1`](s9234/integration_v1/summary.json) and
[`s15850/integration_v1`](s15850/integration_v1/summary.json).

| Design | Load FF states checked | Expected response bits checked | Mismatches | Original → PACT coverage | Original → PACT detected/full faults |
|---|---:|---:|---:|---|---|
| s5378 | 20,943 | 20,943 | 0 | 96.04% → 96.04% | 11,354/11,822 → 11,354/11,822 |
| s9234 | 32,916 | 32,916 | 0 | 94.14% → 94.14% | 15,511/16,476 → 15,511/16,476 |
| s15850 | 71,022 | 71,022 | 0 | 94.62% → 94.62% | 29,763/31,456 → 29,763/31,456 |

Coverage differences are 0.00 percentage points. Lost-fault and unexpected-new
fault identity sets are **unknown**, represented by null, not empty lists.
All real input load/response bits are known binary values. Symbolic X transport
and masked unload handling are demonstrated in focused hand-constructed tests.

## Required engineering answers

1. **Automatic topology conversion:** Yes. `pact-integrate` reads
   `result.json:selected` and hash-verifies `optimized.architecture.json`, checks
   the saved recommendation's wire/local constraints, and emits the topology
   and concrete scan-only patch. No manual permutation copying occurs. A fresh
   solve can use configurable `--time-limit`; all reported runs reused the saved
   60-second results without running search.
2. **FF identity:** Exactly preserved. Physical instance name is the canonical
   identifier. DEF placement, architecture cells, ATPG signal identity map,
   old/new positions and independent replay agree bijectively. Input-map
   ambiguity, renamed FFs, different coordinates or clocks fail explicitly.
3. **Inventory:** Every FF occurs exactly once in both orders. Duplicate,
   missing, invented or empty-chain entries fail structural validation. Chain
   identity, SI/SO association and per-chain capacity remain fixed.
4. **Pattern remapping:** Yes. FAN BASIC_SCAN PPI is a parallel state indexed
   by its named header, not an original serial vector. PACT derives the original
   B0 serial schedule, decodes it through old chain positions to FF identities,
   and serializes the same state under the new chain topology. PPO expected
   capture state follows the corresponding response mapping. PI1/PO1 and all
   original fields are preserved with their signal headers. PI2/PO2/SI timing
   extensions, partial maps and invalid logic symbols fail explicitly.
5. **Independent cycle-level load replay:** PASS on all 406 patterns and
   124,881 FF states. The checker does not import the remapper. It executes
   simultaneous shift edges on both actual chain orders and compares each
   state against the independent source PPI map as well as against the other
   topology. Short chains receive leading padding under a common clock, so
   there is no implicit per-chain clock gating.
6. **Expected unload semantics:** PASS on all 124,881 supplied PPO bits. The
   checker seeds the expected captured FF state and explicitly samples SO
   before each shift edge, tracking the FF identity leaving each chain. This
   proves response transport, not functional capture logic simulation. The
   original optimizer's activity assumptions remain unchanged (no capture or
   final unload in its objective model).
7. **Fault equivalence:** Original and independently reconstructed workloads
   both ran `read_pattern`, `set_fault_type saf`, `add_fault -a`,
   `run_fault_sim`, and `report_statistics` successfully on the original FAN
   functional netlist. Pattern counts, full detected counts and coverage match
   exactly. Separately, `report_fault -s DT` terminates with **exit -11
   (SIGSEGV)** on each design before producing a complete identity list. The
   preserved probe logs/exit records are in each `fault_replay` directory.
   The source reporter dereferences circuit gate IDs before checking negative
   sentinel IDs and includes library-specific pin lookup; no speculative
   external-tool fix was introduced. We therefore cannot enumerate lost/new
   identities, even though the replayed workloads and coverage agree. No ATPG
   regeneration took place.
8. **Physical consumption:** Demonstrated. OpenROAD actually executed each
   emitted `implementation_patch.py`, producing `implementation.odb` and its
   gzip archive. Actual source FF inventory and coordinates match the input
   architecture. The existing qualified rewire adapter asserts unchanged
   functional nets/placement and correct SI/SO topology. The output is a placed
   database in the existing ORFS `3_place.odb` representation.
9. **Manual steps remaining to route:** Supply the installed tools and frozen
   source ODB, optionally execute the patch through the same integration CLI,
   stage emitted ODB plus original SDC under a new ORFS variant, then invoke
   the existing route and postroute verifier. Exact commands and the s9234f
   block-name exception are in the [guide](../../docs/end_to_end.md). The CLI
   stops after implementation/replay; it does not automatically launch a route.
10. **What prevents calling this complete today:** Full detected-fault identity
    equivalence lacks a reliable FAN export. This is a usable qualified-design
    integration flow, not a universal DFT/tester backend: generic direct K-chain
    physical application is NOT_RUN on real benchmarks; compressed scan,
    multi-clock timing and sequential FAN protocols are NOT_SUPPORTED. No
    postroute timing-aware capture or silicon tester qualification is claimed.
11. **Single next milestone:** Provide a safe, independently checked FAN
    detected-fault identity export and compare original versus recovered sets
    for these same three workloads. That closes the outstanding test-quality
    proof without changing or tuning the optimizer.

## Concrete implementation and existing route evidence

Each bundle contains human-readable `implementation_patch.json` with every
`SI -> FF -> ... -> FF -> SO` link, an executable `implementation_patch.py`,
canonical before/after topology, and `scan_permutation.json` with bidirectional
position maps, heads/tails, K, capacities, FF count and deterministic hashes.
`patterns_remapped.json` identifies the common-clock load/capture/unload phases
and physical port associations. `patterns_recovered.pat` is generated from
independent replay for FAN consumption.

Chain zero's logical `test_si_0`/`test_so_0` explicitly bind to physical
`test_si`/`test_so`; inherited buffers are transparent. Chain one uses direct
`test_si_1`/`test_so_1`. Only FF SI and the inherited scan-output buffer input
are rewired; functional D is untouched. New ports follow the existing policy.

| Design | Selected architecture SHA-256 | Existing internal routed edges matched | DRC | New route |
|---|---|---:|---:|---|
| s5378 | `7c9e378ead24878ac991a74f16f6365e2ea867a6309ece4f7362ca7abf935ff9` | 177 | 0 | NOT_RUN |
| s9234 | `f099374de4cb080ebfdfbf5e577bbf77acc7f3e802c4cb5dc5888c0327764f54` | 209 | 0 | NOT_RUN |
| s15850 | `4a82d24ea6465f7b68ceec9c84d883e17fd53ed29d3135093927ac7d227848ce` | 532 | 0 | NOT_RUN |

Every retained route report, archive SHA-256, selected architecture hash,
internal edge and reported SI/SO endpoint verification was checked. The exact
same selected orders were previously route-qualified, so those results were
reused. No optimizer, topology campaign, historical baseline or route campaign
was rerun. New inexpensive ODB patch applications proved actual consumption.

## Provenance and tests

The initial development worktree was clean on
`codex/pact-phase0d-budgeted-search`, base commit `e9c018df`. All solver modules,
objectives, M3/M5 definitions, moves, five-objective archive, recommendation
policy and historical evidence remain untouched. New integration artifacts are
isolated under `reports/end_to_end`.

Each `manifest.json` hashes every delivered artifact, selected/supplied solver
files, input files and integration source. Historic final results did not embed
raw input hashes: the adapter reconstructs their binding using the preserved
qualification freeze, identical supplied topology, selected output hash,
dimensions, policy constraints and exact qualified route. This limitation is
explicit; new solver runs invoked through integration record input bindings.
The three saved bundle verification checks passed, each checking 24 artifacts.

Focused tests: **28 passed**. They cover FF bijection, fixed capacities,
deterministic serialization/hashing, 1/2/3 chains, reversal, cross-chain exchange,
unequal lengths, SI/SO directionality, direct SO, symbolic X/masks, malformed
topology, duplicate/missing FFs, replay corruption and provenance corruption.
The full regression passed **267 tests in 124.76 seconds**, with zero failures,
errors or skips; evidence is in `regression.log` and `regression.xml`.
An initial collection-only attempt failed because the external Python venv
lacked `threadpoolctl`; its log/XML are retained separately. The already
installed pure-Python module was copied into the ignored `.optimizer-deps`
directory, alongside existing Numba, to run the complete suite. No package
installation or solver changes were needed.

Initial development diagnostic bundles remain on disk in ignored `reuse_check`,
`seed11_k2`, and `seed11_k2_final` directories; the delivered and classified
bundles are only `integration_v1`. Raw implementation ODBs remain locally
available, with compressed copies committed. No historical files were deleted.

Changed tracked files: `.gitattributes`, `.gitignore`, `README.md`, `pyproject.toml`.
End-to-end evidence uses byte-preserving Git attributes so checkout line-ending
conversion cannot invalidate its artifact hashes. Added:
`src/pact/integration/`, `scripts/pact_integrate.py`,
`tests/unit/test_end_to_end.py`, `docs/end_to_end.md`, and this evidence tree.
The milestone is committed on the existing branch; nothing is pushed.
