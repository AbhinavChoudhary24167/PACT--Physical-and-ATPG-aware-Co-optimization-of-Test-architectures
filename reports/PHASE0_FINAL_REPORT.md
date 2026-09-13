# PACT Phase-0 evidence report

## A. Environment

The observed runs used Ubuntu 24.04.4 LTS under WSL2, kernel `6.18.33.2-microsoft-standard-WSL2`, on an AMD Ryzen 7 7735HS. WSL exposed four logical CPUs, 3.8 GiB RAM, and 8.0 GiB swap. The initial inventory found no OpenROAD, Yosys, KLayout, Make, C++, or CMake installation. The [initial and post-install inventories](../artifacts/raw/tool_qualification/environment/) record the exact environment.

| Component | Observed identity |
| --- | --- |
| OpenROAD binary | `26Q2-1164-g08f67ee5ec`; package SHA256 `f3f1eeaa18f327503f72cc45dcef5b1514ec2e89726ec53b4553bf4f951168a3` |
| OpenROAD regression-source checkout | `dc5eee77c45dba8e5ace2fc89c38c6d9a4ed6e0f` (not asserted to be the binary build commit) |
| OpenROAD-flow-scripts checkout | `5e8b1450d19263f797a27c4f371b9dd19f32a3aa` |
| FAN_ATPG checkout | `26b2b36c0e9db11a4b6d9e759df6e44357121f39` |
| Yosys / KLayout | Yosys 0.33 (`2584903a060`); KLayout 0.28.16 |
| Python / Git / Make / CMake | Python 3.12.3; Git 2.43.0; GNU Make 4.3; CMake 3.28.3 |

The full build commit for the prebuilt OpenROAD binary was not recovered. Python package versions are frozen in [python-packages.txt](../artifacts/manifests/python-packages.txt). The external source checkouts and binaries live outside Git; no upstream files were modified.

## B. Tool qualification

OpenROAD's supplied SKY130 `one_cell_sky130.tcl` and `place_sort_sky130.tcl` DFT regressions passed scan replacement, DFT planning, and scan stitching. `scan_opt` emitted `DFT-0014 Scan Opt is not currently implemented`; its before/after netlists had identical hashes. The [DFT qualification](openroad_dft_qualification.md) links the raw logs. This verifies the installed commands, but their stitched ordering was not extracted for s5378.

FAN_ATPG built at the pinned commit. Its supplied ATPG and fault-simulation examples for all four listed ISCAS89 circuits exited zero and agreed on coverage and pattern count; see the [ATPG qualification](fan_atpg_qualification.md). ORFS imported fixed translated s5378 and s9234 scan netlists. For **each** design, the supplied order and a verified OpenDB scan-only nearest-neighbor rewire completed placement/CTS, global routing, and detailed routing. The four saved route exits are [s5378 baseline](../artifacts/raw/orfs_smoke/s5378/route.place-fixed.exit), [s5378 nearest](../artifacts/raw/orfs_rewire/s5378/nearest_neighbor/route.exit), [s9234 baseline](../artifacts/raw/orfs_smoke/s9234/route.exit), and [s9234 nearest](../artifacts/raw/orfs_rewire/s9234/nearest_neighbor/route.exit). PDNSim was not run; all power-integrity fields are `NOT_RUN`.

## C. Benchmark provenance

| Design | Role | Source and checksum | ATPG | Physical implementation |
| --- | --- | --- | --- | --- |
| `pact_sanity` | Self-authored 64-FF debug RTL; excluded from research conclusions | [RTL](../benchmarks/pact_sanity/pact_sanity.v), SHA256 `8797c3613127fd20faad264375ea3f91cf703bce4e88e32e444a7a31b0da34ae` | No verified full-scan extraction into FAN | Synthesized only |
| `s27` | ATPG qualification | FAN `mod_netlist/s27.v`, SHA256 `7c612134b5f7ea5faf4f8658dab6409e6bf3c71f74d13ee2ae6163307c64da25` | Passed | No |
| `s5378` | Research baseline, one fixed placement | FAN `mod_netlist/s5378.v`, SHA256 `10d258eff2287e4e737023c90fe10e6d4561afa18491ce1a414aa04fd964b158` | Passed; 179 mapped FFs | Supplied and nearest-neighbor orders routed |
| `s9234` | Independent-design replication attempt, one fixed placement | FAN `mod_netlist/s9234.v`, SHA256 `668647f66a005b830ff92bf075db8f583aaa3165ff8f9f2d716ab9f8a24326c6` | Passed; 211 mapped FFs | Supplied and nearest-neighbor orders routed |
| `s15850` | ATPG-qualified replication candidate | FAN `mod_netlist/s15850.v`, SHA256 `3ab8d259c9977082e5a5f0677b952ed170f20f74f9896954168770b148d1b9b4` | Passed | No |

