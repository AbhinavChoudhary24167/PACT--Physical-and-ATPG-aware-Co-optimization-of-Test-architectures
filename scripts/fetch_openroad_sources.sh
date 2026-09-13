#!/usr/bin/env bash
set -uo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
OUT="$ROOT/artifacts/raw/tool_qualification/openroad"
mkdir -p "$OUT" "$ROOT/external"
for name in OpenROAD OpenROAD-flow-scripts; do
  URL="https://github.com/The-OpenROAD-Project/${name}.git"
  DEST="/root/pact-deps/$name"
  mkdir -p /root/pact-deps
  if [ -e "$DEST" ]; then
    printf 'Existing path, no overwrite: %s\n' "$DEST" > "$OUT/${name}.clone.log"
    STATUS=0
  else
    timeout 300s git clone --depth=1 "$URL" "$DEST" > "$OUT/${name}.clone.log" 2>&1
    STATUS=$?
  fi
  printf '%s\n' "$STATUS" > "$OUT/${name}.clone.exit"
  if [ "$STATUS" -ne 0 ]; then continue; fi
  git -C "$DEST" rev-parse HEAD > "$OUT/${name}.commit"
  git -C "$DEST" remote get-url origin > "$OUT/${name}.url"
  git -C "$DEST" status --porcelain > "$OUT/${name}.status"
done
