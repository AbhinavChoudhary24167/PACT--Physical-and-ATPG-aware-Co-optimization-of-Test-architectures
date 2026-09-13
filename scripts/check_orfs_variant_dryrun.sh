#!/usr/bin/env bash
set -uo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ORFS_ROOT="${PACT_ORFS_ROOT:?Set PACT_ORFS_ROOT}"
OUT="$ROOT/artifacts/raw/orfs_rewire/s5378/nearest_neighbor"
mkdir -p "$OUT"
target='./results/nangate45/s5378/nearest_neighbor'
timeout 30s make -n -C "$ORFS_ROOT/flow" \
  -o "$target/3_place.odb" -o "$target/3_place.sdc" \
  DESIGN_CONFIG="$ROOT/experiments/phase0/s5378_orfs/config_nearest.mk" \
  OPENROAD_EXE="$(command -v openroad)" YOSYS_EXE="$(command -v yosys)" \
  route > "$OUT/route_dryrun.log" 2>&1
status=$?
printf '%s\n' "$status" > "$OUT/route_dryrun.exit"
exit "$status"
