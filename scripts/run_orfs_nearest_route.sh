#!/usr/bin/env bash
set -uo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ORFS_ROOT="${PACT_ORFS_ROOT:?Set PACT_ORFS_ROOT}"
OUT="$ROOT/artifacts/raw/orfs_rewire/s5378/nearest_neighbor"
CHECK="$ROOT/artifacts/derived/phase0/smoke_s5378/nearest_neighbor.rewire_verification.json"
if [ ! -f "$CHECK" ]; then echo 'Rewire verification missing' > "$OUT/route.blocker"; exit 2; fi
if ! grep -q '"status": "PASS"' "$CHECK"; then echo 'Rewire verification failed' > "$OUT/route.blocker"; exit 2; fi
target='./results/nangate45/s5378/nearest_neighbor'
timeout 300s make -C "$ORFS_ROOT/flow" \
  -o "$target/3_place.odb" -o "$target/3_place.sdc" \
  DESIGN_CONFIG="$ROOT/experiments/phase0/s5378_orfs/config_nearest.mk" \
  OPENROAD_EXE="$(command -v openroad)" YOSYS_EXE="$(command -v yosys)" \
  route > "$OUT/route.log" 2>&1
status=$?
printf '%s\n' "$status" > "$OUT/route.exit"
sha256sum "$OUT/route.log" > "$OUT/route.sha256"
exit "$status"
