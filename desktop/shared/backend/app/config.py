import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent

# --- Desktop Mode ---
DESKTOP_MODE = os.getenv("DESKTOP_MODE", "") == "1"
ELECTRON_RESOURCES_PATH = os.getenv("ELECTRON_RESOURCES_PATH", "")

# When running inside an Electron bundle, add bundled binaries to PATH
if DESKTOP_MODE and ELECTRON_RESOURCES_PATH:
    _res = Path(ELECTRON_RESOURCES_PATH)
    _extra_paths = [str(_res / "ffmpeg"), str(_res / "node")]
    _extra = os.pathsep.join(p for p in _extra_paths if Path(p).exists())
    if _extra:
        os.environ["PATH"] = _extra + os.pathsep + os.environ.get("PATH", "")

# --- NFR: Non-Functional Requirements ---
MAX_CONCURRENT_DOWNLOADS = int(os.getenv("MAX_CONCURRENT_DOWNLOADS", "2" if DESKTOP_MODE else "3"))
RESOLVE_TIMEOUT_SECONDS = int(os.getenv("RESOLVE_TIMEOUT_SECONDS", "30"))
DOWNLOAD_TIMEOUT_SECONDS = int(os.getenv("DOWNLOAD_TIMEOUT_SECONDS", "600"))
FILE_TTL_SECONDS = int(os.getenv("FILE_TTL_SECONDS", "86400" if DESKTOP_MODE else "3600"))
CLEANUP_INTERVAL_SECONDS = int(os.getenv("CLEANUP_INTERVAL_SECONDS", "300"))  # 5 min
MAX_FILE_SIZE_MB = int(os.getenv("MAX_FILE_SIZE_MB", "2048"))

# --- Large file / Cookie refresh ---
LARGE_FILE_TIMEOUT_SECONDS = int(os.getenv("LARGE_FILE_TIMEOUT_SECONDS", "7200"))  # 2 hours
LARGE_FILE_THRESHOLD_BYTES = int(os.getenv("LARGE_FILE_THRESHOLD_BYTES", str(2 * 1024**3)))  # 2 GB
COOKIE_MAX_AGE_SECONDS = int(os.getenv("COOKIE_MAX_AGE_SECONDS", "3600"))  # 1 hour
COOKIE_REFRESH_WAIT_SECONDS = int(os.getenv("COOKIE_REFRESH_WAIT_SECONDS", "120"))
COOKIE_RETRY_MAX = int(os.getenv("COOKIE_RETRY_MAX", "2"))

# --- Storage ---
_default_download_dir = (
    str(Path.home() / "Downloads" / "YouTubeDownload")
    if DESKTOP_MODE
    else str(BASE_DIR / "downloads")
)
DOWNLOAD_DIR = Path(os.getenv("DOWNLOAD_DIR", _default_download_dir))
DOWNLOAD_DIR.mkdir(parents=True, exist_ok=True)

# --- Redis ---
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")

# --- Rate Limiting ---
RATE_LIMIT_RESOLVE = os.getenv("RATE_LIMIT_RESOLVE", "10/minute")
RATE_LIMIT_DOWNLOAD = os.getenv("RATE_LIMIT_DOWNLOAD", "5/minute")

# --- Security: supported video platform hostnames ---
ALLOWED_HOSTS = [
    "youtube.com",
    "youtu.be",
    "tiktok.com",
    "douyin.com",
    "91porn.com",
    "9p9.xyz",
]

# --- Authentication ---
# AUTH_MODE: "cookies" (default, file-based) | "browser" (local dev only)
AUTH_MODE = os.getenv("AUTH_MODE", "cookies")
COOKIES_FILE = os.getenv("COOKIES_FILE", "")
COOKIES_FROM_BROWSER = os.getenv("COOKIES_FROM_BROWSER", "")

# Desktop mode: use cookies file + auto-detect browser for refresh
if DESKTOP_MODE:
    # Auto-detect available browser for cookie extraction
    if not COOKIES_FROM_BROWSER:
        _BROWSER_DETECT_ORDER = [
            ("edge", "/Applications/Microsoft Edge.app"),
            ("chrome", "/Applications/Google Chrome.app"),
            ("firefox", "/Applications/Firefox.app"),
            ("brave", "/Applications/Brave Browser.app"),
            ("safari", "/Applications/Safari.app"),
        ]
        for _bname, _bpath in _BROWSER_DETECT_ORDER:
            if Path(_bpath).exists():
                COOKIES_FROM_BROWSER = _bname
                break

    # Desktop uses cookies file mode with auto-refresh
    AUTH_MODE = "cookies"
    _desktop_data_dir = Path.home() / "Library" / "Application Support" / "YouTubeDownload"
    _desktop_data_dir.mkdir(parents=True, exist_ok=True)
    if not COOKIES_FILE:
        COOKIES_FILE = str(_desktop_data_dir / "cookies.txt")
_default_cache_dir = (
    str(Path.home() / "Library" / "Caches" / "YouTubeDownload" / "ytdlp")
    if DESKTOP_MODE
    else str(BASE_DIR / ".ytdlp_cache")
)
YTDLP_CACHE_DIR = os.getenv("YTDLP_CACHE_DIR", _default_cache_dir)
Path(YTDLP_CACHE_DIR).mkdir(parents=True, exist_ok=True)

# --- Worker ---
WORKER_MAX_RETRIES = int(os.getenv("WORKER_MAX_RETRIES", "3"))
WORKER_RETRY_DELAY_SECONDS = int(os.getenv("WORKER_RETRY_DELAY_SECONDS", "5"))