The exact pinned upstream URLs, local paths, hashes, and license caveat are in [the benchmark manifest](../benchmarks/manifests/iscas89_from_fan.yaml). FAN_ATPG identifies its repository as MIT-licensed; original ISCAS89 benchmark rights were not independently verified. No benchmark was silently replaced.

## D. Scan architecture methods

Within each design, all evaluations hold one chain, the same placed coordinates, clock domain, and ATPG targets: s5378 has 179 named `SDFF_X1` instances and 117 targets; s9234 has 211 and 156. Architectures contain an exact FF inventory and deterministic canonical SHA256. The supplied FAN chain is reconstructed from the actual pre-stitched netlist (`B0` proxy); it is **not** OpenROAD-native `execute_dft_plan` ordering. Thus the requested OpenROAD-native baseline remains missing for both designs.

`random` shuffles the sorted FF names with explicit seeds 11, 13, 17, 19, and 23. `nearest_neighbor` starts at the lexicographically first FF and greedily selects the shortest Manhattan edge, breaking ties by name. `serpentine` sweeps eight Y bins with alternating X direction. `activity_only` greedily avoids positive pairwise correlation of ATPG PPI bits without reading coordinates. `physical_activity_alpha_*` uses the same deterministic greedy start and cost `α·(Manhattan distance / maximum FF-pair distance) + (1−α)·((PPI Pearson correlation + 1)/2)`, with α in `{0,.25,.50,.75,1}`. These are conventional heuristics, not learned methods. α=0 duplicates `activity_only`; α=1 duplicates `nearest_neighbor` and shares its architecture hash.

## E. ATPG methodology

The measured fault model is FAN_ATPG's single stuck-at `saf` model, with `BASIC_SCAN` one-frame patterns, static and dynamic compression on, and X-fill on. Supplied examples reported s27: 94.55%, 5 patterns, 0.000235 s; s5378: 96.04%, 117, 0.4923 s; s9234: 94.14%, 156, 2.257 s; s15850: 94.62%, 133, 4.746 s. The [saved reports and `.pat` files](../artifacts/raw/tool_qualification/fan_atpg/) are the source of these values. The parser uses the observed seven-field `PI1 | PI2 | PPI | SI | PO1 | PO2 | PPO` format; PPI names and order are checked against source scan FF outputs and placed FF instance/Q-net inventories. The [s5378](../artifacts/derived/s5378/ff_identity_map.json) and [s9234](../artifacts/derived/s9234/ff_identity_map.json) identity manifests hash their four respective source artifacts. These are FAN's already full-scanned netlists: a general sequential-RTL→combinational-ATPG translation, including for `pact_sanity`, remains unfinished.

## F. Shift simulation methodology

For every target pattern, each chain is serially loaded tail bit first. At clock `t`, FF0 receives the next scan-in bit and FFi receives FFi−1's previous value. The simulator stores before, after, and XOR toggle for every FF and every shift clock; each loaded state is asserted equal to the logical PPI target, independent of chain order. `T_total = Σ(pattern,clock,FF) toggle`; `S_t = Σ_FF toggle`; global peak, mean, P95, and P99 derive from `S_t`. The initial state is all zero, and the next vector starts from the previous **loaded** state. Functional capture between vectors is unmodeled, so these are controlled shift proxies rather than actual tester power traces. The sequences contain `117×179 = 20,943` s5378 and `156×211 = 32,916` s9234 shift clocks. Manually computed 2-, 3-, and 4-cell cases and pattern-transition tests are in the 24-test [saved pytest run](../artifacts/raw/tests/pytest.log).

