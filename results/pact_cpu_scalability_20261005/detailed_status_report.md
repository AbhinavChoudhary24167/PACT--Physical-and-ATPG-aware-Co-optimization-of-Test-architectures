# PACT CPU-first development and unseen-design continuation

Status snapshot: **5 October 2026, 11:23 IST (05:53 UTC)**.

The CPU evaluator and exact compact activity backend are qualified. Both large
external-reference activity measurements now qualify. The s38584 missing-SPEF
repair is complete and preserves the registered capacitance definition.
The subsequent cold search started, but its worker ended without a completion
receipt. No new large-design candidate has completed physical qualification.

This report supersedes the *status* in `cpu_scalability_report.md`, which was
written before the authorized SPEF repair. That earlier report and the original
scientific-stop receipt remain preserved as evidence.

## 1. Scope and provenance

The baseline is commit `9a8a63cb003e9eea966e47769073a65a758029db`; the dedicated
branch is `development/cpu-scalability-20261005`. Changes remain uncommitted and
reviewable in the working tree. New receipts live in this result directory;
large raw artifacts use `D:\PACT_EXPERIMENTS\results\pact_cpu_scalability_20261005`.
The historical `pact_cold_start_unseen_20261004` campaign remains separate.

The optimizer retains K=2, seed 11, epsilon values 0.02/0.05/0.10, the existing
objectives, operators, acceptance rules and candidate-selection ordering. Cold
initialization uses only the frozen external reference. No previous PACT
architecture or archive supplies a starting point. There is no GPU, distributed
execution, broad multiprocessing or further evaluator optimization in the
continuation patch.

The original CPU-stage audit established that **1772 historical files were
unchanged**. That audit and the settled s35932/activity equivalence checks were
not repeated for the bounded repair. Executed sources, inputs, architectures,
tools and evidence are bound by SHA-256 in the corresponding receipts.

## 2. CPU evaluator: measured performance

The controlled witness uses s35932, one worker and the same fixed path of
128 exact mutation evaluations. It measures evaluator performance rather than
rerunning the historical optimization campaign.

| Measurement | Original evaluator | CPU incremental evaluator | Interpretation |
|---|---:|---:|---|
| Exact mutations per second | 0.336460 | 1.596226 | **4.744× throughput** |
| Mutation-loop wall time | 380.431 s | 80.189 s | 78.92% lower |
| Complete witness wall time | 421.130 s | 131.524 s | 68.77% lower |
| Complete witness CPU time | 423.786 s | 131.655 s | Same witness scope |
| Spatial-update time | 179.872 s | 25.174 s | **86.00% lower** |
| Rejection rollback | 157.456 s | 0.529 s | **99.66% lower** |
| Scan-waveform generation | 24.207 s | 25.160 s | No measured improvement |
| Gate propagation | 9.810 s | 9.684 s | Approximately unchanged |
| Geometry | 0.486 s | 0.484 s | Approximately unchanged |
| Reduction | 0.458 s | 0.447 s | Small contribution |
| State construction | 16.790 s | 37.484 s | Increased initialization cost |
| Peak RSS | 1,537,588 KiB | 1,551,964 KiB | +14.04 MiB / +0.94% |

The original bottleneck combined strided spatial writes with repeated traversal
of unchanged packed cycles. Rejection also reran waveform/field work to undo a
proposal. The new implementation uses contiguous tile columns, skips identical
eight-cycle blocks when capacitance is unchanged, caches exact transition
totals, updates affected spatial reductions and restores sparse transaction
snapshots directly. Bulk array copying was not the dominant original cost:
cProfile attributed only 0.117 seconds to NumPy array-copy calls.

Spatial updates and scan-waveform generation are now comparable at about
25 seconds each in this witness. Construction and independent replay remain
material costs outside the mutation loop. Timers and cProfile spans overlap;
they should not all be added together. Native time is charged to its caller,
so isolated native dispatch overhead was not measured.

