#!/usr/bin/env bash
set -uo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ORFS_ROOT="${PACT_ORFS_ROOT:?Set PACT_ORFS_ROOT}"
OUT="$ROOT/artifacts/raw/orfs_smoke/s9234"
mkdir -p "$OUT/metrics"
export PACT_ORFS_BLOCK=s9234f PACT_ORFS_OUT="$OUT"
timeout 90s openroad -no_init -exit "$ROOT/scripts/tcl/export_orfs_placement.tcl" > "$OUT/export.log" 2>&1
status=$?
printf '%s\n' "$status" > "$OUT/export.exit"
if [ "$status" -ne 0 ]; then exit "$status"; fi
for file in "$ORFS_ROOT"/flow/logs/nangate45/s9234f/base/*.json; do cp "$file" "$OUT/metrics/"; done
cd "$ROOT" || exit 2
sha256sum artifacts/raw/orfs_smoke/s9234/placed.def artifacts/raw/orfs_smoke/s9234/placed.v artifacts/raw/orfs_smoke/s9234/metrics/*.json > "$OUT/export.sha256"
