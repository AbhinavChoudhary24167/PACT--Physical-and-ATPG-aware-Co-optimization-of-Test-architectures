> **STOPPED_LEGACY_DEFINITION_BUG.** Read [BUG_REPORT.md](BUG_REPORT.md) and
> [FINAL_REPORT.md](FINAL_REPORT.md) first. Scientific execution is guarded;
> the commands below document the original workflow, not permission to resume.
> No valid multi-seed classification or measured speedup is claimed.

# Phase-2C reproduction

Independent registration and evidence for multi-seed M3/M5 generalization and
an exact event-driven evaluator. The [contract](EXPERIMENT_CONTRACT.md) and
[freeze](freeze.json) precede new correlations. The [Phase-2B numerical
reproduction](phase2b_reproduction.json) preserves its PARTIAL classification.

Use the existing Ubuntu-24.04 WSL environment from the repository root:

```bash
export PYTHONDONTWRITEBYTECODE=1 OPENBLAS_NUM_THREADS=1
export PYTHONPATH=src:/mnt/d/PACT_EXPERIMENTS/cache/phase2a_python
export TMPDIR=/mnt/d/PACT_EXPERIMENTS/tmp
export MPLCONFIGDIR=/mnt/d/PACT_EXPERIMENTS/cache/matplotlib
PY=/root/pact-deps/pact-venv/bin/python
# One-time registration only; deliberately refuses to overwrite an existing freeze.
$PY scripts/phase2c_freeze.py
$PY scripts/phase2c_run.py prepare
$PY scripts/phase2c_run.py smoke
$PY scripts/phase2c_run.py run --workers 4
$PY scripts/phase2c_measure.py
# Run timings after physical work finishes; three fresh processes per case/method.
$PY scripts/phase2c_benchmark.py
$PY -m pytest -q --capture=sys --basetemp=/mnt/d/PACT_EXPERIMENTS/pytest_tmp/phase2c_regression_isolated
$PY scripts/phase2c_report.py
$PY scripts/phase2c_finalize.py
```

Completed physical attempts are not repeated; an interrupted attempt stays
visible as TOOL_FAILURE. Prepared seed placements and every saved reference
remain hash-bound to the registration. The measurement cache hashes its code
and scientific dependencies. For inspection, use the existing artifacts rather
than running the one-time freeze again.

- [Final report](FINAL_REPORT.md): 14 direct answers, measured costs and limits.
- [Generalization](generalization_results.json): all frozen gates and classification.
- [Architecture matrix](architecture_matrix.json), [seed matrix](seed_matrix.json):
  every one of 105 registered cells, including failures.
- [Equivalence](evaluator_equivalence.json): integer/float/witness/rank proof.
- [Correlations](correlations.json), [rankings](rankings.json),
  [pair directions](pairwise_comparisons.json): per-seed evidence and stability.
- [Failure diagnostics](failure_diagnostics.json): per-FF contribution manifests.
- [Complexity](complexity.json), [raw timings](benchmark_raw.json): real and
  synthetic results kept separate; 100k/1M projections explicitly analytical.
- [Integrity](integrity_audit.json), [source hashes](source_provenance.json),
  [output hashes](result_provenance.json), [tests](tests.json), [commands](commands.json).

Large ODBs, SPEF, weights, execution logs, diagnostic details and their hash
manifest live at `D:/PACT_EXPERIMENTS/results/phase2c`, following PACT storage policy.
No earlier artifact, optimizer objective, frozen waveform or coefficient is changed.
