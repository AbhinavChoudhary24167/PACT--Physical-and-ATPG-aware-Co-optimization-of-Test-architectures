#!/usr/bin/env bash
set -uo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
OUT="$ROOT/artifacts/raw/tool_qualification/openroad"
PKG_DIR="$ROOT/external/openroad_prebuilt"
VERSION='26Q2-1164-g08f67ee5ec'
NAME="openroad_${VERSION}_amd64-ubuntu-24.04.deb"
URL="https://vaultlink.precisioninno.com/api/releases/${VERSION}/${NAME}/download"
mkdir -p "$OUT" "$PKG_DIR"
printf '%s\n' "$URL" > "$OUT/package_url.txt"
timeout 300s curl --fail --location --show-error --silent --dump-header "$OUT/download.headers" --output "$PKG_DIR/$NAME" "$URL" > "$OUT/download.log" 2>&1
DOWNLOAD_STATUS=$?
printf '%s\n' "$DOWNLOAD_STATUS" > "$OUT/download.exit"
if [ "$DOWNLOAD_STATUS" -ne 0 ]; then exit "$DOWNLOAD_STATUS"; fi
sha256sum "$PKG_DIR/$NAME" > "$OUT/package.sha256"
DEBIAN_FRONTEND=noninteractive timeout 300s apt-get install -y "$PKG_DIR/$NAME" > "$OUT/install.log" 2>&1
INSTALL_STATUS=$?
printf '%s\n' "$INSTALL_STATUS" > "$OUT/install.exit"
if [ "$INSTALL_STATUS" -ne 0 ]; then exit "$INSTALL_STATUS"; fi
timeout 20s openroad -version > "$OUT/version.log" 2>&1 || timeout 20s openroad --version >> "$OUT/version.log" 2>&1
