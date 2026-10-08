# Gate 10A practical-impact validation

## A. Executive classification

**PACT_GATE10A_NO_MATERIAL_PHYSICAL_IMPACT**. Development recommendation: **FREEZE**.

Complete admissible evidence meets neither the material PI benefit nor spatial correspondence criterion.

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

Primary design power uses a high-accuracy sum of exported per-instance components. Native JSON aggregate differences are retained and checked against the population-derived binary32 gamma_n reduction bound already qualified by the runner; this parser bound is separate from scientific materiality and reproducibility thresholds.

| Design | Architecture | Status | Dynamic mW | Switching mW | Internal mW | Leakage mW |
|---|---|---|---:|---:|---:|---:|
| b14_opt | B3T | QUALIFIED | 0.664406 | 0.321264 | 0.343142 | 0.100094 |
| b14_opt | CS_C1 | QUALIFIED | 0.662864 | 0.320652 | 0.342212 | 0.100106 |
| b14_opt | CS_C3 | QUALIFIED | 0.6634 | 0.320906 | 0.342494 | 0.100106 |
| b14_opt | B5 | QUALIFIED | 0.573919 | 0.270656 | 0.303264 | 0.100094 |
| b15_opt | B2 | QUALIFIED | 0.901273 | 0.397634 | 0.50364 | 0.157492 |
| b15_opt | CS_C1 | QUALIFIED | 0.89386 | 0.394299 | 0.499561 | 0.157492 |
| b15_opt | CS_C2 | QUALIFIED | 0.894651 | 0.395037 | 0.499614 | 0.157492 |
| b15_opt | CS_C3 | QUALIFIED | 0.895762 | 0.395311 | 0.500451 | 0.157492 |
| b15_opt | B5 | QUALIFIED | 0.78793 | 0.345608 | 0.442322 | 0.157458 |

## J. IR-drop results

Primary statistics use one worst VDD terminal per powered nonphysical Liberty-modelled instance; percentiles use linear interpolation. Absolute supply thresholds are strict >11, >33 and >55 mV.
Native PDNSim terminal voltage CSVs have six decimals in volts (about 1 µV resolution); segment currents have roughly four significant digits. Derived arithmetic retains the available source precision. Equal exported voltages do not establish exact equality inside the solver. The registered 0.1 mV materiality threshold is much larger than this voltage export resolution.

| Design | Architecture | Worst mV | p99 mV | p95 mV | Mean mV | Powered instances |
|---|---|---:|---:|---:|---:|---:|
| b14_opt | B3T | 0.747 | 0.72765 | 0.656 | 0.48737 | 3136 |
| b14_opt | CS_C1 | 0.744 | 0.72764 | 0.656 | 0.486396 | 3137 |
| b14_opt | CS_C3 | 0.744 | 0.72664 | 0.657 | 0.486701 | 3137 |
| b14_opt | B5 | 0.656 | 0.64165 | 0.571 | 0.426577 | 3136 |
| b15_opt | B2 | 1.137 | 1.02 | 0.884 | 0.591961 | 4771 |
| b15_opt | CS_C1 | 1.129 | 1.01 | 0.8765 | 0.587583 | 4771 |
| b15_opt | CS_C2 | 1.13 | 1.01 | 0.877 | 0.588161 | 4771 |
| b15_opt | CS_C3 | 1.132 | 1.012 | 0.8795 | 0.588737 | 4771 |
| b15_opt | B5 | 1.042 | 0.90466 | 0.79165 | 0.528652 | 4768 |

## K. Current-density results

Peak/p95/p99 absolute PDN segment current is reported in amperes. Current density was **NOT EVALUATED** because no qualified metal cross-section (width and thickness) was supplied. Segment current is not current density; no EM limit is applied.
Full raw segment endpoints and currents are retained. Regional maximum segment-current maps use segment midpoints and are diagnostic. Mean/peak activity correspondence and fixed top-quartile hotspot IoU against those maps use the same occupied-domain and missing-value rules; these current proxies do not enter the classifier. Worst-drop instance origins and peak-current segment locations are retained in the machine summary and IR CSV.

## L. Spatial correlations

Both Pearson and average-tie-rank Spearman are reported at 4×4 and 8×8. The primary domain is occupied nonphysical Liberty-powered instance-origin bins; empty die regions are excluded. Mean regional C×N per shift cycle is compared with regional dynamic-power sum and static-IR maximum.
Top-quartile IoU uses ceil(occupied bins/4), with ascending bin ID breaking value ties. Missing occupied values invalidate primary statistics; finite-subset calculations are diagnostic. Constant vectors have undefined agreement.
The preregistered proxy criterion uses all eight reference/CS_C1 architecture-grid Spearman values ≥0.5: **NOT MET**.
Complete vectors/supports and all correlations are in `spatial_correlations.csv` and per-architecture `spatial_vectors.json`. Secondary per-bin maximum C×N maps are reconstructed from the bound retained cycle counts and crosschecked against frozen H4/H8. Different bins can peak on different cycles; correlations against averaged power and static IR do not validate transient peak prediction.