Spatial metrics bin the same FF placement into 8×8, 16×16, and 32×32 grids. `A(b,t)=Σ_{FF in b} toggle(FF,t)`, with bin density `D(b,t)=A(b,t)/N_b` and zero density for empty bins. The predeclared primary hotspot is `max_(b,t) Σ_(c: Manhattan bin radius ≤1) D(c,t)/(1+distance(b,c))` on the 8×8 grid. Out-of-die bins are zero. Peak and percentiles over all clock/bin pairs and cumulative-bin Gini are also saved. This metric is explicitly a **spatial shift-activity hotspot proxy**, not IR drop.

## G. Physical methodology

FAN's `mod_netlist` designs already contain scan cells and scan connectivity. ORFS Nangate45/FreePDK45 supports `SDFF_X1` but lacks FAN's `BUF_X3`: 34 in s5378 and 96 in s9234. [s5378](../artifacts/manifests/s5378_translation.json) and [s9234](../artifacts/manifests/s9234_translation.json) translations replaced only those cell masters with Boolean-equivalent `BUF_X4` before placement, retaining all nets and FF identities. Within each design the same translated logic was used in both routed orders; drive strength and physical cost therefore differ from the original FAN netlist but cannot explain each paired ordering delta. The first s5378 untranslated import and SDC attempt failed; their raw logs remain in [its smoke evidence](../artifacts/raw/orfs_smoke/s5378/). An initial s9234 translation wrapper invocation also exited nonzero after creating the netlist because of shell quoting; its failure note is preserved, and the corrected wrapper exited zero.

The [s5378](../experiments/phase0/s5378_orfs/config.mk) and [s9234](../experiments/phase0/s9234_orfs/config.mk) ORFS configs fix platform Nangate45, core utilization target 35%, placement-density add-on 0.20, and a 10 ns single clock constraint. Structured floorplan metrics report s5378 die/core `7,393.42/6,921.05 µm²`, utilization 35.67%; s9234 die/core `10,699.8/10,208 µm²`, utilization 35.28%. The ORFS placement seeds were not explicitly randomized or recorded; the `11/13/17/19/23` labels are **ordering seeds only**. Within each design both physical routes start from one exact fixed placement. There is one placement per design, not five placement replicas.

The supplied pre-stitched scan netlist was placed first. After placement and before CTS, [OpenDB Tcl](../scripts/tcl/rewire_scan.tcl) disconnected/reconnected only the scan SI ITerms and scan-out buffer input for the nearest-neighbor variant. The [s5378](../artifacts/derived/phase0/smoke_s5378/nearest_neighbor.rewire_verification.json) and [s9234](../artifacts/derived/phase0/smoke_s9234/nearest_neighbor.rewire_verification.json) verification records confirm identical component masters, coordinates, and orientations for 2,013 and 2,688 placed instances respectively; functional Verilog normalized only at legal SI/scan-out pins was text-identical; each physical chain exactly matches its requested order; all 117 and 156 targets respectively remap correctly. CTS, global route, and detailed route were rerun for each variant. Geometric scan HPWL sums Manhattan distances between FF DEF origins, excluding ports; it is separate from **total** routed net wirelength. No routed scan-net-only length was extracted. Timing in the result records comes from structured global-route metrics; final detailed-route DRC and total wirelength come from structured detailed-route metrics. Congestion/overflow were not extracted as a defensible comparable quantity. No separate peak-memory or calibrated power evidence exists.

The [identity checks](../artifacts/derived/s5378/identity_check.json) record one placed SI-net name mismatch on s5378 and [two on s9234](../artifacts/derived/s9234/identity_check.json), due to placement-stage scan-input buffering. FF identity is based on the exact PPI/instance/Q-net bijection and DEF master, not equality of all SI net names; the post-edit physical chain and target-remapping checks address the altered scan connectivity directly.

## H. Results

The following 14 rows use s5378/Nangate45, 179 FFs, one chain, 117 patterns, and 96.04% fault coverage. `H8` is the predeclared distance-weighted hotspot, `P99bin` includes empty clock/bin slots, `Smax` is global simultaneous toggles, `T` is total shift toggles, `route WL` is **total** detailed-route net wirelength, and WNS is global-route setup slack. A dash means the architecture was evaluated only as a fixed-placement proxy. The machine-readable [s5378 records](../artifacts/derived/phase0/s5378/results.jsonl) link 14 compressed per-clock traces.

