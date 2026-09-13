#!/usr/bin/env bash
set -uo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
VENV="${PACT_VENV:?Set PACT_VENV}"
OUT="$ROOT/artifacts/raw/orfs_smoke/s9234"
mkdir -p "$OUT"
timeout 30s "$VENV/bin/python" "$ROOT/scripts/translate_fan_benchmark.py" --design s9234 > "$OUT/translate.log" 2>&1
status=$?
printf '%s\n' "$status" > "$OUT/translate.exit"
sha256sum "$OUT/translate.log" > "$OUT/translate.sha256"
exit "$status"