The optional independent reference evaluator trades speed for memory. Full
reference replay took 11.150 seconds with 1,321,484 KiB peak RSS. Per-pattern
bounded replay took 16.800 seconds with 275,472 KiB peak RSS, a **79.15% memory
reduction**. The resulting score is bit-identical. This is a memory tradeoff,
not an additional speedup claim.

## 3. Exactness and verification

The CPU tests exercised 4096 deterministic proposals, more than 2000 exact
mutations and more than 1000 rejected moves across all five operators.
Comparisons covered the preserved packed evaluator, an independent unpacked
oracle, E/H4/H8, objective values, acceptance decisions and rejection-state
hashes. Rejected state restores bitwise. Padding and zero-capacitance cases
also have focused coverage.

The s35932 controlled witness has identical proposal orders, acceptance
decisions, selected architectures and independently replayed selected metrics.
Intermediate E accumulation differs by at most 0.000030756, within the
registered optimizer `rtol=1e-9, atol=1e-6` rule. This is tolerance-qualified
exactness, not a claim that every intermediate floating-point value is
bit-identical.

The established CPU-stage focused suite passed **57 tests in 28.18 seconds**.
The bounded SPEF patch subsequently passed **16 directly relevant tests in
4.89 seconds**, plus the stop/continuation guard test in 1.90 seconds. These
groups overlap; they should not be summed into a unique-test total.

Evidence: `evaluator_equivalence.json`, `verification.json`,
`reference/equivalence.json` and `spef_patch/qualification.json`.

## 4. Exact compact activity backend

The CPU Icarus VPI collector records settled-timestamp transitions in a gzip
binary scalar-net-by-cycle matrix. It retains the mapped circuit, stimulus,
zero-delay simulation mode, capacitance definitions, spatial bins, scopes and
reductions. Qualification requires complete simulation, a valid count-stream
footer, functional replay, unknown/overflow checks and independent FF checks.

| Design | Count values compared | Full VCD bytes | Compact bytes | Size reduction |
|---|---:|---:|---:|---:|
| s953 | 1,300,290 | 561,671 | 109,189 | 5.14× |
| s1196 | 1,288,008 | 420,655 | 89,626 | 4.69× |
| s35932 | 556,948,224 | 589,581,353 | 68,900,761 | **8.56×** |

All per-cycle counts and source totals match exactly. Across the three
equivalence cases, **1818 numeric summary/map values have zero absolute
difference**, satisfying the original activity threshold
`1e-10*max(1,abs(reference))`. Fresh full-VCD controls also reproduce the
preserved event streams.

The controlled fresh s35932 simulator took 386.645 seconds with full VCD and
234.406 seconds with compact collection: **1.65× simulator speedup**.
The full workflow scopes differ because equivalence runs include oracle
comparison work; a controlled end-to-end activity speedup has not been
established. The 8.56× trace reduction is 88.31% fewer bytes.

## 5. Both large reference measurements qualify

These are frozen external-reference measurements. They do not establish that
PACT has improved a new routed candidate.

| Field | s38417 REF_B2 | s38584 REF_B3T |
|---|---:|---:|
| Activity status | QUALIFIED | QUALIFIED after bounded reanalysis |
| Complete shift cycles | 171,780 | 189,658 |
| Mapped nets | 13,582 | 16,838 |
| Independent FF-cycle checks | 281,032,080 | 270,452,308 |
| Compact trace bytes | 374,107,061 | 482,381,871 |
| E | 1,391,034,999.4807134 | **1,783,229,997.7849805** |
| H4 | 2094.4293152 | **2320.4008376039997** |
| H8 | 813.50868644 | **796.92240403** |

E/H4/H8 use the existing PACT metric definitions and units; E is not presented
as a measured joule value. Numbers from different designs are not a
before/after optimization comparison.