| Method | Seed | Arch SHA prefix | Scan HPWL µm | H8 | Peak bin | P99bin | Smax | T | Route WL µm | WNS ns |
| --- | ---: | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| supplied FAN | 11 | `0fed7836` | 1741.17 | 4.1667 | 8 | 5 | 109 | 1,954,773 | 16,801 | 9.12194 |
| nearest neighbor | 11 | `3425da89` | 1055.76 | 4.0278 | 8 | 5 | 114 | 1,894,953 | 16,963 | 9.12008 |
| serpentine | 11 | `1acc866d` | 1141.44 | 4.0556 | 8 | 5 | 117 | 1,860,459 | — | — |
| activity only | 11 | `053838c6` | 6747.49 | 4.3333 | 8 | 6 | 166 | 2,502,575 | — | — |
| random | 11 | `9b141653` | 8796.18 | 4.0000 | 8 | 5 | 112 | 1,866,065 | — | — |
| random | 13 | `603c0d1e` | 8434.55 | 4.0556 | 8 | 5 | 115 | 1,870,391 | — | — |
| random | 17 | `f30ad9b2` | 8406.05 | 4.2222 | 8 | 5 | 107 | 1,898,573 | — | — |
| random | 19 | `51eae294` | 8213.85 | 4.2222 | 8 | 5 | 113 | 1,924,769 | — | — |
| random | 23 | `a1243ea9` | 8004.88 | 4.0833 | 8 | 5 | 111 | 1,877,099 | — | — |
| α=0.00 | 11 | `053838c6` | 6747.49 | 4.3333 | 8 | 6 | 166 | 2,502,575 | — | — |
| α=0.25 | 11 | `4156ada0` | 2920.24 | 4.3333 | 8 | 6 | 151 | 2,390,557 | — | — |
| α=0.50 | 11 | `a420f50a` | 1844.43 | 4.3333 | 8 | 6 | 143 | 2,287,569 | — | — |
| α=0.75 | 11 | `dedbd65f` | 1269.92 | 4.3333 | 8 | 6 | 131 | 2,165,813 | — | — |
| α=1.00 | 11 | `3425da89` | 1055.76 | 4.0278 | 8 | 5 | 114 | 1,894,953 | — | — |

The next 14 rows use s9234/Nangate45, 211 FFs, one chain, 156 patterns, and 94.14% fault coverage. They use the same definitions and output schema. The machine-readable [s9234 records](../artifacts/derived/phase0/s9234/results.jsonl) link their 14 compressed traces.

| Method | Seed | Arch SHA prefix | Scan HPWL µm | H8 | Peak bin | P99bin | Smax | T | Route WL µm | WNS ns |
| --- | ---: | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| supplied FAN | 11 | `58621d69` | 6356.72 | 4.0444 | 10 | 6 | 129 | 3,637,841 | 27,147 | 8.78275 |
| nearest neighbor | 11 | `282bdf42` | 1247.87 | 3.9000 | 10 | 6 | 126 | 3,388,923 | 24,217 | 8.77687 |
| serpentine | 11 | `cceec17c` | 1442.66 | 4.0306 | 10 | 6 | 126 | 3,418,699 | — | — |
| activity only | 11 | `61dcc4b8` | 10070.88 | 4.2778 | 10 | 7 | 162 | 4,270,617 | — | — |
| random | 11 | `5a40a487` | 10543.01 | 3.9000 | 10 | 6 | 127 | 3,424,417 | — | — |
| random | 13 | `94404b85` | 10603.14 | 3.9889 | 10 | 6 | 128 | 3,457,413 | — | — |
| random | 17 | `e65d4c28` | 11006.40 | 3.9333 | 10 | 6 | 126 | 3,461,199 | — | — |
| random | 19 | `8b0b2be9` | 10317.15 | 3.9861 | 10 | 6 | 125 | 3,438,855 | — | — |
| random | 23 | `a6222b26` | 11121.97 | 3.9444 | 10 | 6 | 129 | 3,429,965 | — | — |
| α=0.00 | 11 | `61dcc4b8` | 10070.88 | 4.2778 | 10 | 7 | 162 | 4,270,617 | — | — |
| α=0.25 | 11 | `a45eb2f5` | 3655.02 | 4.2667 | 10 | 7 | 153 | 4,114,937 | — | — |
| α=0.50 | 11 | `e394a889` | 2053.81 | 4.1000 | 10 | 7 | 143 | 3,897,149 | — | — |
| α=0.75 | 11 | `39f159ed` | 1471.22 | 4.0417 | 10 | 6 | 134 | 3,669,617 | — | — |
| α=1.00 | 11 | `282bdf42` | 1247.87 | 3.9000 | 10 | 6 | 126 | 3,388,923 | — | — |

