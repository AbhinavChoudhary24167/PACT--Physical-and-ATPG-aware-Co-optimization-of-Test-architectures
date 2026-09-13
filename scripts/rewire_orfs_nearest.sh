#!/usr/bin/env bash
set -uo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ORFS_ROOT="${PACT_ORFS_ROOT:?Set PACT_ORFS_ROOT}"
VENV="${PACT_VENV:?Set PACT_VENV}"
DESIGN="${PACT_DESIGN:-s5378}"
case "$DESIGN" in s5378) BLOCK=s5378;; s9234) BLOCK=s9234f;; *) echo 'Unsupported design' >&2; exit 2;; esac
OUT="$ROOT/artifacts/raw/orfs_rewire/$DESIGN/nearest_neighbor"
VARIANT="$ORFS_ROOT/flow/results/nangate45/$BLOCK/nearest_neighbor"
mkdir -p "$OUT" "$VARIANT"
timeout 30s "$VENV/bin/python" "$ROOT/scripts/prepare_rewire_s5378.py" --design "$DESIGN" > "$OUT/prepare.log" 2>&1
status=$?
printf '%s\n' "$status" > "$OUT/prepare.exit"
if [ "$status" -ne 0 ]; then exit "$status"; fi
export PACT_BASE_ODB="$ORFS_ROOT/flow/results/nangate45/$BLOCK/base/3_place.odb"
export PACT_VARIANT_ODB="$VARIANT/3_place.odb"
export PACT_REWIRE_TCL="$ROOT/artifacts/derived/phase0/smoke_$DESIGN/nearest_neighbor.rewire.tcl"
export PACT_REWIRE_OUT="$OUT"
timeout 90s openroad -no_init -exit "$ROOT/scripts/tcl/rewire_scan.tcl" > "$OUT/rewire.log" 2>&1
status=$?
printf '%s\n' "$status" > "$OUT/rewire.exit"
if [ "$status" -ne 0 ]; then exit "$status"; fi
cp "$ORFS_ROOT/flow/results/nangate45/$BLOCK/base/3_place.sdc" "$VARIANT/3_place.sdc"
cd "$ROOT" || exit 2
sha256sum "artifacts/raw/orfs_rewire/$DESIGN/nearest_neighbor/rewired.def" "artifacts/raw/orfs_rewire/$DESIGN/nearest_neighbor/rewired.v" > "$OUT/rewired.sha256"
