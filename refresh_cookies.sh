#!/usr/bin/env bash
#
# Automatically extract YouTube cookies from your browser
# and write them to cookies.txt for the Docker containers.
#
# Usage:
#   ./refresh_cookies.sh          # defaults to edge
#   ./refresh_cookies.sh chrome   # use chrome
#   ./refresh_cookies.sh firefox  # use firefox
#
# To auto-refresh daily, add to crontab:
#   crontab -e
#   0 9 * * * /path/to/YoutubeDownload/refresh_cookies.sh edge >> /tmp/cookie_refresh.log 2>&1

set -euo pipefail

BROWSER="${1:-edge}"
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
COOKIE_FILE="$SCRIPT_DIR/cookies.txt"

echo "[$(date)] Refreshing YouTube cookies from $BROWSER..."

if command -v yt-dlp &> /dev/null; then
    YTDLP="yt-dlp"
elif python3 -m yt_dlp --version &> /dev/null; then
    YTDLP="python3 -m yt_dlp"
else
    echo "ERROR: yt-dlp not found. Install with: pip3 install yt-dlp"
    exit 1
fi

# Clear stale cookies to prevent interference
echo "# Netscape HTTP Cookie File" > "$COOKIE_FILE"

$YTDLP \
    --cookies-from-browser "$BROWSER" \
    --cookies "$COOKIE_FILE" \
    --skip-download \
    --quiet \
    "https://www.youtube.com/watch?v=jNQXAC9IVRw" 2>&1 | grep -v "^Deprecated"

LINES=$(grep -c -v '^#\|^$' "$COOKIE_FILE" 2>/dev/null || echo 0)
echo "[$(date)] Done. $LINES cookies written to $COOKIE_FILE"

# If containers are running, notify them (file is bind-mounted, no restart needed)
if docker compose ps --status running 2>/dev/null | grep -q api; then
    echo "[$(date)] Containers are running — cookies will be picked up automatically."
fi