| Design | Architecture | Grid | Mean-activity comparison | n | Pearson r | Spearman ρ | Top-quartile IoU | Status |
|---|---|---|---|---:|---:|---:|---:|---|
| b14_opt | B3T | 4×4 | dynamic_power | 16 | 0.915534 | 0.95 | 0.6 | AVAILABLE |
| b14_opt | B3T | 4×4 | static_ir | 16 | 0.851648 | 0.90869 | 0.333333 | AVAILABLE |
| b14_opt | B3T | 8×8 | dynamic_power | 61 | 0.774047 | 0.756425 | 0.230769 | AVAILABLE |
| b14_opt | B3T | 8×8 | static_ir | 61 | 0.752796 | 0.855262 | 0.454545 | AVAILABLE |
| b14_opt | CS_C1 | 4×4 | dynamic_power | 16 | 0.915545 | 0.95 | 0.6 | AVAILABLE |
| b14_opt | CS_C1 | 4×4 | static_ir | 16 | 0.84948 | 0.909493 | 0.333333 | AVAILABLE |
| b14_opt | CS_C1 | 8×8 | dynamic_power | 61 | 0.774616 | 0.753781 | 0.230769 | AVAILABLE |
| b14_opt | CS_C1 | 8×8 | static_ir | 61 | 0.752274 | 0.855738 | 0.454545 | AVAILABLE |
| b14_opt | CS_C3 | 4×4 | dynamic_power | 16 | 0.915872 | 0.95 | 0.6 | AVAILABLE |
| b14_opt | CS_C3 | 4×4 | static_ir | 16 | 0.85083 | 0.90869 | 0.333333 | AVAILABLE |
| b14_opt | CS_C3 | 8×8 | dynamic_power | 61 | 0.77552 | 0.754469 | 0.230769 | AVAILABLE |
| b14_opt | CS_C3 | 8×8 | static_ir | 61 | 0.75253 | 0.854563 | 0.454545 | AVAILABLE |
| b14_opt | B5 | 4×4 | dynamic_power | 16 | 0.892233 | 0.908824 | 0.6 | AVAILABLE |
| b14_opt | B5 | 4×4 | static_ir | 16 | 0.853278 | 0.931568 | 0.6 | AVAILABLE |
| b14_opt | B5 | 8×8 | dynamic_power | 61 | 0.718897 | 0.707932 | 0.28 | AVAILABLE |
| b14_opt | B5 | 8×8 | static_ir | 61 | 0.733705 | 0.82599 | 0.52381 | AVAILABLE |
| b15_opt | B2 | 4×4 | dynamic_power | 16 | 0.593495 | 0.529412 | 0.333333 | AVAILABLE |
| b15_opt | B2 | 4×4 | static_ir | 16 | 0.313229 | 0.208824 | 0.333333 | AVAILABLE |
| b15_opt | B2 | 8×8 | dynamic_power | 60 | 0.606523 | 0.55153 | 0.2 | AVAILABLE |
| b15_opt | B2 | 8×8 | static_ir | 60 | 0.28788 | 0.426726 | 0.153846 | AVAILABLE |
| b15_opt | CS_C1 | 4×4 | dynamic_power | 16 | 0.589571 | 0.529412 | 0.333333 | AVAILABLE |
| b15_opt | CS_C1 | 4×4 | static_ir | 16 | 0.313518 | 0.208824 | 0.333333 | AVAILABLE |
| b15_opt | CS_C1 | 8×8 | dynamic_power | 60 | 0.602039 | 0.54336 | 0.2 | AVAILABLE |
| b15_opt | CS_C1 | 8×8 | static_ir | 60 | 0.288685 | 0.419628 | 0.153846 | AVAILABLE |
| b15_opt | CS_C2 | 4×4 | dynamic_power | 16 | 0.591606 | 0.529412 | 0.333333 | AVAILABLE |
| b15_opt | CS_C2 | 4×4 | static_ir | 16 | 0.314861 | 0.208824 | 0.333333 | AVAILABLE |
| b15_opt | CS_C2 | 8×8 | dynamic_power | 60 | 0.603078 | 0.547862 | 0.2 | AVAILABLE |
| b15_opt | CS_C2 | 8×8 | static_ir | 60 | 0.289847 | 0.42222 | 0.153846 | AVAILABLE |
| b15_opt | CS_C3 | 4×4 | dynamic_power | 16 | 0.590342 | 0.529412 | 0.333333 | AVAILABLE |
| b15_opt | CS_C3 | 4×4 | static_ir | 16 | 0.313109 | 0.208824 | 0.333333 | AVAILABLE |
| b15_opt | CS_C3 | 8×8 | dynamic_power | 60 | 0.602636 | 0.548529 | 0.2 | AVAILABLE |
| b15_opt | CS_C3 | 8×8 | static_ir | 60 | 0.288255 | 0.419189 | 0.153846 | AVAILABLE |
| b15_opt | B5 | 4×4 | dynamic_power | 16 | 0.544762 | 0.570588 | 0.333333 | AVAILABLE |
| b15_opt | B5 | 4×4 | static_ir | 16 | 0.295523 | 0.220588 | 0.333333 | AVAILABLE |
| b15_opt | B5 | 8×8 | dynamic_power | 60 | 0.543138 | 0.495012 | 0.2 | AVAILABLE |
| b15_opt | B5 | 8×8 | static_ir | 60 | 0.285145 | 0.400289 | 0.153846 | AVAILABLE |

