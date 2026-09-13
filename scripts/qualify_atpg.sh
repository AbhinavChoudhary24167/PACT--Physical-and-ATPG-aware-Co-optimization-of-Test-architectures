#!/usr/bin/env bash
set -uo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SOURCE="/root/pact-deps/FAN_ATPG"
OUT="$ROOT/artifacts/raw/tool_qualification/fan_atpg"
mkdir -p "$OUT" /root/pact-deps
if [ ! -e "$SOURCE" ]; then
  timeout 300s git clone --depth=1 https://github.com/NTU-LaDS-II/FAN_ATPG.git "$SOURCE" > "$OUT/clone.log" 2>&1
  status=$?
  printf '%s\n' "$status" > "$OUT/clone.exit"
  if [ "$status" -ne 0 ]; then exit "$status"; fi
fi
git -C "$SOURCE" rev-parse HEAD > "$OUT/commit"
git -C "$SOURCE" remote get-url origin > "$OUT/url"
sha256sum "$SOURCE/LICENSE" > "$OUT/license.sha256"
timeout 300s make -C "$SOURCE" -j2 > "$OUT/build.log" 2>&1
status=$?
printf '%s\n' "$status" > "$OUT/build.exit"
if [ "$status" -ne 0 ]; then exit "$status"; fi
git -C "$SOURCE" status --porcelain > "$OUT/source.status"
find "$SOURCE/script" -maxdepth 3 -type f -name '*s27*' -o -name '*s5378*' -o -name '*s9234*' -o -name '*s15850*' > "$OUT/available_example_scripts.txt"
