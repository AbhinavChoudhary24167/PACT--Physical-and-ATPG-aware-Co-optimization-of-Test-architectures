#!/usr/bin/env bash
set -uo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ORFS_ROOT="${PACT_ORFS_ROOT:?Set PACT_ORFS_ROOT to the pinned ORFS checkout}"
OUT="$ROOT/artifacts/raw/orfs_smoke/s5378"
CONFIG="${PACT_DESIGN_CONFIG:-$ROOT/experiments/phase0/s5378_orfs/config.mk}"
TAG="${PACT_SMOKE_TAG:-translated}"
mkdir -p "$OUT"
git -C "$ORFS_ROOT" rev-parse HEAD > "$OUT/orfs.commit"
timeout 300s make -C "$ORFS_ROOT/flow" \
  DESIGN_CONFIG="$CONFIG" \
  OPENROAD_EXE="$(command -v openroad)" \
  YOSYS_EXE="$(command -v yosys)" \
  place > "$OUT/${TAG}.place.log" 2>&1
status=$?
printf '%s\n' "$status" > "$OUT/${TAG}.place.exit"
sha256sum "$OUT/${TAG}.place.log" > "$OUT/${TAG}.place.sha256"
exit "$status"
