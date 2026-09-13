#!/usr/bin/env bash
set -uo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SOURCE="/root/pact-deps/FAN_ATPG"
OUT="$ROOT/artifacts/raw/tool_qualification/fan_atpg"
mkdir -p "$OUT/patterns" "$OUT/reports" "$OUT/benchmarks"
cd "$SOURCE" || exit 2
for design in s27 s5378 s9234 s15850; do
  timeout 180s ./bin/opt/fan -f "script/fanScripts/atpg_${design}.script" > "$OUT/${design}.atpg.log" 2>&1
  atpg_status=$?
  printf '%s\n' "$atpg_status" > "$OUT/${design}.atpg.exit"
  if [ "$atpg_status" -ne 0 ]; then continue; fi
  for ext in pat stil; do
    if [ -f "pat/FAN_${design}.${ext}" ]; then cp "pat/FAN_${design}.${ext}" "$OUT/patterns/"; fi
  done
  if [ -f "rpt/FAN_${design}.rpt" ]; then cp "rpt/FAN_${design}.rpt" "$OUT/reports/"; fi
  timeout 180s ./bin/opt/fan -f "script/fanScripts/fsim_${design}.script" > "$OUT/${design}.fsim.log" 2>&1
  fsim_status=$?
  printf '%s\n' "$fsim_status" > "$OUT/${design}.fsim.exit"
  if [ -f "rpt/${design}_fsim.rpt" ]; then cp "rpt/${design}_fsim.rpt" "$OUT/reports/"; fi
  cp "mod_netlist/${design}.v" "$OUT/benchmarks/"
done
git status --porcelain > "$OUT/source_after_examples.status"
cd "$ROOT" || exit 2
find artifacts/raw/tool_qualification/fan_atpg -type f ! -name '*.sha256' -print0 | sort -z | xargs -0 sha256sum > "$OUT/examples.sha256"
