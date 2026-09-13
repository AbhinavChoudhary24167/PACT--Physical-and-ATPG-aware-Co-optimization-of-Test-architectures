#!/usr/bin/env bash
set -uo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
VENV="${PACT_VENV:?Set PACT_VENV}"
OUT="$ROOT/artifacts/raw/orfs_smoke/s9234"
mkdir -p "$OUT"
timeout 60s "$VENV/bin/python" "$ROOT/scripts/establish_s5378_identity.py" --design s9234 > "$OUT/identity.log" 2>&1
status=$?
printf '%s\n' "$status" > "$OUT/identity.exit"
sha256sum "$OUT/identity.log" > "$OUT/identity.sha256"
exit "$status"
