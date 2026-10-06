# PACT_GATE10A_PRACTICAL_IMPACT_VALIDATION

This separate prospective measurement campaign asks the OpenROAD maintainer's
question: **“What is the practical impact of the 2.4% reduction? Does this
translate in IR-drop or thermal hotspot improvement?”**
Motivation: https://github.com/The-OpenROAD-Project/OpenROAD/discussions/11478#discussioncomment-18767526.
The question is supplied by the requester; the discussion could not be fetched
by the web reader during preparation. No empirical answer is assumed.

## Frozen parent and execution boundary

Initial checkout was clean at e5dbf26721f3e0e17aac9d3569691b322969b4c0.
The published Gate 09 merge is 53ebab37fd76970d7c5e676b0caec13c7c16296e;
its tree is identical to the initial checkout. Gate 09 scientific execution was
sealed at e8c2f5da298f073c231b5798561ffadce6355ec2. Its files and external raw
evidence remain immutable. All new work uses
`development/gate10a-practical-impact-validation`.

This document, methodology, protocol, selected architectures, verified reuse
manifest and tool provenance must be committed before the first power or IR
solve. Read-only inventories and synthetic parser/statistic tests are allowed
before that commit. The commit receipt binds those files and precedes execution.
Outcome-dependent changes to metrics, assumptions, architecture selection or
thresholds are prohibited. Implementation defects may be repaired with preserved
failed receipts and evidence that the frozen definitions were not changed.

PACT, K=2, seed 11, objectives, search operators, epsilon, candidates, primary
candidate selection, topology, workloads, placement and routed signal geometry
are frozen. No search, ATPG, placement, routing, extraction, or simulation rerun
is admitted when retained evidence supplies the required information.

## Architecture set and comparisons

The complete selected set is b14_opt {B3T, CS_C1, CS_C3, B5} and
b15_opt {B2, CS_C1, CS_C2, CS_C3, B5}. No optional B2 is added to b14.
The co-primary architecture comparisons are CS_C1 versus B3T for b14 and
CS_C1 versus B2 for b15. b14 CS_C3 and b15 CS_C2/CS_C3 are prespecified
secondary comparisons; B5 is the activity-oriented, higher-wire-cost control.
Every selected record is reported even if held or failed; incomplete records
never participate in numeric comparisons.

The b14 Gate 09 observations to test are approximately +0.044% routed scan
wire, −0.357% E, −1.708% H4 and −5.688% H8 for CS_C1 versus B3T, and
approximately −5.7% H8 for CS_C3. These are frozen proxy observations, not
evidence of power-integrity benefit. Full-precision Gate 09 values are consumed.

## Activity-derived power and static PDN model

Use the hash-matched Gate 09 OpenROAD binary and Nangate45 typical Liberty,
the frozen routed ODB, SPEF, 10 ns clock (100 MHz), 1.1 V and scan-shift mode.
Retained exact settled transition counts cover all qualified load/unload shift
cycles; initialization, capture and functional input setup were excluded.
Gate 09 deliberately omitted VCD. No claim of VCD-based power is made.
Regenerate per-net totals from the verified compact counts; unbound derived
CSVs must not be treated as historically hash-qualified evidence.

Annotate each retained data-net driver pin (or input port) with density
N/(number_of_shift_cycles × 10 ns), in transitions/ns, using the runtime
`set_power_activity` API. Non-clock duty is fixed at 0.5 because retained counts
do not contain logic-high occupancy. Zero-transition nets have zero density.
The scan clock is 0.5 duty and two transitions per 10 ns; every retained clock
net/driver must be explicitly covered or verified by clock propagation. Scan
enable is fixed asserted; unused controls/constants are explicitly inventoried.
Report annotation coverage, defaults, tied nets and unsupported pins; incomplete
activity processing is an admission failure, not a physical result.