The paired [s5378](../artifacts/raw/orfs_physical/s5378/) and [s9234](../artifacts/raw/orfs_physical/s9234/) structured physical metrics show supplied→nearest: total detailed-route wirelength `16,801→16,963 µm` (+162, +0.96%) for s5378 but `27,147→24,217 µm` (−2,930, −10.79%) for s9234. Global-route setup WNS changes `9.12194→9.12008 ns` (−0.00186 ns) and `8.78275→8.77687 ns` (−0.00588 ns), respectively. Both pairs retain setup TNS 0, global-route setup/hold violation counts 0, max-slew/cap violation counts 0, and final detailed-route DRC errors 0. The small WNS deltas should not be presented as important timing effects.

Across the **two paired designs** (nearest minus supplied), scan HPWL delta has mean/median −2,897.13 µm, sample SD 3,127.84, and range −5,108.85 to −685.41; primary H8 delta has mean/median −0.1417, sample SD 0.0039, and range −0.1444 to −0.1389; total detailed-route wirelength delta has mean/median −1,384 µm, sample SD 2,186.37, and range −2,930 to +162. With only two heterogeneous circuits, a 95% CI or p-value for a population effect would be misleading; these are descriptive paired summaries.

For the five random *ordering* seeds on each fixed placement, s5378 scan HPWL has mean 8,371.10 µm, median 8,406.05, sample SD 293.59, range 8,004.88–8,796.18, and a t-based 95% CI for the mean of 8,006.56–8,735.64. Its H8 mean/median/SD/range/nominal CI are 4.1167/4.0833/0.1009/4.0000–4.2222/3.9914–4.2420. For s9234, corresponding scan HPWL values are 10,718.33/10,603.14/335.73/10,317.15–11,121.97/10,301.47–11,135.20 µm, and H8 values are 3.9506/3.9444/0.0375/3.9000–3.9889/3.9040–3.9971. These CIs describe random *orders*, not physical replicas; no physical-seed CI or paired inferential test is justified. The [combined 28-record comparison](../artifacts/derived/phase0/comparison_all.json) reports one of two designs with a strict proxy conflict, so the proxy conflict is **not replicated**. Both per-design CLI/schema checks and the 24-test unit suite passed. Required static figures were generated for [s5378](figures/scan_wirelength_vs_hotspot_activity.png) and [s9234](figures/s9234/scan_wirelength_vs_hotspot_activity.png), including heatmaps, scan overlays, and explicitly labeled no-data congestion panels.

## I. Trade-off analysis

H1: Yes for both designs: nearest-neighbor estimated scan HPWL is 685.41 µm (39.4%) below supplied FAN ordering on s5378 and 5,108.85 µm (80.4%) below it on s9234. H2: Yes, ordering changes exact-shift proxies: nearest lowers total toggles by 59,820 (3.06%) and H8 from 4.1667 to 4.0278 on s5378, and by 248,918 (6.84%) and H8 from 4.0444 to 3.9000 on s9234. The s5378 global peak rises 109→114 while s9234 falls 129→126, showing that one activity summary does not describe all effects.

H3: On s5378, random seed 11 has the lowest observed H8 at 4.0000 versus minimum-HPWL nearest at 4.0278. This absolute 0.0278 (0.69%) proxy hotspot gain costs 8,796.18 versus 1,055.76 µm estimated scan wirelength (8.33×). On s9234, nearest has both minimum HPWL 1,247.87 µm and minimum H8 3.9000; random seed 11 numerically ties H8 to metric precision with 10,543.01 µm HPWL. The [combined comparison](../artifacts/derived/phase0/comparison_all.json) therefore finds a strict proxy conflict in **one of two designs**, not replication. Every serial-load simulation reaches its design's identical logical FF targets, but the random orders were not physically rewired and routed.

