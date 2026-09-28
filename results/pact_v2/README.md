# PACT Implementation-Aware Backend v2

**PACT_V2_NEW_PARETO_ARCHITECTURE_FOUND**

Generated and evaluated 50723 distinct new
architectures; selected 9 for implementation and measured
9. The primary measured Pareto space is routed
scan-path upper bound, all-data weighted total shift activity and 8×8 weighted
local peak. Timing/DRC qualify eligibility, and every metric remains separately
reported. No scalar score determines this classification.

## Commands and inputs

Run from the repository in the existing WSL Ubuntu-24.04 environment:

```sh
export PYTHONPATH=.optimizer-deps:src OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1
PY=/root/pact-deps/pact-venv/bin/python
for d in s5378 s9234 s15850; do
  $PY scripts/pact_v2.py search --design "$d" --seconds 180 --max-evaluations 20000 --route-limit 3
  $PY scripts/pact_v2.py route --design "$d" --route-seconds 600
  $PY scripts/pact_v2.py measure --design "$d"
done
$PY scripts/pact_v2.py report
$PY scripts/pact_v2_check.py
$PY scripts/pact_v2_seal.py
```

Search refuses to overwrite evidence; use a fresh `--output` for replay. Exact
invocations, parent commits, input hashes and Python tool versions are in each
design's `inputs.json`. Source-code hashes bind the actual search implementation.
`search.json` contains configuration, initialization/search runtime, evaluation
counts, baseline scores, the predicted frontier and selection roles. Canonical
architectures and hashes are in `architectures/`; the lossless mutation log is
`evaluations.csv.gz`. `comparison.csv` includes every distinct evaluated order,
including rejected proposals; unimplemented rows have no physical measurement.
The local uncompressed logs and large implementation artifacts are ignored.

Inputs are the stored P/T, J50 and PACT architectures, original FAN BASIC_SCAN
patterns, bijective FF mappings, frozen placement/ports and existing OpenRCX +
Liberty loads. The other physical ordering is also a seed. Old results and routes
were reused without rerunning historical experiments. New route execution records
contain exact rewire/make/verification commands and runtime. Measurement manifests
bind routed ODB, netlist, workload, library, extraction rules and simulator inputs.
The evidence seal verifies those bindings, stores compressed per-cycle/stimulus
records, and hashes the local raw waveforms, parasitics and databases without
adding them to Git.

## Predicted selection

Activity and spatial extremes plus a balanced nondominated candidate were selected
under configurable 10% wire and maximum-edge allowances; duplicates were removed.
These are estimates over direct FF Q/QN loads, not whole-network predictions.

The retained predicted H8 values are tied for s5378; the spatial selection label there does not indicate a lower predicted peak.

| Design | Architecture / selection | Wire estimate µm | FF weighted total | FF H8 | Max edge µm |
|---|---|---:|---:|---:|---:|
| s5378 | P  | 1380.830 | 6551607.772 | 74.08928 | 92.025 |
| s5378 | J50  | 2634.750 | 6119391.698 | 74.08928 | 99.355 |
| s5378 | PACT  | 1517.750 | 6288853.648 | 74.08928 | 88.745 |
| s5378 | c4eabc41cb50 spatial | 1435.350 | 5954055.479 | 74.08928 | 92.025 |
| s5378 | b5c4710dcf54 balanced | 1378.390 | 6108746.853 | 74.08928 | 88.745 |
| s5378 | 3b627d8af4f2 activity | 1500.490 | 5713541.340 | 74.08928 | 88.745 |
| s9234 | T  | 1723.945 | 15939361.483 | 142.71312 | 104.180 |
| s9234 | J50  | 3069.885 | 14336929.243 | 151.72918 | 110.140 |
| s9234 | PACT  | 1893.465 | 15660554.883 | 139.33013 | 87.755 |
| s9234 | 53bb5b018758 balanced | 1718.525 | 15757167.423 | 139.33013 | 87.180 |
| s9234 | 797aff0b91f6 spatial | 1855.825 | 15409719.600 | 132.75388 | 87.755 |
| s9234 | f4bca5652bda activity | 1892.425 | 14985562.201 | 139.33013 | 87.755 |
| s15850 | P  | 3525.470 | 64737696.447 | 142.34482 | 169.200 |
| s15850 | J50  | 9052.290 | 54822427.548 | 129.02526 | 151.780 |
| s15850 | PACT  | 3857.910 | 63964348.156 | 141.65611 | 169.200 |
| s15850 | e14689c97ca5 balanced | 3517.730 | 64652545.838 | 142.34482 | 169.200 |
| s15850 | f3e118a35e7b spatial | 3876.950 | 63836165.553 | 128.46361 | 169.200 |
| s15850 | 1c4fe83a6b04 activity | 3854.310 | 63678279.114 | 141.65611 | 169.200 |

