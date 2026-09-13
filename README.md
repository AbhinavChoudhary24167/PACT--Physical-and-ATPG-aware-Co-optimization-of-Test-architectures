# PACT Phase 0

PACT (Physical- and ATPG-aware Co-optimization of Test Architectures) tests whether legal scan-chain orderings create a reproducible conflict between physical scan cost and ATPG-derived shift-activity hotspots. This repository contains the experimental infrastructure, raw evidence, and a gate-based Phase-0 report. It does not contain machine learning.

The hypothesis is open. A missing tool, unverified flip-flop identity map, or failed physical rerun is recorded as a failed gate, not replaced with simulated research evidence.

## Quick start

Run from this repository in Ubuntu WSL:

```bash
./scripts/collect_versions.sh
python3 -m venv .venv
. .venv/bin/activate
pip install -e '.[dev]'
python -m pact.cli doctor
pytest -q
```

See `reports/progress.md` for the current gate status and `docs/methodology.md` for metric definitions.
