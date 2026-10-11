"""Cooperative cancellation for long-running commands.

A command receives a :class:`CancelToken` through its optional ``args.cancel``
field and calls :meth:`CancelToken.check` at every safe point. The GUI creates
one token per run and sets it from the "Cancel" button; the CLI is stopped by
``KeyboardInterrupt`` (handled in :mod:`sortiton.cli`). A command that is never
cancelled uses the shared :data:`NO_CANCEL` token.
"""

from __future__ import annotations

import threading


class Cancelled(Exception):
    """Raised by :meth:`CancelToken.check` once the token has been cancelled."""


class CancelToken:
    """A thread-safe "stop" flag wrapped around :class:`threading.Event`.

    ``check()`` turns the flag into an exception, so a command stops at its next
    check point instead of polling a boolean everywhere. The token is safe to
    share between the worker threads of a command and the GUI thread that
    cancels it.
    """

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


#: The default token for commands started without one; it is never cancelled.
NO_CANCEL = CancelToken()
