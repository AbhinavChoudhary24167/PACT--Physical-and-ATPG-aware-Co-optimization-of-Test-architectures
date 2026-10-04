# Constrained Stage-B activity optimization

Stage B uses the existing simultaneous-state evaluator and fixed-capacity move
operators. The physical reference is the lower measured routed scan cost of B2
and B3T. It screens proposals against port-inclusive scan HPWL before updating
activity:

`W_proxy(candidate) <= (1 + epsilon) W_proxy(reference)`.

Feasible search lanes minimize E, H4, H8, and their equally weighted mean after
division by the reference metrics. Each endpoint winner retains its raw metrics;
an independent simultaneous replay verifies the retained architectures. The
capacity multiset permits the exact reversed-capacity B3T start, while each move
preserves its starting chain lengths, FF membership and clock domains.

The [measured report](../results/pact_stage_b/REPORT.md) contains the complete
three-design campaign, exact comparisons, timing and qualification results.
Proxy feasibility is checked separately from actual routed budget acceptance.
Neither the search score nor a lower switching proxy establishes signoff power.

The public input bundles contain the exact architecture, load/response arrays,
physical sensitivity arrays, topology, capacitance, primary-input states and
labelled B2/B3T/P0 starts used by the campaign. All three bundles were rebuilt
through the portable loader and independently replayed against the saved scores
for their three starts and three routed selections. The selected architectures
and all qualified Stage-A comparator metrics are exported under neutral labels.
Machine-specific execution receipts and provenance values are stored privately.

Install the project with its optimizer dependencies, then run a fresh search:

```sh
python -m pip install -e '.[optimizer,dev]'
OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 NUMBA_NUM_THREADS=1 \
  python scripts/pact_stage_b_search.py \
  --input results/pact_stage_b/inputs/s5378.json.gz \
  --output scratch/stage_b/s5378 \
  --seconds 300 --epsilons 0.02 0.05 0.10
python -m pytest -q tests/unit/test_stage_b.py
```

Use the corresponding input for s9234 and s15850 with the same configuration.
Choose an output directory on a volume with sufficient free space; search refuses
to overwrite saved evidence. The defaults use seed 11, 20,000 evaluations and a
2,000-attempt no-improvement window. Model loading, initialization and final
replay are separate from the mutation-loop wall-clock budget. A single indivisible
evaluation may finish after that budget. Wall-clock termination can change the
final search endpoint across machines; the published architecture files preserve
the exact measured selections.

The portable search runner produces candidate architectures and predictor scores.
It does not reimplement physical qualification. Measured CSVs use the frozen
Nangate45/ORFS flow, route seed 11, two route cores, FAN schedule, all-data
ground-plus-pin capacitance and global-route timing. Raw databases, waveforms
and the private campaign adapters are retained with the local scientific record.

Public results:

- `candidate_results.csv`: winners at all three proxy budgets.
- `search_configuration.csv`: actual solver time, evaluations and termination.
- `routed_results.csv`: every selected routed/measured outcome.
- `comparison.csv`: exact deltas and both dominance definitions versus B2/B3T/P0.
- `prediction_transfer.csv`: proxy-to-measured activity transfer.
- `stage_a_comparator.csv`: all frozen comparator points and qualification statuses.
- `s15850_hotspot_diagnostic.csv`, `s15850_hotspot_contributors.csv` and
  `s15850_background_probe.csv`: focused saved-count coverage diagnostics. The
  background probe is separate from the executed search method.
- `architectures/` and `inputs/`: portable selected orders and predictor inputs.

The publication branch contains a clean method/results export based on the
existing public main branch. The frozen Stage-A branch and private scientific
history remain local.
