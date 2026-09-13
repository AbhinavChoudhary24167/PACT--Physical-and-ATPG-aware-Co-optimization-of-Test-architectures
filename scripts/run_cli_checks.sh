#!/usr/bin/env bash
set -uo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
VENV="${PACT_VENV:?Set PACT_VENV}"
export PACT_ORFS_ROOT="${PACT_ORFS_ROOT:?Set PACT_ORFS_ROOT}"
export PACT_FAN_ATPG_ROOT="${PACT_FAN_ATPG_ROOT:?Set PACT_FAN_ATPG_ROOT}"
DESIGN="${PACT_DESIGN:-s5378}"
case "$DESIGN" in s5378) OUT="$ROOT/artifacts/raw/cli_checks"; FIGURES=reports/figures;; s9234) OUT="$ROOT/artifacts/raw/cli_checks/s9234"; FIGURES=reports/figures/s9234;; *) echo 'Unsupported design' >&2; exit 2;; esac
mkdir -p "$OUT"
cd "$ROOT" || exit 2
timeout 90s "$VENV/bin/python" -m pact.cli doctor > "$OUT/doctor.json" 2> "$OUT/doctor.err"
printf '%s\n' "$?" > "$OUT/doctor.exit"
timeout 30s "$VENV/bin/python" -m pact.cli validate-scan \
  --architecture "artifacts/derived/$DESIGN/supplied_architecture.json" > "$OUT/validate.json" 2> "$OUT/validate.err"
printf '%s\n' "$?" > "$OUT/validate.exit"
timeout 180s "$VENV/bin/python" -m pact.cli shift-activity \
  --architecture "artifacts/derived/phase0/smoke_$DESIGN/nearest_neighbor.architecture.json" \
  --patterns "artifacts/raw/tool_qualification/fan_atpg/patterns/FAN_$DESIGN.pat" \
  --ff-map "artifacts/derived/$DESIGN/ff_identity_map.json" \
  --out "artifacts/derived/phase0/$DESIGN/nearest_cli_activity.json" > "$OUT/shift.log" 2>&1
printf '%s\n' "$?" > "$OUT/shift.exit"
timeout 60s "$VENV/bin/python" -m pact.cli compare \
  --results "artifacts/derived/phase0/$DESIGN/results.jsonl" \
  --out "artifacts/derived/phase0/$DESIGN/comparison.json" > "$OUT/compare.log" 2>&1
printf '%s\n' "$?" > "$OUT/compare.exit"
timeout 180s "$VENV/bin/python" -m pact.cli plot \
  --results "artifacts/derived/phase0/$DESIGN/results.jsonl" \
  --output "$FIGURES" > "$OUT/plot.log" 2>&1
printf '%s\n' "$?" > "$OUT/plot.exit"
sha256sum "$OUT"/*.log "$OUT"/*.json > "$OUT/checks.sha256"
if grep -qv '^0$' "$OUT"/*.exit; then exit 1; fi
