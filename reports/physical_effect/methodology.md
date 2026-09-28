# Frozen physical-effect methodology

Established before the first activity result. Only seed 11, K=2 and the exact
historical recommendations are used. The experiment order is s5378, s9234,
s15850. No objective, architecture, solver setting or test pattern is tuned.

## Experiment and measurement

The root manifest freezes nine routed archives, canonical architecture and scan
order hashes, original placed database/netlist, placement, identity map, FAN
workload, serialized workload, original SDC, selected PACT hash and qualification
report. Each exact ODB is exported to Verilog by OpenROAD. Its netlist, mapping,
stimulus and SPEF hashes are recorded before simulation. PACT uses the existing
integration remapped load/unload vectors byte-for-byte in value; baseline vectors
are serialized from the identical named logical FAN states. These are checked
against the source workload before running any simulation.

Icarus Verilog executes the whole routed netlist with the installed Nangate45
gate library with its `TETRAMAX` functional-mode define, which omits timing
helper feedback drivers. Specify blocks are disabled (the default); no SDF is applied.
This is zero-delay logical gate simulation, not accurate hazard activity.
The scan clock period is 10 ns. Initialization shifts zeros through every chain
and is excluded. For each pattern: apply PI1 outside measurement, load the
remapped PPI with SE=1 on the common clock, check every FF Q, perform one
functional capture with SE=0, check every captured FF Q against PPO, then unload
with zero scan input and check SO before each edge. Capture and all PI/SE setup
activity are excluded by an explicit cycle marker. Load and unload are measured
separately and together. Shorter chains use leading zero padding for load;
unload compares only their valid chain-length samples. No clock gating is added.

VCD records DUT nets at timestamps and an explicit signed cycle marker. Count
only binary transitions during measured shift windows. Reject X/Z changes in
the measured nets, missing net mappings, missing cycles and hash mismatches.
At a timestamp, the final marker defines the window regardless of VCD record
order. This includes SI changes and sequential/combinational propagation in
each shift cycle. Zero-delay event ordering cannot establish physical glitches.
Raw VCD, SPEF, ODB and simulator executables are ignored; generation commands,
hashes, logs, net/cycle counts and compact count arrays are retained.

The installed OpenROAD Verilog writer omits input aliases when an added BTerm
name differs from its dbNet name. The adapter adds exactly those input
connections from the independently exported ODB map (for example
`phase0c_scan_in_1 = test_si_1`). Raw and corrected netlists and hashes are kept.
Output aliases already emitted by OpenROAD remain intact. Physical-only
`TAPCELL_X1` instances have no signal pins and use an empty simulation module.
No functional cells, scan topology or routed geometry are changed.

## Electrical model

Mode A: OpenRCX extracts the exact detailed-routed ODB with existing Nangate45
`rcx_patterns.rules`, corner index 0, coupling threshold 0.1, cc_model 10,
context depth 5, version 1.0. Primary weight is extracted ground capacitance
plus actual Liberty sink-pin capacitance, in fF. Grounded capacitance includes
coupling terms below the extraction tool's 0.1 fF grounding threshold. SPEF incident coupling is
preserved separately, but excluded from the primary metric because its energy
depends on relative neighboring waveforms. No arbitrary wire-cap constant is
used. Missing capacitance on a switched net fails; missing extraction on a
static net is listed and excluded rather than assigned a physical constant.

Report sum(C_ground + C_pin)*N as **capacitance-weighted switching activity**, in
fF transitions. No voltage is assumed and no watts/joules are claimed. This
excludes internal cell power, short-circuit power, leakage and coupling energy.
It is not a full-chip power estimate or a signoff timing/power result.

## Scopes and spatial attribution

`scan_data`: every FF Q/QN net, transparent buffer/inverter descendants, and
scan-input transparent paths. This includes functional fanout loading on those
nets. `all_data`: all uniquely driven non-clock signal nets, including secondary
combinational activity. External input nets are included. Clock root CK and its
transparent descendants are explicitly excluded; power/ground and nets without
a unique source are enumerated separately. No identical clock activity is used
to dilute the comparison. The wider data scope prevents hiding secondary
activity behind the scan-only scope.

Use fixed 4x4 and 8x8 equal-area die grids for every architecture and design.
8x8 is the primary local comparison; 4x4 is a prespecified scale sensitivity.
Half-open bins include the die maximum in the last bin. Each whole net is
assigned to its driver cell origin, or to the input-port center for external
inputs. This is explicitly a **source-localized net switching proxy**, not a
distributed spatial power-density analysis. Entire routed capacitance is not
claimed to reside at the source; segment-level capacitance attribution is not
implemented. Both unweighted and weighted maxima are calculated over bins and
cycles. P95/P99 local values use the per-cycle spatial maximum population.

## Comparisons and decision

Report signed percentage changes against P (s5378/s15850) or T (s9234), and
against J50. Negative is reduced activity or cost. Total transitions, mean,
maximum, P95/P99 per-cycle activity and both local grids are retained for both
scopes. Routed scan path length is the qualified full-net path upper bound,
not exclusive scan-only metal length. Only timing/DRC linked to the exact
archive is reported. Existing M3/M5 values are read only after independent
measurements and are descriptive comparisons, never measurement inputs.

A strong positive classification requires improvement in total and spatial
implementation activity on the tested designs without unacceptable degradation.
Disagreement between metrics or designs is mixed; no positive physical effect
is inferred from M3/M5 alone. Functional-capture or artifact-identity failure
blocks an interpretable comparison until resolved. IR-drop is secondary and
requires a credible PDN supply boundary and characterized switching currents;
spatial activity alone cannot establish voltage drop.