## Measured physical effects

Both load and unload are measured. The original zero-delay gate simulation,
source-localized grids, OpenRCX grounded + Liberty pin capacitance convention,
route verification and functional checks are unchanged. All shown timing values
are the existing flow's global-route estimates, not signoff. DRC and all verification
outcomes are in `summary.json` and individual route/measurement reports.

The repository suite passed 280 tests. The final focused check passed 6 tests. Independent replay reproduced 9 selected candidates and matched stored Q totals for 924 FFs. See `tests.json` and `reproducibility.json`.

The core objective implementation is unchanged across these runs; later CLI
edits added measurement locking and path normalization.

| Design | Architecture | Transitions | Peak/cycle | C·N total | Local peak | H8 C·N | H4 C·N | Route µm | Setup / hold ns | Nondominated |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---|
| s5378 | P | 5147171 | 603 | 19375482.162 | 31 | 186.56425 | 427.04280 | 5172.870 | 9.087880 / 0.002729 | False |
| s5378 | J50 | 4889711 | 567 | 18633738.131 | 33 | 176.16843 | 418.29128 | 5911.570 | 9.086730 / 0.002739 | False |
| s5378 | PACT | 4955244 | 595 | 18563391.310 | 31 | 167.80267 | 430.19493 | 5189.610 | 9.086550 / 0.002710 | True |
| s5378 | c4eabc41cb50 | 4868181 | 629 | 18117570.827 | 31 | 195.02159 | 420.45982 | 5163.830 | 9.086660 / 0.002729 | True |
| s5378 | b5c4710dcf54 | 4939146 | 633 | 18425596.544 | 32 | 177.51052 | 425.27511 | 5141.000 | 9.086650 / 0.002749 | True |
| s5378 | 3b627d8af4f2 | 4711279 | 600 | 17484807.963 | 31 | 181.82719 | 431.84621 | 5180.895 | 9.086650 / 0.002709 | True |
| s9234 | T | 11805835 | 933 | 39343115.757 | 54 | 192.03927 | 521.51998 | 10520.985 | 8.743510 / 0.000690 | True |
| s9234 | J50 | 10901893 | 876 | 36453170.523 | 50 | 197.39312 | 477.61081 | 11490.195 | 8.749200 / 0.000694 | True |
| s9234 | PACT | 11671923 | 931 | 38881534.462 | 50 | 188.34326 | 479.04074 | 10622.830 | 8.742830 / 0.001955 | True |
| s9234 | 53bb5b018758 | 11730061 | 916 | 39092514.567 | 51 | 190.57281 | 501.99701 | 10564.785 | 8.744530 / 0.000690 | True |
| s9234 | 797aff0b91f6 | 11506315 | 907 | 38263232.017 | 54 | 191.18141 | 497.97814 | 10629.670 | 8.748020 / 0.000690 | True |
| s9234 | f4bca5652bda | 11303917 | 891 | 37512213.183 | 54 | 190.50311 | 528.32574 | 10631.990 | 8.742660 / 0.000694 | True |
| s15850 | P | 51656644 | 1731 | 161934844.530 | 90 | 277.17684 | 684.84663 | 24095.050 | 8.132980 / 0.000547 | True |
| s15850 | J50 | 45881553 | 1556 | 145276948.656 | 90 | 267.99241 | 628.92771 | 27774.430 | 8.132680 / 0.001362 | True |
| s15850 | PACT | 51185084 | 1712 | 160474750.279 | 90 | 277.05019 | 705.01210 | 24290.780 | 8.132370 / 0.000863 | False |
| s15850 | e14689c97ca5 | 51599492 | 1739 | 161801741.151 | 90 | 277.68177 | 697.01926 | 24123.785 | 8.132980 / 0.000720 | True |
| s15850 | f3e118a35e7b | 51115947 | 1723 | 160381858.455 | 90 | 271.85138 | 687.67999 | 24265.025 | 8.132440 / 0.000938 | True |
| s15850 | 1c4fe83a6b04 | 51008643 | 1736 | 159939844.757 | 90 | 279.74037 | 682.04774 | 24248.245 | 8.133020 / 0.000862 | True |

## Comparison with each stored baseline

