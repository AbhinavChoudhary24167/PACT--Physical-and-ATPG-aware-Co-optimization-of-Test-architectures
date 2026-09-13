#!/usr/bin/env bash
set -uo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ORFS_ROOT="${PACT_ORFS_ROOT:?Set PACT_ORFS_ROOT}"
STAGE="${1:?Pass place or route}"
case "$STAGE" in place|route) ;; *) echo "Invalid stage: $STAGE" >&2; exit 2;; esac
OUT="$ROOT/artifacts/raw/orfs_smoke/s9234"
mkdir -p "$OUT"
git -C "$ORFS_ROOT" rev-parse HEAD > "$OUT/orfs.commit"
timeout 600s make -C "$ORFS_ROOT/flow" \
  DESIGN_CONFIG="$ROOT/experiments/phase0/s9234_orfs/config.mk" \
  OPENROAD_EXE="$(command -v openroad)" YOSYS_EXE="$(command -v yosys)" \
  "$STAGE" > "$OUT/$STAGE.log" 2>&1
status=$?
printf '%s\n' "$status" > "$OUT/$STAGE.exit"
sha256sum "$OUT/$STAGE.log" > "$OUT/$STAGE.sha256"
exit "$status"
