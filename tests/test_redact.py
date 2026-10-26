"""Redaktion von URLs und Kommandozeilen (``sortiton/redact.py``).

Zugangsdaten, Pfadsegmente, Query-Werte und Tokens dürfen nicht im Log oder in
einer Fehlermeldung landen - auch nicht in einer URL ohne Schema oder hinter
einem ``--source-url=…``.
"""

from __future__ import annotations

from _support import check


def test_urls_and_arguments_are_redacted() -> None:
    """Nur Schema und Host bleiben lesbar, alles andere wird ersetzt."""
    from sortiton import redact

    # Redaction test fixture; not a real credential.
    auth = "user:pass"  # pragma: allowlist secret
    secret = f"https://{auth}@example.org/watch/session-token?token=abc#frag"
    hidden = redact.url(secret)
    check("the host stays readable", hidden.startswith("https://example.org/"), hidden)
    check("the path is gone", "session-token" not in hidden, hidden)
    check("the query is gone", "token" not in hidden, hidden)
    check("the password is gone", "pass" not in hidden, hidden)
    check("inline URLs in an error are redacted",
          "abc" not in redact.text(f"failed for {secret}"), redact.text(secret))
    check("a plain path is unchanged", redact.url("/music/track.mp3") == "/music/track.mp3")

    for argument in ("--source-url=https://example.org/watch?v=secret",
                     "--source-url=youtu.be/watch?v=secret"):
        rendered = redact.command([argument])[0]
        check("the token is redacted", "secret" not in rendered, rendered)
        check("the option is still visible", rendered.startswith("--source-url="),
              rendered)

    bare = redact.url("youtu.be/watch?v=secret")
    check("a scheme-less query is redacted", "secret" not in bare, bare)
