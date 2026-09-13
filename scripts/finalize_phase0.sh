#!/usr/bin/env bash
# Recheck already saved campaigns, generate figures, and freeze their hashes.
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
: "${PACT_VENV:?Set PACT_VENV}"
: "${PACT_ORFS_ROOT:?Set PACT_ORFS_ROOT}"
: "${PACT_FAN_ATPG_ROOT:?Set PACT_FAN_ATPG_ROOT}"
OUT="$ROOT/artifacts/raw/final_checks"
mkdir -p "$OUT"
cd "$ROOT"
bash scripts/run_tests.sh
bash scripts/run_cli_checks.sh
PACT_DESIGN=s9234 bash scripts/run_cli_checks.sh
timeout 60s "$PACT_VENV/bin/python" scripts/merge_phase0_results.py > "$OUT/merge.log" 2>&1
timeout 60s "$PACT_VENV/bin/python" -m pact.cli compare \
  --results artifacts/derived/phase0/results.jsonl \
  --out artifacts/derived/phase0/comparison_all.json > "$OUT/compare.log" 2>&1
timeout 60s "$PACT_VENV/bin/python" scripts/freeze_evidence.py > "$OUT/freeze.log" 2>&1
printf '0\n' > "$OUT/finalize.exit"
