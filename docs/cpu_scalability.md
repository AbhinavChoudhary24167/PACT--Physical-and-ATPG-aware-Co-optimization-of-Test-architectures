# CPU scalability development

This work preserves the PACT formulation, K=2, seed 11, epsilon lanes,
balanced weights, Boolean depth bound, frozen geometry, ATPG workload,
physical gates and exact measured C×N/H4/H8 definitions. Historical campaigns
are immutable. New receipts use `results/pact_cpu_scalability_20261005/`;
raw activity uses the corresponding new namespace in configured experiment
storage. No GPU work, new objectives or parameter tuning is included.

## Evaluator

`candidate_stateful.State` and its unpacked independent `reference` remain
available as oracles. Stage-B now defaults to `cpu_incremental.State`; callers
can explicitly supply the original `state_type` for development comparisons.
The original evaluator/search sources are preserved with byte hashes in the
new run's `oracle/` directory. Gate 0 records the clean Windows Git baseline,
dedicated branch, Linux toolchain and hardware. WSL Git reported six existing
Markdown line-ending differences; the recorded historical byte inventory is
checked independently of Git's platform-specific line-ending filters.

The CPU evaluator uses the unchanged source-to-H8-bin mapping. Each tile's
cycle column is contiguous. Updates traverse deterministic sorted changed
sources. Eight-cycle packed blocks whose waveform and capacitance agree are
skipped; capacitance changes still evaluate their complete required cycles.
Exact integer transition totals include nets with zero capacitance. Only dirty
tile totals/peaks and their parent H4 cells are reduced. H4 retains the same
four H8 cells and addition order. E's regrouped reduction is checked under the
registered `rtol=1e-9, atol=1e-6` evaluator policy, rather than claiming all trial
floating-point sums are bitwise identical.

A transaction saves each affected tile once, plus prior wave references,
capacitances, energies, integer transition totals, orders, diagonals,
endpoints and reduction state. Rejection restores these values directly.
Bitwise state hashes cover the full field, packed waves, orders, locations,
diagonals, electrical state, cached transition totals and score. This avoids
replaying every changed source and avoids inverse-update roundoff leakage.

## Reproduce the development witness

Use the recorded Linux environment with NumPy, SciPy, Numba and pytest.
Set `OMP_NUM_THREADS=1`, `OPENBLAS_NUM_THREADS=1`, `NUMBA_NUM_THREADS=1` and
include `src` and the installed optimizer dependencies in `PYTHONPATH`.

```sh
python scripts/pact_cpu_scalability.py freeze
python scripts/pact_cpu_scalability.py profile --backend oracle --evaluations 128
python -m pytest -q tests/unit/test_cpu_incremental.py
python scripts/pact_cpu_scalability.py profile --backend incremental --evaluations 128 --label _sparse
python scripts/pact_cpu_scalability.py compare
```

These are fixed-evaluation development witnesses, not historical campaign
reruns. Output files are exclusive-create; preserve previous runs and choose
a new namespace when repeating a development witness. The current witness
uses the unmodified Stage-B loop with explicit state types, identical frozen
s35932 inputs and independent retained-candidate replay. cProfile supplies
allocation/copy and Python call attribution alongside evaluator phase timers.
Native Numba time is charged to its Python caller; those call timings do not
claim a separately isolated native-dispatch overhead or additive exclusive
subphases.

## Exact activity

The selected backend is an Icarus VPI collector that follows Icarus VCD's
settled timestamp emission. It samples dirty scalar nets at read-only
synchronization, uses the final cycle marker, excludes initialization/capture
windows, preserves aliases and rejects active unknowns and uint8 overflow.
It emits all mapped per-net/per-cycle transition counts in a compressed binary
stream. Dimensions, exact net order, gzip integrity and a successful completion
footer are mandatory. A footer alone does not qualify a run: successful
functional load/capture/unload checks and independent FF transition replay are
also required.

Compact analysis retains the existing capacitance/missing-static-net policy,
scope definitions, per-cycle statistics, percentile populations and first-peak
tie rules. It uses 1024-row subsets and a temporary memory-mapped count array
to bound resident scratch. The old full VCD parser remains the oracle.
Equivalence compares every complete transition value, every source total,
all scope statistics, spatial maps and E/H4/H8 with `rtol=atol=1e-10`.

```sh
python scripts/pact_cpu_activity.py --source /path/to/qualified/design/role
python scripts/pact_cpu_activity.py --source /path/to/blocked/design/role --purpose continuation
```

