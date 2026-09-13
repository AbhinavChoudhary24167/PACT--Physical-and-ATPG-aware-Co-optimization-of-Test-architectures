#!/usr/bin/env bash
set -uo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ORFS_ROOT="${PACT_ORFS_ROOT:?Set PACT_ORFS_ROOT}"
VARIANT="${PACT_ORFS_VARIANT:?Set PACT_ORFS_VARIANT}"
case "$VARIANT" in base|nearest_neighbor) ;; *) echo 'Unsupported variant' >&2; exit 2;; esac
OUT="$ROOT/artifacts/raw/orfs_physical/s5378/$VARIANT"
mkdir -p "$OUT/metrics" "$OUT/reports"
for file in "$ORFS_ROOT"/flow/logs/nangate45/s5378/"$VARIANT"/*.json; do cp "$file" "$OUT/metrics/"; done
for file in "$ORFS_ROOT"/flow/reports/nangate45/s5378/"$VARIANT"/*.rpt; do cp "$file" "$OUT/reports/"; done
cd "$ROOT" || exit 2
find "artifacts/raw/orfs_physical/s5378/$VARIANT" -type f ! -name '*.sha256' -print0 | sort -z | xargs -0 sha256sum > "$OUT/files.sha256"
