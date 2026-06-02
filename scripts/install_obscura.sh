#!/usr/bin/env bash
# Install Obscura headless browser for local development.
# Detects OS + arch, downloads the correct release, installs to /usr/local/bin.
#
# Usage:
#   ./scripts/install_obscura.sh              # install to /usr/local/bin
#   ./scripts/install_obscura.sh ./bin        # install to ./bin
#   OBSCURA_STEALTH=true ./scripts/install_obscura.sh  # note: stealth requires building from source
set -euo pipefail

INSTALL_DIR="${1:-/usr/local/bin}"
REPO="h4ckf0r0day/obscura"
BASE_URL="https://github.com/${REPO}/releases/latest/download"

OS=$(uname -s | tr '[:upper:]' '[:lower:]')
ARCH=$(uname -m)

case "${OS}-${ARCH}" in
  linux-x86_64)   ASSET="obscura-x86_64-linux.tar.gz" ;;
  darwin-arm64)   ASSET="obscura-aarch64-macos.tar.gz" ;;
  darwin-x86_64)  ASSET="obscura-x86_64-macos.tar.gz" ;;
  *)
    echo "Unsupported platform: ${OS}-${ARCH}"
    echo "Build from source: https://github.com/${REPO}#build-from-source"
    exit 1 ;;
esac

TMP=$(mktemp -d)
trap 'rm -rf "$TMP"' EXIT

echo "Downloading ${ASSET}..."
curl -fL "${BASE_URL}/${ASSET}" | tar xz -C "$TMP"

# The archive extracts obscura + obscura-worker — both must be co-located.
for BIN in obscura obscura-worker; do
  if [ -f "$TMP/$BIN" ]; then
    if [ -w "$INSTALL_DIR" ]; then
      cp "$TMP/$BIN" "${INSTALL_DIR}/${BIN}" && chmod +x "${INSTALL_DIR}/${BIN}"
    else
      sudo cp "$TMP/$BIN" "${INSTALL_DIR}/${BIN}" && sudo chmod +x "${INSTALL_DIR}/${BIN}"
    fi
    echo "Installed ${INSTALL_DIR}/${BIN}"
  fi
done

echo ""
echo "Verify: obscura fetch https://example.com --dump text --quiet"
echo "Stealth build (anti-fingerprinting): cargo build --release --features stealth"
