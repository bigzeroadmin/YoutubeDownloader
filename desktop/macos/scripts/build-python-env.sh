#!/usr/bin/env bash
# Build a standalone Python 3.12 environment with project dependencies
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
DESKTOP_DIR="$SCRIPT_DIR/.."
RESOURCES_DIR="$DESKTOP_DIR/resources"
BACKEND_DIR="$DESKTOP_DIR/../shared/backend"
PYTHON_DIR="$RESOURCES_DIR/python"

PYTHON_BIN="$PYTHON_DIR/bin/python3.12"

# ---------------------------------------------------------------------------
# Download python-build-standalone (relocatable Python 3.12)
# ---------------------------------------------------------------------------
if [ -f "$PYTHON_BIN" ]; then
  echo "[python] Already exists at $PYTHON_BIN, skipping download."
else
  echo "[python] Downloading python-build-standalone 3.12 for macOS ARM64..."

  PY_TAG="20260414"
  PY_RELEASE="cpython-3.12.13+${PY_TAG}-aarch64-apple-darwin-install_only.tar.gz"
  PY_URL="https://github.com/astral-sh/python-build-standalone/releases/download/${PY_TAG}/${PY_RELEASE}"
  PY_TMP="$RESOURCES_DIR/python_tmp.tar.gz"

  mkdir -p "$RESOURCES_DIR"
  curl -L -o "$PY_TMP" "$PY_URL"
  tar xzf "$PY_TMP" -C "$RESOURCES_DIR/"
  rm -f "$PY_TMP"

  echo "[python] Installed: $("$PYTHON_BIN" --version)"
fi

# ---------------------------------------------------------------------------
# Install Python dependencies (excluding redis)
# ---------------------------------------------------------------------------
echo "[python] Installing Python dependencies..."

# Create a desktop-specific requirements file (no redis)
REQUIREMENTS_DESKTOP="$RESOURCES_DIR/requirements-desktop.txt"
grep -v -i "^redis" "$BACKEND_DIR/requirements.txt" > "$REQUIREMENTS_DESKTOP" || true

"$PYTHON_BIN" -m pip install \
  --upgrade pip \
  --quiet 2>/dev/null || true

"$PYTHON_BIN" -m pip install \
  -r "$REQUIREMENTS_DESKTOP" \
  --quiet

echo ""
echo "=== Python environment ready ==="
echo "Python: $("$PYTHON_BIN" --version)"