Every continuation declares a timeout regime: normal ceiling 7200 seconds;
diagnostic ceiling 14400 seconds. `--timeout` may lower the selected ceiling.
The record includes configured timeout, regime, stages, workflow wall/CPU/RSS,
simulator time, trace bytes, completion and termination reason. Partial activity
is never a scientific measurement. Runs are sequential with one simulator,
one Python worker, native thread counts fixed at one, and no concurrent physical
jobs. Internal evaluator threading is not implemented.

The optional `cpu_reference.reference` bounds the original independent unpacked
oracle to one complete pattern at a time. It computes every original Boolean
state and spatial field, adds pattern energies and takes maxima over every
pattern's H4/H8. On the frozen s35932 initial reference the full and bounded
scores are bit-identical. Whole-worker RSS decreases from 1,321,484 to 275,472
KiB, while oracle time increases from 11.150 to 16.800 seconds. This is a memory
tradeoff, not a reference-computation speedup. Cold-start search accepts explicit
state/reference hooks; its original defaults and scientific configuration remain.

## Large-reference continuation and scientific stop

Both new reference runs use normal 7200-second workflow ceilings and the original
frozen physical/stimulus inputs. s38417 REF_B2 qualifies after 1013.712 seconds;
its complete compact trace is 374,107,061 bytes. This recovers reference activity,
not a completed candidate search/qualification campaign.

s38584 REF_B3T finishes simulation in 1029.984 seconds, including functional
load/capture/unload checks. Its complete compact trace and independent check of
270,452,308 FF-cycle values pass. Analysis then rejects four switched nets that
appear in SPEF NAME_MAP but have no extracted D_NET section: net654, net655,
net714 and net719. Their zero sink-pin capacitance does not override the frozen
analyzer's missing-switched-net prohibition. E/H4/H8 remain unavailable.

The experiment is stopped under the requested scientific policy. No cold search,
candidate routing/ATPG/activity or further unseen expansion was launched. The
SHA-bound `scientific_stop.json` preserves the diagnosis; the continuation
launcher refuses further runs while this stop exists. No missing capacitance is
filled, and no historical record is changed.

## Authorized bounded missing-SPEF repair

The subsequent continuation request authorizes an evidence-driven repair of
the s38584 condition. `src/pact/activity/spef_evidence.py` keeps the original
normal extraction path and permits an explicit fallback only with SHA-bound
ODB/netlist/Liberty/extractor evidence. The implemented proof is conservative:
one valid driver, no sinks/ports, no regular/special/global wire, no RC objects,
exact logical/physical source identity and an independently reproduced omission.
Missing geometry for a net with sinks, mismatched identity, unknown pin load or
incomplete extraction evidence remains a hard failure. Wire zero is combined
with the independently known pin contribution; no measured counts are removed.

`scripts/pact_spef_evidence_export.py` inspects both the frozen routed ODB and an
isolated extraction snapshot. For the four s38584 nets, each is a dangling
BUF_X1/Z output with no sinks or routing. Re-extraction with the frozen binary
and parameters reproduces every existing extracted capacitance exactly and
again emits no D_NET or RC objects for these nets. The parser and mapping agree;
no upstream defect is established. The local OpenRCX source also gates D_NET
serialization on capacitance nodes; its checkout revision differs from the
installed binary, so the actual frozen-binary reproduction is the decisive
evidence.

The opt-in compact analyzer emits `missing_spef_diagnostics.json`, explicit
`SPEF_ZERO_WIRE_FALLBACK` CSV rows, counters and source bindings. Without an
evidence argument, the original missing-switched-net failure remains. Reanalysis
reads the old uncompressed cache only after checking every byte against the
complete compressed count stream, including its footer/CRC. The completed
s38584 simulation and s38417 measurement are not repeated.

The actual s38584 reanalysis qualifies E=1783229997.7849805,
H4=2320.4008376039997, H8=796.92240403: 16029 normal switched nets, four qualified
fallbacks and zero mapping/extraction/unresolved errors. Sixteen focused tests
cover the new classifications and directly touched storage path; the actual
four-net reproduction and complete independent FF replay also pass.
`spef_patch/qualification.json` and `stop_resolution.json` supersede the stop
without rewriting its failure evidence. The gate only allows continuation while
the qualified patch sources and repaired reference receipt retain their hashes.

New cold searches use `scripts/pact_cpu_continue_search.py`; candidate physical,
FAN and compact activity use `scripts/pact_cpu_qualify_continuation.py`. Both use
the separate continuation namespace, original frozen references/settings and
one heavy job group. Original cold-start defaults remain available, and retained
candidate scores are independently replayed by the bounded original oracle.
