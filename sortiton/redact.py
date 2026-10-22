"""Keep secrets out of logs and journals."""

from __future__ import annotations

import re
from urllib.parse import urlsplit

_URL_RE = re.compile(r"https?://\S+")
_HOST_RE = re.compile(r"^[A-Za-z0-9.-]+\.[A-Za-z]{2,}(?::\d+)?(?:/.*)?$")


def url(value: str) -> str:
    """``https://host/…`` for a URL; unchanged for anything else."""
    text = str(value)
    try:
        parts = urlsplit(text)
    except ValueError:
        return text
    if parts.scheme.lower() in {"http", "https"} and parts.netloc:
        netloc = parts.netloc.rsplit("@", 1)[-1]
        return f"{parts.scheme}://{netloc}/…"
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
