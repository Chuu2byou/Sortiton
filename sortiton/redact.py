"""Keep secrets out of logs and journals.

A fetch URL often carries a session token in its path or query string. The log
file and the journal are plain text and may be shared when reporting a problem,
so only the scheme and host of an HTTP(S) URL are kept. Everything else is
replaced by an ellipsis.
"""

from __future__ import annotations

import re
from urllib.parse import urlsplit

_URL_RE = re.compile(r"https?://\S+")
#: A scheme-less URL as yt-dlp accepts it: host.tld/... (optionally after "--x=").
_HOST_RE = re.compile(r"^[A-Za-z0-9.-]+\.[A-Za-z]{2,}(?::\d+)?(?:/.*)?$")


def url(value: str) -> str:
    """``https://host/…`` for a URL; unchanged for anything else."""
    text = str(value)
    try:
        parts = urlsplit(text)
    except ValueError:
        return text
    if parts.scheme.lower() in {"http", "https"} and parts.netloc:
        # netloc may still contain "user:password@" - keep only the host part.
        netloc = parts.netloc.rsplit("@", 1)[-1]
        return f"{parts.scheme}://{netloc}/…"
    # yt-dlp also accepts "youtu.be/watch?v=…" without a scheme. Keep the host
    # and path but drop the query, which is where session tokens usually live.
    if "?" in text and "://" not in text:
        head = text.partition("?")[0]
        candidate = head.rsplit("=", 1)[-1]
        if _HOST_RE.match(candidate):
            return head + "?…"
    return text


def text(value: str) -> str:
    """Redact every HTTP(S) URL inside a longer message."""
    return _URL_RE.sub(lambda match: url(match.group(0)), str(value))


def command(argv) -> list[str]:
    """Redact URL-shaped arguments, including ``--option=URL`` forms."""
    return [url(text(str(argument))) for argument in argv]
