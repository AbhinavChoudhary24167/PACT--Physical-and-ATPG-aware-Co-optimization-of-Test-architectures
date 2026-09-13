#!/usr/bin/env bash
set -uo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
VENV="${PACT_VENV:?Set PACT_VENV}"
DESIGN="${PACT_DESIGN:-s5378}"
case "$DESIGN" in s5378|s9234) ;; *) echo 'Unsupported design' >&2; exit 2;; esac
OUT="$ROOT/artifacts/raw/orfs_rewire/$DESIGN/nearest_neighbor"
mkdir -p "$OUT"
timeout 90s "$VENV/bin/python" "$ROOT/scripts/verify_rewire_s5378.py" --design "$DESIGN" > "$OUT/verify.log" 2>&1
status=$?
printf '%s\n' "$status" > "$OUT/verify.exit"
sha256sum "$OUT/verify.log" > "$OUT/verify.sha256"
exit "$status"
