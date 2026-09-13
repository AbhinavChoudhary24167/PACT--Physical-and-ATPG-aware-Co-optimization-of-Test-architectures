#!/usr/bin/env bash
set -uo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ORFS_ROOT="${PACT_ORFS_ROOT:?Set PACT_ORFS_ROOT to the pinned ORFS checkout}"
OUT="$ROOT/artifacts/raw/orfs_smoke/s5378"
mkdir -p "$OUT"
timeout 300s make -C "$ORFS_ROOT/flow" \
  DESIGN_CONFIG="$ROOT/experiments/phase0/s5378_orfs/config.mk" \
  OPENROAD_EXE="$(command -v openroad)" \
  YOSYS_EXE="$(command -v yosys)" \
  route > "$OUT/route.place-fixed.log" 2>&1
status=$?
printf '%s\n' "$status" > "$OUT/route.place-fixed.exit"
sha256sum "$OUT/route.place-fixed.log" > "$OUT/route.place-fixed.sha256"
exit "$status"
