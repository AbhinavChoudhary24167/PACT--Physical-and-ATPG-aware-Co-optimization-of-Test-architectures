#!/usr/bin/env bash
set -uo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ORFS_ROOT="${PACT_ORFS_ROOT:?Set PACT_ORFS_ROOT}"
VARIANT="${PACT_ORFS_VARIANT:?Set PACT_ORFS_VARIANT}"
case "$VARIANT" in base|nearest_neighbor) ;; *) echo 'Unsupported variant' >&2; exit 2;; esac
DESIGN="${PACT_DESIGN:-s5378}"
case "$DESIGN" in s5378) BLOCK=s5378;; s9234) BLOCK=s9234f;; *) echo 'Unsupported design' >&2; exit 2;; esac
OUT="$ROOT/artifacts/raw/orfs_physical/$DESIGN/$VARIANT"
mkdir -p "$OUT/metrics" "$OUT/reports"
for file in "$ORFS_ROOT"/flow/logs/nangate45/"$BLOCK"/"$VARIANT"/*.json; do cp "$file" "$OUT/metrics/"; done
for file in "$ORFS_ROOT"/flow/reports/nangate45/"$BLOCK"/"$VARIANT"/*.rpt; do cp "$file" "$OUT/reports/"; done
cd "$ROOT" || exit 2
find "artifacts/raw/orfs_physical/$DESIGN/$VARIANT" -type f ! -name '*.sha256' -print0 | sort -z | xargs -0 sha256sum > "$OUT/files.sha256"
