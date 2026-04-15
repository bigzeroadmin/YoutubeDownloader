import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent

# --- NFR: Non-Functional Requirements ---
MAX_CONCURRENT_DOWNLOADS = int(os.getenv("MAX_CONCURRENT_DOWNLOADS", "3"))
RESOLVE_TIMEOUT_SECONDS = int(os.getenv("RESOLVE_TIMEOUT_SECONDS", "30"))
DOWNLOAD_TIMEOUT_SECONDS = int(os.getenv("DOWNLOAD_TIMEOUT_SECONDS", "600"))
FILE_TTL_SECONDS = int(os.getenv("FILE_TTL_SECONDS", "3600"))  # 1 hour
CLEANUP_INTERVAL_SECONDS = int(os.getenv("CLEANUP_INTERVAL_SECONDS", "300"))  # 5 min
MAX_FILE_SIZE_MB = int(os.getenv("MAX_FILE_SIZE_MB", "2048"))

# --- Storage ---
DOWNLOAD_DIR = Path(os.getenv("DOWNLOAD_DIR", str(BASE_DIR / "downloads")))
DOWNLOAD_DIR.mkdir(parents=True, exist_ok=True)

# --- Redis ---
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")

# --- Rate Limiting ---
RATE_LIMIT_RESOLVE = os.getenv("RATE_LIMIT_RESOLVE", "10/minute")
RATE_LIMIT_DOWNLOAD = os.getenv("RATE_LIMIT_DOWNLOAD", "5/minute")

# --- Security: allowed URL hostname patterns ---
ALLOWED_HOSTS = [
    "youtube.com",
    "www.youtube.com",
    "m.youtube.com",
    "youtu.be",
    "music.youtube.com",
]

# --- Authentication ---
# AUTH_MODE: "cookies" (default, file-based) | "browser" (local dev only)
AUTH_MODE = os.getenv("AUTH_MODE", "cookies")
COOKIES_FILE = os.getenv("COOKIES_FILE", "")
COOKIES_FROM_BROWSER = os.getenv("COOKIES_FROM_BROWSER", "")
YTDLP_CACHE_DIR = os.getenv("YTDLP_CACHE_DIR", str(BASE_DIR / ".ytdlp_cache"))
Path(YTDLP_CACHE_DIR).mkdir(parents=True, exist_ok=True)

# --- Worker ---
WORKER_MAX_RETRIES = int(os.getenv("WORKER_MAX_RETRIES", "3"))
WORKER_RETRY_DELAY_SECONDS = int(os.getenv("WORKER_RETRY_DELAY_SECONDS", "5"))
