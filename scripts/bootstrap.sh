#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
VENV="${PACT_VENV:-$ROOT/.venv}"
timeout 120s python3 -m venv "$VENV"
timeout 600s "$VENV/bin/python" -m pip install -e "$ROOT[dev]"
mkdir -p "$ROOT/artifacts/manifests"
"$VENV/bin/python" -m pip freeze > "$ROOT/artifacts/manifests/python-packages.txt"
printf '%s\n' "$VENV"
