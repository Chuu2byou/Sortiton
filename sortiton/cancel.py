"""Cooperative cancellation for long-running commands."""

from __future__ import annotations

import threading


class Cancelled(Exception):
    """Raised by :meth:`CancelToken.check` once the token has been cancelled."""


class CancelToken:
    """A thread-safe "stop" flag wrapped around :class:`threading.Event`."""

    def __init__(self) -> None:
        self._event = threading.Event()

    def cancel(self) -> None:
        """Ask the running command to stop at its next check point."""
        self._event.set()

    def is_set(self) -> bool:
        """True once :meth:`cancel` was called (a plain boolean check)."""
        return self._event.is_set()

    def check(self) -> None:
        """Raise :class:`Cancelled` when the token was cancelled."""
        if self._event.is_set():
            raise Cancelled


NO_CANCEL = CancelToken()
