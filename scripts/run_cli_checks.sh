#!/usr/bin/env bash
set -uo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
VENV="${PACT_VENV:?Set PACT_VENV}"
export PACT_ORFS_ROOT="${PACT_ORFS_ROOT:?Set PACT_ORFS_ROOT}"
export PACT_FAN_ATPG_ROOT="${PACT_FAN_ATPG_ROOT:?Set PACT_FAN_ATPG_ROOT}"
OUT="$ROOT/artifacts/raw/cli_checks"
mkdir -p "$OUT"
cd "$ROOT" || exit 2
timeout 90s "$VENV/bin/python" -m pact.cli doctor > "$OUT/doctor.json" 2> "$OUT/doctor.err"
printf '%s\n' "$?" > "$OUT/doctor.exit"
timeout 30s "$VENV/bin/python" -m pact.cli validate-scan \
  --architecture artifacts/derived/s5378/supplied_architecture.json > "$OUT/validate.json" 2> "$OUT/validate.err"
printf '%s\n' "$?" > "$OUT/validate.exit"
timeout 180s "$VENV/bin/python" -m pact.cli shift-activity \
  --architecture artifacts/derived/phase0/smoke_s5378/nearest_neighbor.architecture.json \
  --patterns artifacts/raw/tool_qualification/fan_atpg/patterns/FAN_s5378.pat \
  --ff-map artifacts/derived/s5378/ff_identity_map.json \
  --out artifacts/derived/phase0/s5378/nearest_cli_activity.json > "$OUT/shift.log" 2>&1
printf '%s\n' "$?" > "$OUT/shift.exit"
timeout 60s "$VENV/bin/python" -m pact.cli compare \
  --results artifacts/derived/phase0/s5378/results.jsonl \
  --out artifacts/derived/phase0/s5378/comparison.json > "$OUT/compare.log" 2>&1
printf '%s\n' "$?" > "$OUT/compare.exit"
timeout 180s "$VENV/bin/python" -m pact.cli plot \
  --results artifacts/derived/phase0/s5378/results.jsonl \
  --output reports/figures > "$OUT/plot.log" 2>&1
printf '%s\n' "$?" > "$OUT/plot.exit"
sha256sum "$OUT"/*.log "$OUT"/*.json > "$OUT/checks.sha256"
if grep -qv '^0$' "$OUT"/*.exit; then exit 1; fi