Negative changes mean reduction. Nondominance is computed against all measured
eligible old and new candidates of the same design, not just the physical start.

| Design | New architecture | Reference | Route Δ% | C·N Δ% | H8 Δ% | Transitions Δ% | H4 Δ% |
|---|---|---|---:|---:|---:|---:|---:|
| s5378 | c4eabc41cb50 | P | -0.175 | -6.492 | +4.533 | -5.420 | -1.542 |
| s5378 | c4eabc41cb50 | J50 | -12.649 | -2.770 | +10.702 | -0.440 | +0.518 |
| s5378 | c4eabc41cb50 | PACT | -0.497 | -2.402 | +16.221 | -1.757 | -2.263 |
| s5378 | b5c4710dcf54 | P | -0.616 | -4.903 | -4.853 | -4.042 | -0.414 |
| s5378 | b5c4710dcf54 | J50 | -13.035 | -1.117 | +0.762 | +1.011 | +1.670 |
| s5378 | b5c4710dcf54 | PACT | -0.937 | -0.742 | +5.785 | -0.325 | -1.144 |
| s5378 | 3b627d8af4f2 | P | +0.155 | -9.758 | -2.539 | -8.469 | +1.125 |
| s5378 | 3b627d8af4f2 | J50 | -12.360 | -6.166 | +3.212 | -3.649 | +3.241 |
| s5378 | 3b627d8af4f2 | PACT | -0.168 | -5.810 | +8.358 | -4.923 | +0.384 |
| s9234 | 53bb5b018758 | T | +0.416 | -0.637 | -0.764 | -0.642 | -3.743 |
| s9234 | 53bb5b018758 | J50 | -8.054 | +7.240 | -3.455 | +7.597 | +5.106 |
| s9234 | 53bb5b018758 | PACT | -0.546 | +0.543 | +1.184 | +0.498 | +4.792 |
| s9234 | 797aff0b91f6 | T | +1.033 | -2.745 | -0.447 | -2.537 | -4.514 |
| s9234 | 797aff0b91f6 | J50 | -7.489 | +4.965 | -3.147 | +5.544 | +4.264 |
| s9234 | 797aff0b91f6 | PACT | +0.064 | -1.590 | +1.507 | -1.419 | +3.953 |
| s9234 | f4bca5652bda | T | +1.055 | -4.654 | -0.800 | -4.251 | +1.305 |
| s9234 | f4bca5652bda | J50 | -7.469 | +2.905 | -3.491 | +3.688 | +10.618 |
| s9234 | f4bca5652bda | PACT | +0.086 | -3.522 | +1.147 | -3.153 | +10.288 |
| s15850 | e14689c97ca5 | P | +0.119 | -0.082 | +0.182 | -0.111 | +1.777 |
| s15850 | e14689c97ca5 | J50 | -13.144 | +11.375 | +3.616 | +12.462 | +10.827 |
| s15850 | e14689c97ca5 | PACT | -0.687 | +0.827 | +0.228 | +0.810 | -1.134 |
| s15850 | f3e118a35e7b | P | +0.705 | -0.959 | -1.921 | -1.047 | +0.414 |
| s15850 | f3e118a35e7b | J50 | -12.635 | +10.397 | +1.440 | +11.408 | +9.342 |
| s15850 | f3e118a35e7b | PACT | -0.106 | -0.058 | -1.876 | -0.135 | -2.458 |
| s15850 | 1c4fe83a6b04 | P | +0.636 | -1.232 | +0.925 | -1.254 | -0.409 |
| s15850 | 1c4fe83a6b04 | J50 | -12.696 | +10.093 | +4.384 | +11.175 | +8.446 |
| s15850 | 1c4fe83a6b04 | PACT | -0.175 | -0.333 | +0.971 | -0.345 | -3.257 |

## Limitations and remaining publication work

Frozen direct FF loads omit downstream combinational toggles, buffer descendants
and candidate-specific load changes during search. Consequently a lower FF peak
does not guarantee a lower whole-network peak. Route measurements resolve that
distinction, and 4×4 results are reported without changing the primary 8×8 objective.
The timing constraint is maximum physical edge length, not a calibrated timing
predictor; actual setup/hold information is limited to the existing flow.

This is one bounded synthesis run per design at the established placement seed,
not multiseed generalization or broad validation. Publication-quality claims would
need an independently planned evaluation with more designs/placements, timing-aware
simulation or signoff where applicable, and a fuller load model if needed. None
of these results establishes watts, IR-drop or silicon reliability improvement.
