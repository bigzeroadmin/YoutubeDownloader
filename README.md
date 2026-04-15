# YouTube Downloader (Private Deployment)

A self-hosted YouTube video/audio download service powered by yt-dlp, FastAPI, Redis, and Nginx.

## Features

- Paste a YouTube URL and browse all available formats (resolution, codec, size)
- Download video in any available quality (360p / 720p / 1080p / 4K)
- DASH video+audio automatic merge via ffmpeg
- Audio extraction (m4a) and MP3 conversion
- Async task queue with progress tracking and retry
- Auto-cleanup of expired files
- Rate limiting via Nginx

## Architecture

```
User -> Nginx (port 8080) -> FastAPI API -> Redis Queue -> Worker (yt-dlp + ffmpeg)
```

## Quick Start

### Prerequisites

- Docker & Docker Compose
- yt-dlp installed on the host (`pip install yt-dlp`)
- A browser (Edge/Chrome/Firefox) logged in to YouTube

### 1. Export cookies (one command)

```bash
./refresh_cookies.sh        # defaults to Edge
./refresh_cookies.sh chrome # or Chrome
```

This auto-extracts YouTube cookies from your browser into `cookies.txt`. No browser extension needed.

To auto-refresh daily (optional):

```bash
crontab -e
# add:
0 9 * * * /path/to/YoutubeDownload/refresh_cookies.sh edge >> /tmp/cookie_refresh.log 2>&1
```

### 2. Start services

```bash
docker compose up -d --build
```

### 3. Open the app

Visit `http://localhost:8080` in your browser.

### Check auth status

```bash
curl http://localhost:8080/api/auth/status
```

## Alternative: Manual Cookie Export

If `refresh_cookies.sh` does not work for your setup:

1. Install browser extension: [Get cookies.txt LOCALLY](https://chromewebstore.google.com/detail/get-cookiestxt-locally/cclelndahbckbenkjhflpdbgdldlbecc)
2. Visit [youtube.com](https://www.youtube.com) while logged in
3. Export cookies and save as `cookies.txt` in the project root

## Alternative: Browser Auto-Read (local dev only)

For development without Docker, set environment variables:

```bash
export AUTH_MODE=browser
export COOKIES_FROM_BROWSER=edge
```

### Stop

```bash
docker compose down
```

## Local Development (without Docker)

```bash
# Start Redis
redis-server &

# Install Python dependencies
cd backend
pip install -r requirements.txt

# Run API server
uvicorn app.main:app --reload --port 8000

# Run worker (in another terminal)
cd backend
python -m app.worker
```

Then open `frontend/index.html` directly, or run:

```bash
cd frontend && python -m http.server 3000
```

and set the API base to `http://localhost:8000/api` in `app.js`.

## API Reference

| Method | Path              | Description               |
|--------|-------------------|---------------------------|
| GET    | `/api/auth/status` | Check authentication status |
| POST   | `/api/resolve`    | Extract available formats |
| POST   | `/api/download`   | Create download task      |
| GET    | `/api/tasks/:id`  | Query task status         |
| GET    | `/api/files/:id`  | Download completed file   |

### POST /api/resolve

```json
{ "url": "https://www.youtube.com/watch?v=..." }
```

### POST /api/download

```json
{
  "url": "https://www.youtube.com/watch?v=...",
  "format_id": "137+251",
  "audio_only": false,
  "convert_mp3": false
}
```

## Configuration

All settings are configurable via environment variables (see `.env.example`):

| Variable                   | Default | Description                      |
|----------------------------|---------|----------------------------------|
| `REDIS_URL`                | `redis://localhost:6379/0` | Redis connection URL |
| `MAX_CONCURRENT_DOWNLOADS` | `3`     | Worker concurrency limit         |
| `FILE_TTL_SECONDS`         | `3600`  | Downloaded file retention time   |
| `DOWNLOAD_TIMEOUT_SECONDS` | `600`   | Per-task download timeout        |
| `WORKER_MAX_RETRIES`       | `3`     | Retry count on failure           |
| `AUTH_MODE`                | `cookies`| Auth method: cookies / browser   |
| `COOKIES_FILE`             | (empty) | Path to cookies.txt              |
| `COOKIES_FROM_BROWSER`     | (empty) | Browser name (browser mode only) |

## License

Private use only. Respect YouTube's Terms of Service and applicable copyright laws.