All secondary peak-map statistics, hotspot bin IDs, finite-subset diagnostics and unavailable reasons are retained alongside the primary table in the CSV/JSON evidence. They do not enter the campaign classifier.

## M. Thermal results

**THERMAL_IMPACT_NOT_EVALUATED**. No thermal hotspot improvement is established.

## N. Practical interpretation

Material PI benefit requires ≥1% relative and ≥0.1 mV absolute reductions in BOTH worst and p99 drop, with ≤1% dynamic-power and peak-current regression. Modest scan-wire cost is ≤2%.

| Design | Candidate vs reference | Δ scan WL % | Δ E % | Δ H4 % | Δ H8 % | Δ dynamic % | Δ worst IR % | Δ p99 IR % | Δ peak current % | Material PI benefit |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---|
| b14_opt | CS_C1 vs B3T | 0.0436992 | -0.357366 | -1.70784 | -5.68763 | -0.232057 | -0.401606 | -0.00137429 | -0.344828 | NO |
| b14_opt | CS_C3 vs B3T | 0.0669867 | -0.273978 | -1.69291 | -5.73228 | -0.151415 | -0.401606 | -0.138803 | -0.258621 | NO |
| b14_opt | B5 vs B3T | 16.7434 | -20.2272 | 5.38646 | 7.08872 | -13.6192 | -12.1821 | -11.8189 | -12.8448 | NO |
| b15_opt | CS_C1 vs B2 | 1.33618 | -1.26674 | 2.61845 | -1.68276 | -0.822562 | -0.703606 | -0.980392 | -0.892244 | NO |
| b15_opt | CS_C2 vs B2 | 0.896204 | -1.36597 | -1.64227 | 4.15126 | -0.734797 | -0.615655 | -0.980392 | -0.754976 | NO |
| b15_opt | CS_C3 vs B2 | 1.24913 | -1.01148 | 2.61253 | -1.34046 | -0.611519 | -0.439754 | -0.784314 | -0.617708 | NO |
| b15_opt | B5 vs B2 | 14.3983 | -19.9278 | -7.11509 | -0.555294 | -12.5759 | -8.35532 | -11.3078 | -10.6383 | NO |

## O. OpenROAD maintainer question — direct answer

b14_opt CS_C1 versus B3T: H8 -5.68763%, dynamic power -0.232057%, worst static VDD drop -0.401606% (-0.003 mV), p99 drop -0.00137429%; b15_opt CS_C1 versus B2: H8 -1.68276%, dynamic power -0.822562%, worst static VDD drop -0.703606% (-0.008 mV), p99 drop -0.980392%. Complete admissible evidence meets neither the material PI benefit nor spatial correspondence criterion. These are observed responses of an activity-derived static model; transient droop and thermal hotspot improvement were not evaluated.

## P. Go/no-go recommendation

**SHOULD PACT DEVELOPMENT CONTINUE? FREEZE.**

Evidence: the tables above and bound raw records. Interpretation: the fixed materiality and correspondence rules determine the classification; smaller effects remain reported. Recommendation: Complete admissible evidence meets neither the material PI benefit nor spatial correspondence criterion.

## Q. Upstream issues/PRs

No new upstream contribution is asserted by this report. Failed implementation attempts are retained separately from scientific architecture results; any separately qualified repair/PR is listed by the publication receipt.

## R. Complete provenance

Scientific power runs use OpenSTA embedded in OpenROAD `26Q2-1164-g08f67ee5ec`, binary SHA-256 `fcd7dcfc37d329bd43a7ede75805319a2e70e6879da11d42b4fd1c2e50e645c3`, declared embedded OpenSTA revision `76c4d6df3537ccce331b5caa812196c3330ba7c4`. Separately inventoried `/usr/bin/sta` reports `3.1.0` and is not the scientific power engine.
Local OpenROAD checkout is a different revision; OpenSTA submodule is not populated. Runtime embedded Tcl procedure/help is authoritative; local C++ sources are supporting inspection only. Binary linkage has not been rebuilt independently.
Protocol, selected inputs, tool/Liberty hashes, smoke controls, per-attempt commands/environment/resources, raw output bindings and derived vector receipts are retained in the Gate 10A evidence tree. `runtime_resources.csv` includes failed/held/control attempts as well as scientific runs.

## S. Next action

Freeze PACT algorithm development; retain the evidence and document the lack of registered material physical benefit.
