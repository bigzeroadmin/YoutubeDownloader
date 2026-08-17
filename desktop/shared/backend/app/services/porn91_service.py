"""91porn.com extraction.

yt-dlp upstream refuses this site ([Piracy] block), so we resolve it
ourselves. Two page families are supported:

- ``view_video.php?viewkey=...`` (91porn.com): decode the URL-encoded
  ``strencode2(...)`` player block and pull the direct mp4 URL out of it.
- ``ev.php?VID=...`` (9p9.xyz embeds): the player block uses the
  3-argument ``strencode(...)`` variant defined in the site's obfuscated
  ``js/m.js``; we evaluate that JS with the bundled node runtime to decode
  it. This yields a URL on the official rsc.cdn77.org CDN.

Notes learned from probing the site:
- Each view_video page load hands out a random mirror URL; some mirrors
  are the real video (tens of MB) and some are tiny dummy clips (~1-3 MB
  vertical ads). We therefore sample several page loads and keep the
  largest candidate.
- The CDN serves the real file to plain browser-like requests; sending the
  page's cookies to the CDN can trigger a dummy response, so the download
  request must NOT carry a Cookie header (a real browser never sends
  91porn cookies to the cross-site CDN).
- The signed mp4 URL is short-lived, so it must be re-extracted at
  download time rather than cached.
"""
from __future__ import annotations

import html as html_mod
import logging
import re
import urllib.parse
import urllib.request
from pathlib import Path
from urllib.error import URLError

logger = logging.getLogger(__name__)

_USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0 Safari/537.36"
)

_PAGE_RE = re.compile(r"view_video\.php\?.*viewkey=")
_EV_PAGE_RE = re.compile(r"/ev\.php\?.*\bVID=")
_STRENCODE_RE = re.compile(r"strencode2?\(\"([^\"]+)\"\)")
_STRENCODE3_RE = re.compile(r"strencode\(\"([^\"]+)\",\"([^\"]+)\",\"([^\"]+)\"\)")
_SOURCE_RE = re.compile(r"src=['\"]([^'\"]+\.mp4[^'\"]*)['\"]")
_TITLE_RE = re.compile(r"<title>(.*?)</title>", re.S)
_THUMB_RE = re.compile(
    r"https?://[^\"'<> ]*/thumb/[^\"'<> ]+\.(?:jpg|jpeg|png)", re.IGNORECASE
)
_DURATION_RE = re.compile(r"Runtime:\s*<span[^>]*>(\d{1,2}:\d{2}(?::\d{2})?)</span>")

# Candidate sampling: stop early once a mirror this large is found.
_MAX_ATTEMPTS = 5
_GOOD_ENOUGH_BYTES = 20 * 1024 * 1024

# Node-side helper: evaluates the site's obfuscated js/m.js (which defines
# strencode) with minimal browser stubs and decodes the ev.php player block.
_DECODE_JS = r"""
const fs = require('fs');
global.window = global;
global.document = {
  write: () => {},
  createElement: () => ({ style: {}, setAttribute: () => {}, getElementsByTagName: () => [] }),
  getElementsByTagName: () => [{ appendChild: () => {} }],
  documentElement: { style: {} },
  cookie: '',
};
global.navigator = { userAgent: 'node' };
global.location = { href: 'https://91porn.com/' };
const [mjsPath, argsJson] = process.argv.slice(2);
eval(fs.readFileSync(mjsPath, 'utf8'));
const args = JSON.parse(argsJson);
process.stdout.write(String(strencode(args[0], args[1], args[2])));
"""


def is_porn91_url(url: str) -> bool:
    """True for 91porn view_video pages and 9p9.xyz ev.php embed pages."""
    host = urllib.parse.urlparse(url).hostname or ""
    return (
        host == "91porn.com"
        or host.endswith(".91porn.com")
        or host == "9p9.xyz"
        or host.endswith(".9p9.xyz")
    )


def _find_node() -> str:
    import shutil
    from app.config import ELECTRON_RESOURCES_PATH

    node = shutil.which("node")
    if node:
        return node
    if ELECTRON_RESOURCES_PATH:
        candidate = Path(ELECTRON_RESOURCES_PATH) / "node" / "node"
        if candidate.is_file():
            return str(candidate)
    raise RuntimeError("node runtime not found (needed to decode 91porn ev.php links)")


def _decode_strencode3(args: list[str], page_url: str, timeout: int) -> str:
    """Decode the 3-argument strencode() block via the site's own m.js + node."""
    import json
    import subprocess
    import tempfile

    from app.config import YTDLP_CACHE_DIR

    mjs_url = urllib.parse.urljoin(page_url, "js/m.js")
    mjs = _fetch_page(mjs_url, timeout)

    script = Path(YTDLP_CACHE_DIR) / "p91_ev_decode.js"
    if not script.is_file() or script.read_text() != _DECODE_JS:
        script.write_text(_DECODE_JS)

    with tempfile.NamedTemporaryFile("w", suffix=".js", delete=False) as fh:
        fh.write(mjs)
        mjs_path = fh.name
    try:
        result = subprocess.run(
            [_find_node(), str(script), mjs_path, json.dumps(args)],
            capture_output=True, text=True, timeout=timeout,
        )
    finally:
        Path(mjs_path).unlink(missing_ok=True)
    if result.returncode != 0:
        raise RuntimeError(f"node strencode decode failed: {result.stderr.strip()[:200]}")
    return result.stdout


