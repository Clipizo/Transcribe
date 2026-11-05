#!/usr/bin/env bash
# Transcribe installer for Mac and Linux.
#
#   Open Terminal, type "bash " (with a space), drag this file into the
#   window and press Enter. Or, in the Transcribe folder:  bash install.sh
#
# It downloads "uv" (a small tool that installs Python) into this folder,
# then runs app/setup_kit.py, which does the rest. Nothing is installed
# outside this folder.
set -u
KIT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$KIT" || exit 1
if [ "$(id -u)" = "0" ] && [ -n "${SUDO_USER:-}" ]; then
  # With sudo, the files would belong to the administrator and Transcribe couldn't use them later.
  echo "Please run the installer without sudo:  bash install.sh"
  echo "Transcribe installs everything inside this folder, so it doesn't need administrator rights."
  exit 1
fi
# Ignore Python settings that other programs may have left on this computer.
unset PYTHONHOME PYTHONPATH
UV_VERSION="0.13.7"   # the uv version this kit was tested with

UV_DIR="$KIT/.tools/uv"
UV="$UV_DIR/uv"
[ -x "$UV" ] || UV="$UV_DIR/bin/uv"

if [ ! -x "$UV" ]; then
  echo "Downloading uv (a small tool that installs Python for Transcribe)..."
  if command -v curl >/dev/null 2>&1; then
    curl -LsSf "https://astral.sh/uv/$UV_VERSION/install.sh" | env UV_UNMANAGED_INSTALL="$UV_DIR" sh
  elif command -v wget >/dev/null 2>&1; then
    wget -qO- "https://astral.sh/uv/$UV_VERSION/install.sh" | env UV_UNMANAGED_INSTALL="$UV_DIR" sh
  fi
  UV="$UV_DIR/uv"
  [ -x "$UV" ] || UV="$UV_DIR/bin/uv"
fi
if [ ! -x "$UV" ] && command -v uv >/dev/null 2>&1; then
  UV="$(command -v uv)"   # fall back to a uv that is already installed
fi
if [ ! -x "$UV" ]; then
  echo
  echo "Could not download uv. Check your internet connection and try again."
  echo "If it still fails, your network may block astral.sh or github.com."
  exit 1
fi

export KIT_UV="$UV"
export UV_PYTHON_INSTALL_DIR="$KIT/.tools/python"
export UV_CACHE_DIR="$KIT/.tools/uv-cache"
export UV_PYTHON_PREFERENCE="${UV_PYTHON_PREFERENCE:-only-managed}"
export UV_NO_CONFIG=1
export UV_HTTP_TIMEOUT=300 UV_HTTP_CONNECT_TIMEOUT=60 UV_HTTP_RETRIES=8
chmod +x "$KIT/transcribe.sh" 2>/dev/null || true
"$UV" run --no-project --python 3.12 "$KIT/app/setup_kit.py" "$@"
