# Gate 10A practical-impact validation

## A. Executive classification

**PACT_GATE10A_INCONCLUSIVE**. Development recommendation: **HOLD**.

Incomplete or invalid required measurement evidence prevents the registered distinctions.

## B. External research question

“What is the practical impact of the 2.4% reduction? Does this translate in IR-drop or thermal hotspot improvement?”

The quoted 2.4% is the maintainer's historical question, separate from the full-precision Gate 09 values tested here. The [original comment](https://github.com/The-OpenROAD-Project/OpenROAD/discussions/11478#discussioncomment-18767526) was independently verified; the read-only verification is retained in `control/external_question_verification.json`.

## C. Frozen Gate 09 inputs

Published Gate 09 parent: `53ebab37fd76970d7c5e676b0caec13c7c16296e`. Preregistration: `b9869834a3479a57f256c83fa74a4617faab4af2`.
Frozen routed ODBs, original SPEF, exact load/unload counts and qualified FAN patterns were reused. No PACT search, ATPG, placement, routing, extraction or replay was rerun.

## D. Architecture selection

b14: B3T, CS_C1, CS_C3, B5. b15: B2, CS_C1, CS_C2, CS_C3, B5. Co-primary comparisons are CS_C1 versus the respective B3T/B2 reference.
The earliest completed admissible qualified nominal density-one run matching the shared qualified execution-source fingerprint is selected; zero/two-density controls and explicitly invalidated implementation attempts are excluded. Selection never uses architecture comparison values.

## E. Power/PI methodology

Nangate45 typical Liberty, 1.1 V, 10 ns scan period. Non-clock measured transition density is annotated with fixed duty 0.5; scan enable is asserted and clock activity remains fixed.
Dynamic power is OpenSTA internal plus switching power. PDNSim solves static VDD drop on the original PDN with ideal sources at both ends of each original top VDD stripe; no package resistance is included.

A common measurement-import repair assigns previously unassigned late-added buffer PG ITerms to the existing VDD/VSS nets in memory using exact ^VDD$/^VSS$ pin rules. Original routed ODB hashes are retained; COMPONENTS/NETS/PINS/VIAS and original PG shapes are checked unchanged. The PDN geometry is frozen while PG connectivity metadata is normalized identically across all nine architectures.

## F. Approximations and limitations

Cycle-resolved source-localized C×N activity, averaged activity-derived Liberty power and static VDD voltage drop are distinct quantities. The method does not establish transient scan droop, physical glitches, signoff PI, ground bounce, package effects or thermal behavior.
Fixed duty lacks measured logic-high occupancy; Liberty state/slew dependence is approximate. Activity-to-power correspondence is partly model-coupled. These two related benchmark families do not establish broad generalization.

## G. Artifact reuse

All nine derived activity CSVs are bound to full validated compact count traces, original mappings and SPEF. Every scientific run retains immutable input/output bindings and execution-source snapshots. Full spatial vectors are retained beneath `reports/gate10a/derived/`.

## H. FAN_ATPG status / repair status

Qualified Gate 09 patterns were reused; FAN_ATPG was not executed. The qualified existing repair identity is `4c253bfa613e5827f17c42a5fce8be7bea779e1e`.

## I. Power results

Power values are estimates under the fixed-duty model, in watts. Blank entries are unavailable evidence.

The CSV also retains the supported native OpenSTA Clock-category internal/switching/leakage/total watts and nonclock complements (design total minus Clock). These native library/timing categories are separate from clock versus nonclock activity annotations; the entire design power remains the PDNSim load.

| Design | Architecture | Status | Dynamic mW | Switching mW | Internal mW | Leakage mW |
|---|---|---|---:|---:|---:|---:|
| b14_opt | B3T | UNAVAILABLE | — | — | — | — |
| b14_opt | CS_C1 | UNAVAILABLE | — | — | — | — |
| b14_opt | CS_C3 | UNAVAILABLE | — | — | — | — |
| b14_opt | B5 | UNAVAILABLE | — | — | — | — |
| b15_opt | B2 | UNAVAILABLE | — | — | — | — |
| b15_opt | CS_C1 | UNAVAILABLE | — | — | — | — |
| b15_opt | CS_C2 | UNAVAILABLE | — | — | — | — |
| b15_opt | CS_C3 | UNAVAILABLE | — | — | — | — |
| b15_opt | B5 | UNAVAILABLE | — | — | — | — |

## J. IR-drop results

Primary statistics use one worst VDD terminal per powered nonphysical Liberty-modelled instance; percentiles use linear interpolation. Absolute supply thresholds are strict >11, >33 and >55 mV.
Native PDNSim terminal voltage CSVs have six decimals in volts (about 1 µV resolution); segment currents have roughly four significant digits. Derived arithmetic retains the available source precision. Equal exported voltages do not establish exact equality inside the solver. The registered 0.1 mV materiality threshold is much larger than this voltage export resolution.

| Design | Architecture | Worst mV | p99 mV | p95 mV | Mean mV | Powered instances |
|---|---|---:|---:|---:|---:|---:|
| b14_opt | B3T | — | — | — | — | — |
| b14_opt | CS_C1 | — | — | — | — | — |
| b14_opt | CS_C3 | — | — | — | — | — |
| b14_opt | B5 | — | — | — | — | — |
| b15_opt | B2 | — | — | — | — | — |
| b15_opt | CS_C1 | — | — | — | — | — |
| b15_opt | CS_C2 | — | — | — | — | — |
| b15_opt | CS_C3 | — | — | — | — | — |
| b15_opt | B5 | — | — | — | — | — |

## K. Current-density results

