#!/usr/bin/env bash
set -u
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
OUT="$ROOT/artifacts/raw/tool_qualification/environment"
mkdir -p "$OUT"
TAG="${PACT_VERSION_TAG:-system}"
{
  date -u +'%Y-%m-%dT%H:%M:%SZ'
  uname -a
  lsb_release -a 2>&1 || cat /etc/os-release
  printf '\nCPU and RAM\n'
  lscpu 2>&1 || true
  free -h 2>&1 || true
  for tool in openroad yosys klayout python3 git make g++ cmake docker; do
    printf '\nTOOL %s\n' "$tool"
    command -v "$tool" || true
    case "$tool" in
      openroad) timeout 15s openroad -version 2>&1 || timeout 15s openroad --version 2>&1 || true ;;
      yosys) timeout 15s yosys -V 2>&1 || true ;;
      klayout) timeout 15s klayout -v 2>&1 || true ;;
      python3) python3 --version 2>&1 ;;
      git) git --version 2>&1 ;;
      make|g++|cmake|docker) timeout 15s "$tool" --version 2>&1 | head -3 || true ;;
    esac
  done
  printf '\nORFS candidate locations\n'
  for p in "$HOME/OpenROAD-flow-scripts" "$HOME/OpenROAD/OpenROAD-flow-scripts" "$HOME/Desktop/OpenROAD/OpenROAD-flow-scripts" "$HOME/Desktop/OpenROAD-flow-scripts"; do
    if [ -d "$p" ]; then printf '%s\n' "$p"; fi
  done
} > "$OUT/${TAG}.txt" 2>&1
cd "$ROOT" || exit 2
sha256sum "artifacts/raw/tool_qualification/environment/${TAG}.txt" > "$OUT/${TAG}.sha256"
printf '%s\n' "$OUT/${TAG}.txt"
