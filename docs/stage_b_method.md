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

This public export contains method source, tests and measured result tables.
Portable model inputs, selected architecture files, raw databases, waveforms and
execution receipts remain in the local scientific record. The portable loader
was independently checked against saved scores for all three starts and all three
routed selections on each design. The campaign's executed optimizer bytes match
the published optimizer.

Install the project with its optimizer dependencies and run the focused tests:

```sh
python -m pip install -e '.[optimizer,dev]'
python -m pytest -q tests/unit/test_stage_b.py
```

The generic search runner accepts a supplied `pact_stage_b_inputs_v1` bundle:

```sh
OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 NUMBA_NUM_THREADS=1 \
  python scripts/pact_stage_b_search.py \
  --input supplied_model.json.gz --output scratch/stage_b \
  --seconds 300 --epsilons 0.02 0.05 0.10
```

The bundle schema is defined by `stage_b_inputs.load_bundle`: canonical scan
architecture, load/response arrays, capacitances, ports, bounds, physical
sensitivity arrays, topology, primary-input states, depth, labelled starting
orders and the externally chosen reference label. It accepts JSON or gzip JSON.
Choose an output directory with sufficient free space; saved searches are never
overwritten. Defaults use seed 11, 20,000 evaluations and a 2,000-attempt
no-improvement window. Initialization and retained-candidate replay are separate
from the mutation-loop wall-clock budget; an indivisible evaluation may finish
after the budget. Wall-clock termination can change endpoints across machines.

The generic runner produces architectures and predictor scores. Measured result
CSVs use the frozen Nangate45/ORFS flow, route seed 11, two route cores, FAN
schedule, all-data ground-plus-pin capacitance and global-route timing.

Public result tables:

- `candidate_results.csv`: winners at all three proxy budgets.
- `search_configuration.csv`: actual solver time, evaluations and termination.
- `routed_results.csv`: every selected routed/measured outcome.
- `comparison.csv`: exact deltas and both dominance definitions versus B2/B3T/P0.
- `prediction_transfer.csv`: proxy-to-measured activity transfer.
- `stage_a_comparator.csv`: all frozen comparator points and qualification statuses.
- `s15850_hotspot_diagnostic.csv` and `s15850_background_probe.csv`: aggregate
  saved-count coverage diagnostics. The background probe is separate from the
  executed method.

The publication branch contains a single method/results commit based on the
existing public main branch. The frozen Stage-A branch and private scientific
history remain local.
