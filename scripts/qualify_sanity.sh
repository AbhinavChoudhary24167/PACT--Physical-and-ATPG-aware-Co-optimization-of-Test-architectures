#!/usr/bin/env bash
set -uo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
OUT="$ROOT/artifacts/raw/benchmarks/pact_sanity"
mkdir -p "$OUT"
RTL="$ROOT/benchmarks/pact_sanity/pact_sanity.v"
timeout 120s yosys -p "read_verilog $RTL; synth -top pact_sanity; stat" > "$OUT/yosys.log" 2>&1
status=$?
printf '%s\n' "$status" > "$OUT/yosys.exit"
sha256sum "$RTL" > "$OUT/rtl.sha256"
sha256sum "$OUT/yosys.log" > "$OUT/yosys.sha256"
exit "$status"
