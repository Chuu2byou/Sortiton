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


def url(value: str) -> str:
    """``https://host/…`` for an HTTP(S) URL, unchanged for anything else."""
    text = str(value)
    try:
        parts = urlsplit(text)
    except ValueError:
        return text
    if parts.scheme.lower() not in {"http", "https"} or not parts.netloc:
        return text
    # netloc may still contain "user:password@" - keep only the host part.
    netloc = parts.netloc.rsplit("@", 1)[-1]
    return f"{parts.scheme}://{netloc}/…"


def text(value: str) -> str:
    """Redact every HTTP(S) URL inside a longer message."""
    return _URL_RE.sub(lambda match: url(match.group(0)), str(value))


def command(argv) -> list[str]:
    """Redact the URL-shaped arguments of a command line."""
    return [url(str(argument)) for argument in argv]
