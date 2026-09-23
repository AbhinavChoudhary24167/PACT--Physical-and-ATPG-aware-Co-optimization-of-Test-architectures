# Phase-2B activity model qualification

Read [phase2b_summary.md](phase2b_summary.md) for the decision and all 11 research answers.
Classification: **PACT_PHASE2B_SURROGATE_PARTIAL**. M5 qualifies for geometric ranking,
M3 for the defined capacitance-load ranking on the frozen set; no joint qualification.
Electrical energy/power remains INCOMPLETE. Phase-2A evidence remains unchanged.

Run from the PACT repository in the existing WSL environment. Exact commands and
dependencies are recorded in environment.json. Freeze is one-time and refuses
replacement; existing evidence must pass its hashes before any stage runs.

1. `scripts/phase2b_freeze.py` — one-time contract; requires native initial_git_status.txt.
2. `openroad -python -no_init -exit scripts/phase2b_extract.py` — placed-only graph and copied-route extraction.
3. `/root/pact-deps/pact-venv/bin/python scripts/phase2b_waveform.py` — independent Icarus capture checks and supplementary FF traces.
4. `OPENBLAS_NUM_THREADS=1 /root/pact-deps/pact-venv/bin/python scripts/phase2b_measure.py` — metrics with no optimizer import or search.
5. `/root/pact-deps/pact-venv/bin/python scripts/phase2b_report.py` — correlations, ranks, pairwise comparisons and figures.
6. Focused tests, then full regression (commands in environment.json).
7. `/root/pact-deps/pact-venv/bin/python scripts/phase2b_finalize.py` — report, complete manifests and integrity.

Set PYTHONDONTWRITEBYTECODE=1, PYTHONPATH=src:/mnt/d/PACT_EXPERIMENTS/cache/phase2a_python,
TMPDIR=/mnt/d/PACT_EXPERIMENTS/tmp, MPLCONFIGDIR=/mnt/d/PACT_EXPERIMENTS/cache/matplotlib.
Large artifacts stay on D:. The prior dirty source dependencies are hash-frozen in
provenance.json; the parent Git commit alone does not reconstruct that prior state.

The primary comparison uses frozen carry-loaded/no-capture/no-final-unload activity.
Supplementary load/capture/unload results never replace primary measurements.
Capacitance counts are fF-transitions with explicit coupling convention, not energy.
