# End-to-end scan integration

## Representation audit (before implementation)

`ScanCell.name` is the canonical physical instance identifier. The identity-map
records bijectively connect `logical_ff`, `atpg_signal` and `physical_instance`.
DEF coordinates (component origins in microns) and clock domains are fixed.
`ScanChain.chain_id` identifies a chain; `cells[position]` runs from SI (position
zero) to SO (last position). `scan_in` and `scan_out` identify boundary ports.

The transformation is explicitly `old_chain[k][position] -> physical_instance
-> new_chain[k][position]`. Chain identities, endpoints and per-chain capacities
remain fixed; FFs can move across chains. Canonical architecture JSON already
hashes placement, clock domains, endpoints and ordered membership.

FAN BASIC_SCAN is **parallel state**, not a serial scan stream: its seven fields
are PI1 | PI2 | PPI | SI | PO1 | PO2 | PPO. PPI and PPO share the named pseudo
primary input header. The verified identity map connects those names to FFs.
PPI is the load state, PPO the expected captured response. The existing optimizer
uses binary PPI only, zero initialization and carried loads, with no capture or
final unload. Integration must preserve PI1/PO1 and PPO separately; it must not
claim that the optimizer activity model simulates functional capture.

Repository inputs are seed-11 B0 K=2 architectures, placed DEF, mapped FAN
patterns, and the repaired placed graph. The first SI/SO path can contain
transparent buffers; additional SO ports are direct. The generic optimizer
adapter supports arbitrary K with explicit direct endpoints. The existing
`phase0c_rewire_odb.py` consumes canonical architecture JSON and a frozen original
single-chain placed ODB, changes FF SI and the inherited SO buffer input, adds
ports, and asserts unchanged functional nets and placement. It does not consume
an already split K-chain ODB. Its explicit qualified port convention is
`test_si`, `test_so`, followed by `test_si_i`, `test_so_i`. Architecture JSON uses
logical `test_si_0`/`test_so_0` for chain zero: the integration patch records the
explicit aliases to physical `test_si`/`test_so`. This is a documented adapter
binding, not FF-name normalization.

The selected output is `result.json:selected`, hash-bound to
`optimized.architecture.json`. `supplied.architecture.json` is the original
optimizer topology. These files avoid copying indexed arrays by hand.

## Integration protocol

The emitted serial workload uses a common shift clock. Every chain shifts on
every cycle. Short chains receive leading zero padding before tail-first load
bits, so all chains finish at the same cycle. Unload samples SO **before** each
shift; only the first chain-length samples are valid. This differs intentionally
from the historical activity simulator's implicit per-chain stopping convention:
no undocumented clock gating is required by the implementation workload.

X is a symbolic unknown on load and a compare mask on unload; it is never filled.
Exact symbolic equality is checked as well as known bits. Capture is a distinct
BASIC_SCAN phase. Nonempty SI/PI2/PO2 (sequential/two-frame protocols) are rejected
until their timing semantics are implemented. Scan compression, inversion,
lockup latches and multiple clock domains are not inferred.

## Running the pipeline

From the repository root, reuse the saved qualified 60-second recommendation:

```bash
python scripts/pact_integrate.py --design s5378 \
  --optimizer-run reports/working_solver/final/s5378 \
  --output reports/end_to_end/s5378/my_run
```

The default qualified inputs are seed 11, K=2. Explicit `--placement`,
`--scan-topology`, `--patterns`, and `--identity-map` paths must agree with their
qualification hashes. Existing output directories must be empty: earlier runs
are never overwritten. The selected architecture, supplied topology, dimensions,
wire allowance and local ceilings are checked before export. Historical solver
results did not store raw input hashes; reuse is restricted to the named final
run directories, checked against the preserved qualification freeze, exact B0
topology, selected architecture hash, and qualified route identity. This is
reconstructed provenance, not a claim that old result.json contained those hashes.

To apply the patch and run existing FAN simulation, use Linux/WSL with the
qualified tools (s9234 uses the physical block name `s9234f`):

```bash
python scripts/pact_integrate.py --design s5378 \
  --optimizer-run reports/working_solver/final/s5378 \
  --source-odb /root/pact-deps/OpenROAD-flow-scripts/flow/results/nangate45/s5378/phase0b_s11_B0/3_place.odb \
  --fan-root /root/pact-deps/FAN_ATPG \
  --output reports/end_to_end/s5378/my_applied_run
```

The command emits:

- `scan_permutation.json`: both position maps, heads/tails, chain lengths and hashes.
- `scan_topology_before.json`, `scan_topology_after.json`: canonical architectures.
- `implementation_patch.json`: concrete SI/Q/SO links and explicit endpoint aliases.
- `implementation_patch.py`: executable OpenROAD adapter with hash checks.
- `patterns_original.json`, `patterns_remapped.json`: named ports, PI/PO headers,
  load/unload vectors, capture metadata, common-clock timing and X policy.
