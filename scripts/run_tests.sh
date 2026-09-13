#!/usr/bin/env bash
set -uo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
VENV="${PACT_VENV:-$ROOT/.venv}"
OUT="$ROOT/artifacts/raw/tests"
mkdir -p "$OUT"
cd "$ROOT" || exit 2
timeout 120s "$VENV/bin/python" -m pytest -q > "$OUT/pytest.log" 2>&1
status=$?
printf '%s\n' "$status" > "$OUT/pytest.exit"
sha256sum "$OUT/pytest.log" > "$OUT/pytest.sha256"
cat "$OUT/pytest.log"
exit "$status"