Retain the qualified placed SDC's input slew/output load constraints and the
frozen technology RC setup. Normalize its clock explicitly to CK period 10 ns,
waveform {0 5}, and use propagated-clock timing. Explicitly cover the retained
clock closure at density 0.2 transitions/ns and duty 0.5; scan enable receives
case analysis 1, density 0, duty 1. Unmeasured input/global fallback density is
zero, accompanied by a complete inventory. A fallback cannot replace an
active data driver lacking qualified counts.

Read original extracted parasitics without re-extraction. Preserve per-instance
internal, switching, leakage and total power and full design power. Dynamic
power means internal plus switching. Power includes the original clock network;
also report clock/non-clock partitions where supported. Timing/slew and Liberty
state-dependent internal/leakage models remain an approximation at fixed duty;
zero-delay settled counts do not resolve physical glitches.

Reuse original VDD/VSS PDN geometry. Primary solve is **VDD static supply drop**,
not ground bounce or combined VDD/VSS drop. Use 1.1 V sources at both ends of
each original top-layer horizontal VDD stripe: x = xMin + width/2 and
xMax − width/2, y = stripe center, square source size = stripe width.
Coordinates are derived deterministically from the frozen geometry. No package
resistance is added. Supply locations, geometry hashes and layer resistance
settings must match within each design. No PDN tuning, decap insertion,
placement movement or signal-routing change is allowed.

Use OpenSTA's estimated instance total power as the PDNSim load (explicit
per-instance overrides allowed solely to convey those exact values).
Preserve solver voltage and segment-current files, connectivity reports and
raw logs. Voltage drop = 1.1 V − returned voltage. EM segment-current outputs
are amperes. Report current density only if physical width AND thickness are
available from qualified technology data; never infer a cross-section.

## Qualification before comparative execution

Use frozen b14 B3T for the representative smoke. Run the identical nominal
power/IR pipeline twice; require matching sorted numeric power/voltage/current
records within abs 1e−12 in SI units and rel 1e−8. With all else fixed,
run non-clock density multipliers 0 and 2 as qualification controls and verify
the non-clock switching component is linear in density within rel 1e−6 and
abs 1e−12 W. Clock activity remains fixed. Controls are not architecture results
and cannot change the model. Verify nonnegative finite power, supply
connectivity, complete powered-cell/terminal matching, FF population 245/449,
source/architecture/workload/placement hashes, parser completeness, full
coordinate containment and no unexplained tool errors. If a supported API
cannot implement this method, seal the invalid-method diagnosis; do not silently
substitute a more favorable model.

## Frozen metrics and materiality

Report worst, mean, median, p95 and p99 drop over powered instance supply
terminals, with the population stated; collapse multiple VDD terminals per
instance by their worst drop for instance statistics. Retain all terminal rows
as well. Report counts/fractions at fixed strict drop thresholds of 1%, 3% and
5% of 1.1 V (11, 33, 55 mV). Report affected occupied-grid regions separately;
their bin area is a coarse extent indicator, not interpolated physical hotspot
area. Report hotspot locations, max and p95/p99 absolute segment current and
complete current maps where available. There is no process-specific EM limit.

A comparison has material PI benefit only when BOTH worst and instance p99
drop decrease by at least 1% relatively AND 0.1 mV absolutely, and neither
dynamic power nor peak absolute segment current regresses by more than 1%.
Low/modest physical cost is ≤2% routed scan-wire increase. These thresholds
are study decision thresholds, not manufacturing or signoff limits. Exact
deltas and smaller effects are reported even when below materiality.

## Spatial statistics and coordinate mapping

Use the original die bounds, lower-left origin, equal 4×4 and 8×8 grids, and
row-major index y×resolution+x. Interior boundary points enter the upper bin;
outer maximum points enter the last bin. PACT assigns whole ground-plus-sink
capacitance to the driver cell origin, or external port center. Preserve this
transform; never move bins to align hotspots. Powered-cell and IR terminal
results map to the same cell origin for the primary comparison. Terminal
physical coordinates and segment midpoints remain available separately.