s38417 completed in 1013.712 seconds wall, 926.482 seconds CPU and 2,543,880 KiB
peak RSS; simulation took 852.591 seconds. Its already-qualified reference
measurement was not repeated.

s38584 originally completed simulation in 1029.984 seconds but failed activity
analysis because four switched nets lacked SPEF D_NET sections. The original
failed workflow took 1195.856 seconds wall and 1071.730 seconds CPU, with
3,299,524 KiB peak RSS. The repair reused that complete trace: **no simulator
rerun**. Reanalysis took 330.957 seconds overall; its measured analysis child
took 321.452 seconds wall, 136.616 seconds CPU and 3,407,780 KiB peak RSS.
These are separate workflow scopes, not one new full simulation measurement.

## 6. s38584 SPEF diagnosis and repair

The actual blocker was s38584. The earlier patch text's s38417 identification
was corrected by the authoritative continuation instruction.

| Net | NAME_MAP | D_NET | ODB | Exact driver | Sinks | Wire/vias/segments | RC objects | Classification |
|---|---|---|---|---|---:|---|---|---|
| net654 | Present | Absent | Present | place655/Z, BUF_X1 | 0 | None; length 0 | None | SPEF_ZERO_WIRE_FALLBACK |
| net655 | Present | Absent | Present | place656/Z, BUF_X1 | 0 | None; length 0 | None | SPEF_ZERO_WIRE_FALLBACK |
| net714 | Present | Absent | Present | place715/Z, BUF_X1 | 0 | None; length 0 | None | SPEF_ZERO_WIRE_FALLBACK |
| net719 | Present | Absent | Present | place720/Z, BUF_X1 | 0 | None; length 0 | None | SPEF_ZERO_WIRE_FALLBACK |

Each net has exactly one output terminal and no sink terminal, port, regular
wire, global wire, special wire or routed geometry. Both the frozen routed ODB
and a fresh extracted ODB agree. Cap-node, resistance-segment and coupling
segment counts are all zero. Logical/physical identities and preserved
terminal/geometry relationships match. Upstream scan-driver relationships are
recorded in the detailed diagnostics.

Driver placement coordinates in micrometres are respectively (57, 67.2),
(168.15, 219.8), (113.62, 88.2) and (76.57, 113.4). Independently established
Liberty sink-pin load is zero because there are no sinks. The nets still
switch: their preserved transition totals are respectively **46625, 46524,
46854 and 46868**. Their counts remain in the activity stream.

Re-extraction using the frozen OpenROAD binary, Liberty, rules and original
parameters independently reproduces all four omissions. Every normally parsed
SPEF capacitance entry matches the original extraction exactly. The evidence
supports a legitimate dangling, no-interconnect representation. It does not
establish a parser, mapping or upstream OpenRCX defect. No upstream repair or
PR is justified by this reproduction.

The analyzer accepts zero wire capacitance only through an explicit evidence
bundle bound to the implementation, extraction, mapping, Liberty, architecture
and exporter. Known pin load is retained. Missing D_NET alone never supplies
zero capacitance. Real routed geometry, ambiguous identities, missing physical
nets, unknown loads and unexplained omissions remain fail-closed.

The four nets qualify through **qualified zero-wire fallback**, not normal
SPEF extraction, mapping repair or extractor repair. Reanalysis records:

| Diagnostic counter | Count |
|---|---:|
| Normally complete switched SPEF nets | 16,029 |
| Evidence-qualified zero-wire nets | 4 |
| Mapping errors | 0 |
| Extraction errors | 0 |
| Unresolved nets | 0 |

The original strict behavior remains the default without an evidence context.
The original `scientific_stop.json` is preserved; `stop_resolution.json` records
its authorized resolution. The complete 482,381,871-byte trace retains SHA-256
`9a62be932918fd4b83717a8e312324c41f914553fd5b07f5dfc7ef5e557c6a5d`.
Every cached count byte was checked against that stream before read-only reuse,
and independent FF checking passed. The reconstructible 3.193-GB temporary
count cache was then removed; the compressed trace and receipts remain.