Peak/p95/p99 absolute PDN segment current is reported in amperes. Current density was **NOT EVALUATED** because no qualified metal cross-section (width and thickness) was supplied. Segment current is not current density; no EM limit is applied.
Full raw segment endpoints and currents are retained. Regional maximum segment-current maps use segment midpoints and are diagnostic. Mean/peak activity correspondence and fixed top-quartile hotspot IoU against those maps use the same occupied-domain and missing-value rules; these current proxies do not enter the classifier. Worst-drop instance origins and peak-current segment locations are retained in the machine summary and IR CSV.

## L. Spatial correlations

Both Pearson and average-tie-rank Spearman are reported at 4×4 and 8×8. The primary domain is occupied nonphysical Liberty-powered instance-origin bins; empty die regions are excluded. Mean regional C×N per shift cycle is compared with regional dynamic-power sum and static-IR maximum.
Top-quartile IoU uses ceil(occupied bins/4), with ascending bin ID breaking value ties. Missing occupied values invalidate primary statistics; finite-subset calculations are diagnostic. Constant vectors have undefined agreement.
The preregistered proxy criterion uses all eight reference/CS_C1 architecture-grid Spearman values ≥0.5: **UNAVAILABLE**.
Complete vectors/supports and all correlations are in `spatial_correlations.csv` and per-architecture `spatial_vectors.json`. Secondary per-bin maximum C×N maps are reconstructed from the bound retained cycle counts and crosschecked against frozen H4/H8. Different bins can peak on different cycles; correlations against averaged power and static IR do not validate transient peak prediction.

| Design | Architecture | Grid | Mean-activity comparison | n | Pearson r | Spearman ρ | Top-quartile IoU | Status |
|---|---|---|---|---:|---:|---:|---:|---|

All secondary peak-map statistics, hotspot bin IDs, finite-subset diagnostics and unavailable reasons are retained alongside the primary table in the CSV/JSON evidence. They do not enter the campaign classifier.

## M. Thermal results

**THERMAL_IMPACT_NOT_EVALUATED**. No thermal hotspot improvement is established.

## N. Practical interpretation

Material PI benefit requires ≥1% relative and ≥0.1 mV absolute reductions in BOTH worst and p99 drop, with ≤1% dynamic-power and peak-current regression. Modest scan-wire cost is ≤2%.

| Design | Candidate vs reference | Δ scan WL % | Δ E % | Δ H4 % | Δ H8 % | Δ dynamic % | Δ worst IR % | Δ p99 IR % | Δ peak current % | Material PI benefit |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---|
| b14_opt | CS_C1 vs B3T | 0.0436992 | -0.357366 | -1.70784 | -5.68763 | — | — | — | — | — |
| b14_opt | CS_C3 vs B3T | 0.0669867 | -0.273978 | -1.69291 | -5.73228 | — | — | — | — | — |
| b14_opt | B5 vs B3T | 16.7434 | -20.2272 | 5.38646 | 7.08872 | — | — | — | — | — |
| b15_opt | CS_C1 vs B2 | 1.33618 | -1.26674 | 2.61845 | -1.68276 | — | — | — | — | — |
| b15_opt | CS_C2 vs B2 | 0.896204 | -1.36597 | -1.64227 | 4.15126 | — | — | — | — | — |
| b15_opt | CS_C3 vs B2 | 1.24913 | -1.01148 | 2.61253 | -1.34046 | — | — | — | — | — |
| b15_opt | B5 vs B2 | 14.3983 | -19.9278 | -7.11509 | -0.555294 | — | — | — | — | — |

## O. OpenROAD maintainer question — direct answer

The quoted 2.4% reduction does not yet establish an IR-drop or thermal benefit. Required power/static-VDD evidence is incomplete or unqualified, so its practical impact remains unresolved. The historical question is separate from the frozen Gate 09 H4/H8 comparisons tested here. Thermal was not evaluated; no transient IR claim is supported.

## P. Go/no-go recommendation

**SHOULD PACT DEVELOPMENT CONTINUE? HOLD.**

Evidence: the tables above and bound raw records. Interpretation: the fixed materiality and correspondence rules determine the classification; smaller effects remain reported. Recommendation: Incomplete or invalid required measurement evidence prevents the registered distinctions.

## Q. Upstream issues/PRs

No new upstream contribution is asserted by this report. Failed implementation attempts are retained separately from scientific architecture results; any separately qualified repair/PR is listed by the publication receipt.

## R. Complete provenance

OpenROAD `26Q2-1164-g08f67ee5ec`, binary SHA-256 `fcd7dcfc37d329bd43a7ede75805319a2e70e6879da11d42b4fd1c2e50e645c3`; OpenSTA `3.1.0`.
Protocol, selected inputs, tool/Liberty hashes, smoke controls, per-attempt commands/environment/resources, raw output bindings and derived vector receipts are retained in the Gate 10A evidence tree. `runtime_resources.csv` includes failed/held/control attempts as well as scientific runs.

## S. Next action

Hold algorithm development and qualify the missing or invalid measurement basis before drawing a scientific continuation, pivot or stop conclusion.

Unresolved qualification records:

- b14_opt/B3T: Independent raw-CSV aggregate differs: native design internal_w
- b14_opt/CS_C1: Independent raw-CSV aggregate differs: native design internal_w
- b14_opt/CS_C3: Independent raw-CSV aggregate differs: native design internal_w
- b14_opt/B5: Independent raw-CSV aggregate differs: native design internal_w
- b15_opt/B2: Independent raw-CSV aggregate differs: native design internal_w
- b15_opt/CS_C1: Independent raw-CSV aggregate differs: native design internal_w
- b15_opt/CS_C2: Independent raw-CSV aggregate differs: native design internal_w
- b15_opt/CS_C3: Independent raw-CSV aggregate differs: native design internal_w
- b15_opt/B5: Independent raw-CSV aggregate differs: native design internal_w
