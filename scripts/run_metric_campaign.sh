#!/usr/bin/env bash
set -uo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
VENV="${PACT_VENV:?Set PACT_VENV to the qualified Python environment}"
DESIGN="${PACT_DESIGN:-s5378}"
case "$DESIGN" in s5378|s9234) ;; *) echo 'Unsupported design' >&2; exit 2;; esac
OUT="$ROOT/artifacts/raw/metric_campaign/$DESIGN"
mkdir -p "$OUT"
timeout 600s "$VENV/bin/python" "$ROOT/scripts/run_metric_campaign.py" --design "$DESIGN" > "$OUT/run.log" 2>&1
status=$?
printf '%s\n' "$status" > "$OUT/run.exit"
sha256sum "$OUT/run.log" > "$OUT/run.sha256"
exit "$status"
