#!/usr/bin/env bash
set -uo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
VENV="${PACT_VENV:?Set PACT_VENV to the qualified Python environment}"
OUT="$ROOT/artifacts/raw/metric_campaign/s5378"
mkdir -p "$OUT"
timeout 600s "$VENV/bin/python" "$ROOT/scripts/run_metric_campaign.py" > "$OUT/run.log" 2>&1
status=$?
printf '%s\n' "$status" > "$OUT/run.exit"
sha256sum "$OUT/run.log" > "$OUT/run.sha256"
exit "$status"