## 7. Cold campaign: actual current state

After s38584 requalified, cold search was launched immediately. Its registered
configuration retained seed 11, K=2, all three epsilon lanes and **900 seconds
per mutation loop** for each large design. The search worker ceiling is
7200 seconds. Maximum three candidates are selected by the original role
ordering and hash deduplication before any candidate routing.

The last preserved s38584 epsilon=0.02 checkpoint reports:

| Field | Last recorded value |
|---|---:|
| Exact mutation evaluations | 97 |
| Accepted moves | 27 |
| Mutation attempts | 396 |
| Screened infeasible attempts | 259 |
| Mutation-loop elapsed time | 334.312 seconds |

At the 05:53 UTC live check, no search worker remained and no search execution,
lane-completion, preselection or final-result receipt existed. WSL had recently
restarted; its current kernel log records an unclean journal and startup.
The precise reason for the earlier interruption is not established. It is
**not classified as a scientific failure, a proven OOM, or a measured timeout**.
Partial progress and logs are preserved. Live status supersedes the earlier
commentary that described the worker as still running.

| Campaign stage | s38584 | s38417 |
|---|---|---|
| Frozen exact reference activity | QUALIFIED | QUALIFIED |
| Cold search | INTERRUPTED; partial first lane | Not started; originally queued serially |
| Completed cold-search lanes | 0 | 0 |
| Final preselected candidate packages | 0 | 0 |
| New candidate physical/FAN qualification | Not started | Not started |
| New candidate activity and final comparison | Not started | Not started |

Search champions at an incomplete checkpoint are surrogate estimates. They are
not evidence of routed E/H4/H8 improvement. Candidate physical/FAN/activity
orchestration is prepared and syntax-checked, but has not yet produced measured
candidate results. Additional genuinely unseen designs / Gate 9 have not yet
been attempted.

## 8. Runtime, resources and next action

Normal large activity ceiling remains **7200 seconds**; diagnostic ceiling
remains **14400 seconds**. Historical 1800-second records are not rewritten.
The RAM-based policy permits one heavy worker group, one Python/native worker,
one simulator and one OpenROAD job. OpenROAD retains its frozen two-thread
setting. The host exposes four logical CPUs and approximately 3.8 GiB RAM;
8 GiB swap is not counted as parallel-worker capacity.

At the live check C: had only **597,323,776 bytes free (about 570 MiB)** and D:
had **25,123,098,624 bytes free (about 23.40 GiB)**. D: still meets the prepared
candidate workflow's 20-GiB scratch reserve, but C: has very little headroom
for the WSL backing disk and host operation. This capacity issue is observed;
it is not proof that disk pressure caused the interrupted search.

The next experiment is a new, separately recorded cold-start attempt from the
same frozen reference after restoring stable execution and host-disk headroom.
The partial attempt must remain preserved; it cannot be represented as a
completed lane or silently used as a new warm-start architecture. Then finish
all three lanes for each large design, freeze at most three candidates, run the
existing physical and FAN gates, measure complete compact activity, classify
the final routed results against each design's own reference, and proceed to
Gate 9. This requires no repeat of settled reference or equivalence work.

## 9. Implementation files and evidence map

CPU implementation: `src/pact/optimizer/cpu_incremental.py`,
`src/pact/optimizer/cpu_reference.py`, with the Stage-B default and cold-search
dependency hooks in `stage_b.py` and `scripts/pact_cold_start.py`.