H4: The observed s5378 8×8 proxy Pareto set has nearest and random seed 11; s9234's has only nearest. The handcrafted activity-correlation heuristic does not improve the primary hotspot on either design: s5378 α=0–0.75 gives H8=4.3333, and s9234 α=0–0.75 gives H8 from 4.2778 down to 4.0417, all worse than nearest. It should not be portrayed as an effective joint optimizer. H5: Physical reruns show different routing responses to the geometric reduction: **total** detailed-route wirelength rises 0.96% on s5378 but falls 10.79% on s9234. The random hotspot-tie/minimum and activity-aware variants were not routed, so these results do not demonstrate a routed local-activity trade-off. Structured congestion, routed scan-only length, and PDN response are absent. Physical-only and test-activity optimization are not shown to be meaningfully misaligned in a reproducible physical experiment.

## J. Threats to validity

FAN_ATPG is an open-source example flow on supplied pre-scanned benchmarks; its compressed/X-filled stuck-at patterns do not represent transition, path-delay, cell-aware, or production test sets. A general full-scan abstraction from the authored sanity RTL was not demonstrated. The starting scan state is assumed zero and subsequent pattern shifts begin from the previous loaded state, ignoring functional capture. The hotspot is a deterministic activity proxy and no dynamic IR-drop, calibrated power, or static PDN result exists. DEF instance origins approximate FF locations rather than routed scan-pin coordinates. Nangate45/FreePDK45 and the BUF_X3→BUF_X4 compatibility substitutions limit technology realism. Two modest designs (179 and 211 FFs), each with one physical placement, have identity-qualified campaigns; ordering seeds are not physical replications. Only the supplied and nearest orders were routed within each design, OpenROAD-native ordering was not extracted for either, structured congestion/overflow were unavailable, and detailed-route timing was not separately recomputed. The s5378 conflict is a 0.69% proxy difference and was not repeated on s9234; its practical significance is unknown. Original ISCAS89 benchmark rights remain uncertain. An initial CLI run failed on a syntax error after automatic review allowed the post-reset attempt; the failed logs were retained, the error was fixed, and subsequent CLI/schema/plot checks passed. None of these data support industrial signoff or novelty claims.

## K. Phase-0 classification

`PACT_PHASE0_HYPOTHESIS_NOT_ESTABLISHED`

G0 infrastructure: **PASS for the bounded two-design ORFS flow**. G1 DFT commands: **PASS in independent SKY130 regressions**. G2 real ATPG: **PASS**. G3 s5378/s9234 PPI-to-physical-FF identity: **PASS**. G4 serial shift simulation: **PASS, 24 tests and both CLI checks**. G5 required methods including **OpenROAD-native ordering on the research designs**: **FAIL/incomplete** (supplied FAN order is a different baseline). G6 nontrivial design conflict: **provisional fixed-placement proxy observation on s5378 only**, with a 0.69% H8 difference at an 8.33× HPWL cost; no physically routed conflict. G7 central conflict replication: **FAIL** despite a second fully routed design, because s9234's shortest chain also minimizes H8 and no multiple physical seeds were run. The project hypothesis is neither accepted nor refuted by this incomplete campaign; the required success gate fails. No ML work began.

## L. Go/no-go for Phase 1

**No-go for intervention-dataset generation or ML.** First finish a verified sanity full-scan abstraction, extract OpenROAD-native ordering or document its exact inapplicability for these scan cells, physically implement the s5378 candidate hotspot-minimizing random order and a distinct activity-aware order from the fixed placement, vary physical seeds or add further designs, and obtain defensible routed scan/congestion metrics. Any apparent conflict must survive those reruns with enough effect size to matter. [run_phase0.sh](../scripts/run_phase0.sh) with the pinned checkouts and Python environment reproduces the two-design observed subset and intentionally exits 2 because the full G5/G6/G7 gate remains unmet. [finalize_phase0.sh](../scripts/finalize_phase0.sh) rechecks the saved campaigns, figures, and [combined comparison](../artifacts/derived/phase0/comparison_all.json). Evidence checksums are in [phase0_evidence.sha256](../artifacts/manifests/phase0_evidence.sha256).
