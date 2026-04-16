#!/usr/bin/env bash
# Download ffmpeg and node ARM64 binaries for macOS
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
RESOURCES_DIR="$SCRIPT_DIR/../resources"

mkdir -p "$RESOURCES_DIR/ffmpeg" "$RESOURCES_DIR/node"

# ---------------------------------------------------------------------------
# ffmpeg – static ARM64 build
# ---------------------------------------------------------------------------
FFMPEG_BIN="$RESOURCES_DIR/ffmpeg/ffmpeg"
if [ -f "$FFMPEG_BIN" ]; then
  echo "[ffmpeg] Already exists at $FFMPEG_BIN, skipping."
else
  echo "[ffmpeg] Downloading static ARM64 build..."
  FFMPEG_URL="https://github.com/eugeneware/ffmpeg-static/releases/latest/download/darwin-arm64"
  curl -L --retry 3 --retry-delay 5 -o "$FFMPEG_BIN" "$FFMPEG_URL"
  chmod +x "$FFMPEG_BIN"
  echo "[ffmpeg] Installed."
fi

# ffprobe – try descriptinc build; optional (yt-dlp mostly needs ffmpeg only)
FFPROBE_BIN="$RESOURCES_DIR/ffmpeg/ffprobe"
if [ -f "$FFPROBE_BIN" ]; then
  echo "[ffprobe] Already exists, skipping."
else
  echo "[ffprobe] Downloading (optional)..."
  FFPROBE_URL="https://github.com/descriptinc/ffmpeg-ffprobe-static/releases/latest/download/ffprobe-darwin-arm64"
  if curl -L --fail --retry 3 --retry-delay 5 -o "$FFPROBE_BIN" "$FFPROBE_URL" 2>/dev/null && [ -s "$FFPROBE_BIN" ]; then
    chmod +x "$FFPROBE_BIN"
    echo "[ffprobe] Installed."
  else
    echo "[ffprobe] Download failed (optional, yt-dlp works without it)."
    rm -f "$FFPROBE_BIN"
  fi
fi

# ---------------------------------------------------------------------------
# Node.js – LTS ARM64 binary
# ---------------------------------------------------------------------------
NODE_BIN="$RESOURCES_DIR/node/node"
if [ -f "$NODE_BIN" ]; then
  echo "[node] Already exists at $NODE_BIN, skipping."
else
  echo "[node] Downloading Node.js LTS ARM64 binary..."
  NODE_VERSION="v22.15.0"
  NODE_TAR="node-${NODE_VERSION}-darwin-arm64.tar.gz"
  NODE_URL="https://nodejs.org/dist/${NODE_VERSION}/${NODE_TAR}"
  NODE_TMP="$RESOURCES_DIR/node_tmp.tar.gz"

  curl -L --retry 3 --retry-delay 5 -o "$NODE_TMP" "$NODE_URL"
  tar xzf "$NODE_TMP" -C "$RESOURCES_DIR/node/" --strip-components=2 "node-${NODE_VERSION}-darwin-arm64/bin/node"
  rm -f "$NODE_TMP"
  chmod +x "$NODE_BIN"
  echo "[node] Installed: $("$NODE_BIN" --version)"
fi

echo ""
echo "=== Binary dependencies ready ==="
[ -f "$FFMPEG_BIN" ] && echo "ffmpeg:  $FFMPEG_BIN"
[ -f "$FFPROBE_BIN" ] && echo "ffprobe: $FFPROBE_BIN" || echo "ffprobe: (not available)"
echo "node:    $NODE_BIN"