For every architecture/grid, primary x is regional summed C×N per measured
shift cycle, y1 is summed regional instance dynamic power, y2 is maximum
regional instance VDD drop. The primary domain contains bins with non-physical
Liberty-powered instances. Preserve ALL 16/64 values and support counts;
empty die regions cannot inflate zero-zero agreement. Missing values are
missing, never zero. Incomplete occupied domains invalidate the primary
statistic; any finite-subset calculation is explicitly diagnostic.

Always report BOTH Pearson and Spearman (average ranks for ties), population
size, and undefined/constant/insufficient reasons. Primary hotspot IoU uses
top ceil(occupied_bin_count/4) bins, descending metric with ascending bin ID
tie-break. Constant vectors yield undefined hotspot agreement. Do not select
the best statistic. Peak-cycle H4/H8 maps versus averaged/static maps are
prespecified secondary temporal-mismatch analyses. The activity-to-power
comparison is partly model-coupled and is not an independent validation.
No inferential p-values or claims of generalization from two designs are made.

Spatial proxy correspondence is observed when primary/reference mean-activity
versus IR Spearman is ≥0.5 at BOTH grids in BOTH designs (all four records).
Report exceptions and peak-map statistics separately; passing this criterion
does not establish transient-H4/H8 predictive validity.

## Classification and development decision

`PACT_GATE10A_PHYSICAL_IMPACT_SUPPORTED`: both co-primary comparisons meet
material PI benefit at ≤2% scan-wire cost. `PARTIAL_PHYSICAL_IMPACT`: at least
one prespecified PACT comparison meets material PI benefit, but the supported
criterion is unmet. `PROXY_CORRELATION_ONLY`: no such material PACT benefit,
but the complete spatial correspondence criterion passes.
`NO_MATERIAL_PHYSICAL_IMPACT`: complete admissible evidence meets neither.
`INCONCLUSIVE`: missing/invalid evidence prevents those distinctions. Prefix
all classifications with `PACT_GATE10A_` in machine records.

Recommend CONTINUE for supported material benefit. For partial evidence,
recommend CONTINUE only when at least one co-primary comparison meets benefit
at ≤2% cost and neither co-primary has material adverse drop (same symmetric
thresholds); otherwise recommend PIVOT as future work. Recommend PIVOT for
correlation-only evidence. Recommend FREEZE for no material physical impact.
For inconclusive evidence, HOLD algorithm development pending measurement
qualification; insufficient evidence is not scientific support for a pivot or
permanent stop. No future objective or next gate is implemented here.

## Resources, limitations and stop policy

Admission checks apply before every process: a single EDA job, one thread,
host available memory ≥768 MiB, WSL available memory ≥1 GiB and scratch free
space ≥4 GiB plus the estimated job output (≤512 MiB per architecture).
Scratch is a fresh Gate 10A namespace under this workspace; stream gzip/counts,
reuse raw input locations, retain receipts immediately, and remove no unique
evidence. Record command, tool/hash, environment, CPU/wall time, peak RSS and
output disk bytes. Resource holds do not change methodology or count as losses.

Thermal: **THERMAL_IMPACT_NOT_EVALUATED**. No qualified immediately available
thermal flow is included. No thermal benefit is inferred from H4/H8 or watts.
This gate measures cycle-resolved activity, averaged approximate power and a
static PDN solution separately. It cannot establish transient droop, physical
glitches, signoff power integrity, package/ground behavior or thermal hotspots.

FAN_ATPG workloads are reused; execute no FAN stage. Activate an independent
minimal repair track only if a necessary FAN stage proves blocked by a defect.
Continue qualified independent work when one architecture/lane is held. Stop
shared science only for unestablished frozen identities, corrupted workloads,
incomparable common backend or invalid common power/IR method; preserve a
complete diagnostic seal. A report draft must directly answer the maintainer,
distinguish established/observed/approximate/not-evaluated findings, and remain
unposted. Merge/publication occurs only after completed evidence and review.
