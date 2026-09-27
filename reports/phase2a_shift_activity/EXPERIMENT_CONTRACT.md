# Phase-2A experiment contract

Frozen before new activity measurement. Question: across frozen s5378, s9234 and
s15850 architectures, does H_eff8 correctly rank or track independently reconstructed
and physically weighted post-route scan-shift switching behavior?

Seed 11, K=2; all input hashes, architecture hashes, H_eff8, pattern counts and
archived stuck-at coverage are in architecture_set.json, test_quality.json and
provenance.json. No optimization, ATPG generation, placement or route runs.
Use P/A/J50/T plus already-selected Phase-1 balanced/activity_extreme for s9234
and s15850. For s5378 include all FIVE previously qualified Phase-0D candidates,
including dominated ones, with original hash labels; no retrospective balanced
label is invented. B0/R and physical_extreme are omitted to retain the requested
focused comparison. Architecture set is immutable after measurement.

Reuse FAN parser/PPI bijection and parallel_schedule, and check against
verify_parallel_schedule for EVERY pattern with carried state and scan-out.
Start all FF states at zero; load reverse target order, shorter chain gets leading
zero padding but all FFs clock on every cycle. Carry loaded state, no capture,
no extra final unload. Record padding and first-L scan-out versus padding tail.
Do not call H_eff8/activity implementation, its weights or spatial kernel.

Physical hierarchy: use qualified extracted capacitance if present. Preliminary
inventory finds no SPEF under existing Phase-1 or ORFS Nangate45 results. Inspect
ODB RSeg/CapNode evidence too. Without qualified parasitics, the preregistered
fallback is SUM(toggle_FF * routed wire length of all unique nets driven by its
Q or QN, through BUF/CLKBUF/INV branches). Include whole actual net trees and
functional sinks, not Q-to-SI distance. Stop at nontransparent logic; do not
infer internal combinational activity. Count shared nets once; reject competing
FF owners, missing routed wires, changed coordinates/inventory, or failed scan
proofs. QN inversion preserves transition counts. Audit source pins and fanout.
No pin capacitance, layer-dependent capacitance, vias, buffer internal energy,
clock/SE/PI driven nets or coupling energy is represented by this fallback.
Call its unit micrometre-transitions, NEVER energy or power. Physical ENERGY
portion remains incomplete without qualified electrical extraction.

Spatial rule: fixed 10x10 equal bins over each frozen DEF DIEAREA, lower-inclusive
boundaries (outer maximum clamped). Assign FF-driven load to the routed FF origin,
not routed segment locations. Per cycle calculate raw and wire-weighted bin sums;
local activity is every wholly-contained 2x2 adjacent-bin sum (81 windows), equal
weights, no convolution, occupancy or fanout normalization. Peak over all cycles
and bins/windows. This localizes drivers, not distributed wire dissipation.
Report total/mean/peak/p95 cycle activity, raw and weighted spatial peaks.

Statistical plan: within-design Spearman (average tied ranks), Kendall tau-b,
secondary Pearson, and exact ascending rankings, for raw total/peak, weighted
total/peak, raw/weighted bin and 2x2 local peaks. H values rounded to 9 decimal
places solely to avoid floating point false tie distinctions. Exact two-sided
Spearman permutation p-values over all architecture-label permutations per design
are descriptive (selected architectures are not independent random samples;
multiple endpoints, no confirmatory significance claim). Pooled coefficients
use within-design mean-normalized quantities ONLY, with equal design weight;
also report pooled within-design ranks. No raw physical-scale pooling.

Pairs: s9234 T/balanced, J50/activity_extreme, A/activity_extreme;
s15850 T/balanced, J50/balanced, A/activity_extreme; s5378 P/75ea663523d9,
T/75ea663523d9, J50/1f1a3a458946, A/1f1a3a458946. Delta=PACT-baseline;
ties explicitly distinguished from correct/incorrect direction.

Classification rule before measurement: strong confirmation requires correctness,
independent physical weights, Spearman >=0.7 for weighted total AND local peak in
every design, and correct direction in every preregistered pair for both endpoints.
Failure if weighted total AND local peak have nonpositive Spearman in all three
designs. Otherwise partial/design-dependent evidence, with negative endpoints
explicitly reported. These descriptive thresholds do not imply significance.
No objective or architecture tuning follows a failed result.

Large/transient artifacts, cycle traces and extracted net inventories live only
under D:/PACT_EXPERIMENTS/results/phase2a_shift_activity. Compact reports in repo.
Focused correctness tests first, full repository regression after implementation.