def _fetch_page(url: str, timeout: int) -> str:
    req = urllib.request.Request(url, headers={"User-Agent": _USER_AGENT})
    last_exc: Exception | None = None
    # The mirror hosts sit behind flaky/poisoned DNS — intermittent TLS
    # errors are common, so retry a few times before giving up.
    for attempt in range(4):
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                return resp.read().decode("utf-8", "replace")
        except URLError as exc:
            last_exc = exc
            logger.debug("91porn fetch attempt %d failed: %s", attempt + 1, exc)
    raise RuntimeError(f"Failed to fetch 91porn page: {last_exc}")


def _extract_video_url(html: str) -> str:
    m = _STRENCODE_RE.search(html)
    if m:
        decoded = urllib.parse.unquote(m.group(1))
        srcs = _SOURCE_RE.findall(decoded)
        if srcs:
            return srcs[0]
    raise RuntimeError("Could not find video URL on 91porn page")


def _parse_duration(text: str) -> int | None:
    seconds = 0
    for p in text.split(":"):
        seconds = seconds * 60 + int(p)
    return seconds or None


def _head_size(video_url: str, page_url: str, timeout: int) -> int | None:
    headers = {
        "User-Agent": _USER_AGENT,
        "Referer": page_url,
        "Accept": "*/*",
        "Accept-Encoding": "identity;q=1, *;q=0",
    }
    try:
        req = urllib.request.Request(video_url, method="HEAD", headers=headers)
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            length = resp.headers.get("Content-Length")
            if length and length.isdigit():
                return int(length)
    except Exception as exc:  # noqa: BLE001 — size probing is best-effort
        logger.debug("91porn HEAD failed for %s: %s", video_url[:60], exc)
    return None


def _extract_ev(url: str, timeout: int) -> dict:
    """Resolve a 9p9.xyz ev.php embed page.

    Unlike view_video pages, the ev player decodes (via node + the site's
    own m.js) to a URL on the official rsc.cdn77.org CDN — deterministic,
    no mirror sampling needed.
    """
    html = _fetch_page(url, timeout)
    m = _STRENCODE3_RE.search(html)
    if not m:
        raise RuntimeError("Could not find strencode block on ev.php page")

    decoded = _decode_strencode3([m.group(1), m.group(2), m.group(3)], url, timeout)
    srcs = _SOURCE_RE.findall(decoded)
    if not srcs:
        raise RuntimeError("Could not find video URL in decoded ev.php block")
    video_url = srcs[0]

    thumbnail = None
    tm = _THUMB_RE.search(html)
    if tm:
        thumbnail = tm.group(0)
    vid = None
    vm = re.search(r"/(\d+)\.mp4", video_url)
    if vm:
        vid = vm.group(1)

    size = _head_size(video_url, url, timeout)

    return {
        "title": f"91porn video {vid}" if vid else "91porn video",
        "thumbnail": thumbnail,
        "duration": None,
        "video_url": video_url,
        "filesize": size,
        "headers": {
            "User-Agent": _USER_AGENT,
            "Referer": url,
            "Accept": "*/*",
            "Accept-Encoding": "identity;q=1, *;q=0",
        },
    }


def extract_video(url: str, timeout: int = 30) -> dict:
    """Resolve a 91porn view page to a direct mp4 URL plus metadata.

    Samples several page loads and returns the largest mirror found,
    because the site randomly hands out tiny dummy clips on some loads.
    """
    if _EV_PAGE_RE.search(url):
        return _extract_ev(url, timeout)
    if not _PAGE_RE.search(url):
        raise ValueError("Not a 91porn video page URL")

    best: dict | None = None
    meta: dict = {}
    for attempt in range(1, _MAX_ATTEMPTS + 1):
        html = _fetch_page(url, timeout)
        video_url = _extract_video_url(html)
        size = _head_size(video_url, url, timeout)

        if not meta:
            title = None
            m = _TITLE_RE.search(html)
            if m:
                title = html_mod.unescape(
                    re.sub(r"\s*-\s*91porn\s*$", "", m.group(1)).strip()
                ) or None
            thumbnail = None
            m = _THUMB_RE.search(html)
            if m:
                thumbnail = m.group(0)
            duration = None
            m = _DURATION_RE.search(html)
            if m:
                duration = _parse_duration(m.group(1))
            meta = {"title": title or "91porn video", "thumbnail": thumbnail, "duration": duration}

        logger.info(
            "91porn candidate %d/%d: %s (%s bytes)",
            attempt, _MAX_ATTEMPTS, video_url[:70], size,
        )
        if size is not None and (best is None or size > (best["filesize"] or 0)):
            best = {"video_url": video_url, "filesize": size}
            if size >= _GOOD_ENOUGH_BYTES:
                break

    if best is None:
        raise RuntimeError("Could not determine 91porn video size after sampling")

    return {
        **meta,
        "video_url": best["video_url"],
        "filesize": best["filesize"],
        # Headers for the download request — deliberately NO Cookie header.
        "headers": {
            "User-Agent": _USER_AGENT,
            "Referer": "https://www.91porn.com/",
            "Accept": "*/*",
            "Accept-Encoding": "identity;q=1, *;q=0",
        },
    }