Activity implementation: `src/pact/activity/counts_vpi.cpp`, `compact.py`,
`spef_evidence.py`, `scripts/pact_cpu_activity.py` and
`scripts/pact_cpu_vcd_witness.py`. Repair/reproducer tools:
`pact_spef_probe.py`, `pact_spef_evidence_export.py`, `pact_spef_reanalyse.py`.
Campaign/resource tools: `pact_cpu_scalability.py`, `pact_cpu_reference.py`,
`pact_cpu_gates.py`, `pact_cpu_continue_search.py`,
`pact_cpu_qualify_continuation.py`, and the optional scientific-stop hook in
`pact_cold_start_physical.py`. Method documentation is `docs/cpu_scalability.md`.

Focused new tests are `tests/unit/test_cpu_incremental.py`,
`test_compact_activity.py`, `test_cpu_gates.py` and `test_spef_evidence.py`.

| Evidence | Location relative to this report |
|---|---|
| Preserved baseline/tool/input bindings | `gate0.json` |
| Fixed-path CPU timing | `profile_oracle_128.json`, `profile_incremental_128_sparse.json` |
| CPU/oracle verification | `evaluator_equivalence.json`, `verification.json` |
| Activity equivalence | `activity/equivalence/{s953,s1196,s35932}/CS_C1/normal/` |
| s38417 accepted reference | `activity/continuation/s38417/REF_B2/normal/result.json` |
| SPEF reproduction and implementation evidence | `spef_patch/reproducer.json`, `spef_patch/implementation_evidence.json` |
| Per-net diagnostics and s38584 accepted metrics | `spef_patch/reanalysis/missing_spef_diagnostics.json`, `spef_patch/reanalysis/result.json` |
| Qualified repair/source hashes | `spef_patch/qualification.json` |
| Resolved original scientific stop | `stop_resolution.json` |
| Registered cold-search inputs/configuration | `continuation/manifests/s38584_search.json` |
| Preserved partial search | `continuation/searches/s38584/budget_0.02/progress.json` |

## 10. Required bounded-patch status fields

```text
PATCH_STATUS: QUALIFIED; bounded flow-robustness repair complete
ROOT_CAUSE: Four dangling single-driver BUF_X1 output nets have no physical
            interconnect or load; frozen extractor omission reproduced.
S38584_MISSING_NETS:
  net654: QUALIFIED_ZERO_WIRE_FALLBACK
  net655: QUALIFIED_ZERO_WIRE_FALLBACK
  net714: QUALIFIED_ZERO_WIRE_FALLBACK
  net719: QUALIFIED_ZERO_WIRE_FALLBACK
IS_OPENRCX_BUG: NO_EVIDENCE_OF_DEFECT
IS_PARSER_BUG: NO
IS_MAPPING_BUG: NO
IS_LEGITIMATE_ZERO_WIRE_CASE: YES, positively demonstrated for all four nets
FILES_CHANGED: Listed in section 9; source hashes bound in receipts
TESTS_ADDED: Focused classification/fail-closed/cache tests; actual four-net
             extraction and preserved-trace reproduction also pass
S38584_ACTIVITY_STATUS: QUALIFIED; complete original simulation reused
S38584_E: 1783229997.7849805
S38584_H4: 2320.4008376039997
S38584_H8: 796.92240403
S38417_COLD_SEARCH_STATUS: NOT_STARTED
S38584_COLD_SEARCH_STATUS: INTERRUPTED_NO_COMPLETION_RECEIPT
CANDIDATES_GENERATED: 97 exact evaluations in partial lane;
                      0 completed preselected candidate packages
PHYSICAL_QUALIFICATION_STATUS: NEW_CANDIDATES_NOT_STARTED
UNSEEN_DESIGN_CAMPAIGN_STATUS: INCOMPLETE; interruption/resource diagnosis
NEW_SCIENTIFIC_RESULT: Both large external-reference activity measurements
                       qualify; no new routed PACT improvement established
NEXT_BLOCKER: Interrupted execution; very low host C: disk headroom
NEXT_ACTION: Preserve partial run, restore execution/storage headroom, finish
             unchanged cold searches, preselect, route/FAN/measure, then Gate 9
```
