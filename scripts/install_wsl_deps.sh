#!/usr/bin/env bash
set -uo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
OUT="$ROOT/artifacts/raw/tool_qualification/environment"
mkdir -p "$OUT"
date -u +'%Y-%m-%dT%H:%M:%SZ' > "$OUT/apt-start.txt"
timeout 900s apt-get update > "$OUT/apt-update.log" 2>&1
UPDATE_STATUS=$?
printf '%s\n' "$UPDATE_STATUS" > "$OUT/apt-update.exit"
if [ "$UPDATE_STATUS" -ne 0 ]; then exit "$UPDATE_STATUS"; fi
DEBIAN_FRONTEND=noninteractive timeout 900s apt-get install -y bison flex build-essential cmake yosys klayout > "$OUT/apt-install.log" 2>&1
INSTALL_STATUS=$?
printf '%s\n' "$INSTALL_STATUS" > "$OUT/apt-install.exit"
sha256sum "$OUT"/apt-*.log > "$OUT/apt.sha256"
exit "$INSTALL_STATUS"
