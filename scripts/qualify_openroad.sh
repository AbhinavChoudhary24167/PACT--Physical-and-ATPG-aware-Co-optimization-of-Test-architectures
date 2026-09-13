#!/usr/bin/env bash
set -uo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SOURCE="/root/pact-deps/OpenROAD"
RUN="/root/pact-deps/PACT-dft-run"
OUT="$ROOT/artifacts/raw/tool_qualification/openroad"
mkdir -p "$RUN" "$OUT/results"
if [ ! -d "$SOURCE/src/dft/test" ]; then
  echo 'OpenROAD source regression fixtures missing' > "$OUT/regression.blocker"
  exit 2
fi
for file in "$SOURCE"/src/dft/test/*; do
  name="$(basename "$file")"
  if [ ! -e "$RUN/$name" ]; then ln -s "$file" "$RUN/$name"; fi
done
if [ ! -e "$RUN/sky130hd" ]; then ln -s "$SOURCE/test/sky130hd" "$RUN/sky130hd"; fi
export RESULTS_DIR="$OUT/results"
export PACT_DFT_OUT="$OUT"
cd "$RUN" || exit 2
for case in one_cell_sky130 place_sort_sky130; do
  timeout 120s openroad -no_init -exit "$case.tcl" > "$OUT/$case.log" 2>&1
  status=$?
  printf '%s\n' "$status" > "$OUT/$case.exit"
done
timeout 120s openroad -no_init -exit "$ROOT/scripts/tcl/qualify_scan_opt.tcl" > "$OUT/scan_opt.log" 2>&1
status=$?
printf '%s\n' "$status" > "$OUT/scan_opt.exit"
if [ "$status" -eq 0 ] && [ -f "$OUT/before_scan_opt.v" ] && [ -f "$OUT/after_scan_opt.v" ]; then
  sha256sum "$OUT/before_scan_opt.v" "$OUT/after_scan_opt.v" > "$OUT/scan_opt_netlists.sha256"
  cmp -s "$OUT/before_scan_opt.v" "$OUT/after_scan_opt.v"
  printf '%s\n' "$?" > "$OUT/scan_opt_netlist_cmp.exit"
fi
sha256sum "$OUT"/*.log > "$OUT/qualification_logs.sha256"