- `patterns_recovered.pat`: FAN workload reconstructed by independent cycle replay.
- `replay_report.json`, `physical_handoff.json`, `summary.json`, `manifest.json`.
- With `--source-odb`: `implementation.odb`, compressed `implementation.odb.gz`,
  and `implementation_applied.json` with source/output hashes, actual source FF
  placement verification and unchanged-functional-net assertions.
- With `--fan-root`: original/recovered fault-simulation logs, coverage/count
  comparison and a separately recorded detailed fault-list probe.

FAN simulation runs on the original functional netlist with PPI recovered from
the emitted serial workload. This tests permutation-induced workload changes;
it is not timing simulation of the routed database. PI1/PO1/PPO remain preserved.
The supplied FAN build successfully simulates coverage but crashes (SIGSEGV)
while reporting detailed fault identities; the result distinguishes coverage
PASS from detected-fault-set BLOCKED and leaves lost/new fault sets null.

Without `--optimizer-run`, the same command invokes the unchanged optimizer.
`--time-limit` (alias `--time-budget`) is configurable and defaults to 60 seconds;
`--wire-allowance` defaults to 0.10. New runs record input hashes for future reuse.
No search was run for this integration milestone.

For arbitrary K, provide explicit placement/topology/FAN/identity inputs and
`--adapter direct`. A fresh solve also requires `--solver-input` in the existing
optimizer bundle format, with exactly matching architecture and binary target
states. For reuse, supply a run with `integration_inputs.json` bound to those
exact files, and use the optimizer result's design name. Direct implementation
requires an existing ODB with exactly that original topology, SI/Q pins and
direct boundary ports. Buffered or inverted links fail the topology check.
The generic remap/replay path supports arbitrary nonempty fixed capacities,
including unequal lengths and X; the frozen optimizer still requires binary PPI.
Generic direct physical application is implemented but not benchmark-qualified
by this milestone; the three real ODB applications use the qualified adapter.

Verify a delivered bundle without simulation or external tools:

```bash
PYTHONPATH=src python -m pact.integration.verify_artifacts \
  reports/end_to_end/s5378/integration_v1
```

## Physical handoff

The real physical consumer is OpenROAD's `3_place.odb`. The generated patch
materializes it through the existing `phase0c_rewire_odb.py`; functional D,
clock, enable, other functional nets, masters, coordinates and orientations
remain unchanged. The inherited scan-output buffer input is the only non-SI
instance pin changed. The buffer adds no inversion or scan state.

To apply a delivered patch on a machine with its qualified source database:

```bash
ROOT="$PWD"
RUN="$ROOT/reports/end_to_end/s5378/integration_v1"
openroad -python -no_init -exit "$RUN/implementation_patch.py" \
  --repository "$ROOT" \
  --source /root/pact-deps/OpenROAD-flow-scripts/flow/results/nangate45/s5378/phase0b_s11_B0/3_place.odb \
  --output "$RUN/new_implementation.odb"
```

The target ODB must not exist. Alternatively decompress the delivered archive.
To launch a **new** route, stage the emitted ODB and source SDC as follows. These
commands were not run in this milestone because the exact selected orders were
already routed and hash/order-verified with zero DRC.

```bash
ROOT="$PWD"
DESIGN=s5378
BLOCK=s5378                  # s9234f for s9234; s15850 for s15850
RUN="$ROOT/reports/end_to_end/$DESIGN/integration_v1"
FLOW=/root/pact-deps/OpenROAD-flow-scripts/flow
VARIANT=pact_integration_s11
WORK="$RUN/orfs"
DEST="$WORK/results/nangate45/$BLOCK/$VARIANT"
mkdir -p "$DEST"
gzip -dc "$RUN/implementation.odb.gz" > "$DEST/3_place.odb"
cp "$FLOW/results/nangate45/$BLOCK/phase0b_s11_B0/3_place.sdc" "$DEST/3_place.sdc"
CONFIG="$ROOT/experiments/phase0/${DESIGN}_orfs/config.mk"
# s15850: CONFIG="$ROOT/experiments/phase0b/s15850_orfs/config.mk"
cd "$FLOW"
make -o "$DEST/3_place.odb" -o "$DEST/3_place.sdc" \
  DESIGN_CONFIG="$CONFIG" FLOW_VARIANT="$VARIANT" WORK_HOME="$WORK" \
  GRT_SEED=11 NUM_CORES=2 OPENROAD_EXE=/usr/bin/openroad YOSYS_EXE=/usr/bin/yosys route
openroad -python -no_init -exit "$ROOT/scripts/phase0d_verify_routed.py" \
  --routed "$DEST/5_2_route.odb" --architecture "$RUN/scan_topology_after.json" \
  --frozen-def "$ROOT/artifacts/raw/phase0b/placements/$DESIGN/s11/placed.def" \
  --output "$RUN/new_route_verification.json"
```

Inspect ORFS detailed-route DRC and structural verification before calling that
new route qualified. Integration itself does not automatically launch routing.
