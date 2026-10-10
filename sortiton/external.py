"""External helpers: programs on the PATH and optional Python modules.

A feature declares what it needs (see :class:`Requirement`); this module answers
whether it is there. The check is never cached, because tests patch
``shutil.which`` and ``config.MUTAGEN_AVAILABLE`` and the answer has to follow.

``Requirement`` lives here and not in ``features/base.py`` so that this module
stays self-contained: ``features/base.py`` imports ``Tool`` and ``Requirement``
from here, never the other way round - that keeps the import graph free of
cycles.
"""

from __future__ import annotations

import importlib.util
import shutil
from dataclasses import dataclass

from . import config, i18n


@dataclass(frozen=True)
class Tool:
    """A helper the program can use: a program on PATH or a Python module."""

    key: str            # short name, e.g. "ffprobe"
    binary: str = ""    # program looked for on PATH; "" for a Python module
    module: str = ""    # Python module name, e.g. "mutagen"
    hint_key: str = ""  # i18n key with install hints


@dataclass(frozen=True)
class Requirement:
    """At least one of ``any_of`` must be available.

    ``when`` names an option (``Option.name``); the requirement only applies
    when that option is truthy in the parsed arguments.
    """

    any_of: tuple[Tool, ...]
    when: str | None = None


FFPROBE = Tool("ffprobe", "ffprobe", hint_key="external.hint.ffprobe")
FPCALC = Tool("fpcalc", "fpcalc", hint_key="external.hint.fpcalc")
MUTAGEN = Tool("mutagen", "", module="mutagen", hint_key="external.hint.mutagen")


def available(tool: Tool) -> bool:
    """True when ``tool`` can be used right now.

    Deliberately not cached: tests patch ``shutil.which`` and
    ``config.MUTAGEN_AVAILABLE``, and the answer has to follow.
    """
    if tool is MUTAGEN:
        # mutagen is optional; config.MUTAGEN_AVAILABLE is the project's flag.
        return config.MUTAGEN_AVAILABLE
    if tool.module:
        return importlib.util.find_spec(tool.module) is not None
    return shutil.which(tool.binary) is not None


def missing(feature, args) -> list[Requirement]:
    """Requirements of ``feature`` that are not satisfied right now.

    ``feature`` is a :class:`sortiton.features.base.Feature`; ``args`` is the
    parsed arguments (a CLI ``Namespace`` or a GUI ``SimpleNamespace``).
    """
    lacking: list[Requirement] = []
    for requirement in getattr(feature, "requires", ()):
        if requirement.when and not getattr(args, requirement.when, False):
            continue
        if not any(available(tool) for tool in requirement.any_of):
            lacking.append(requirement)
    return lacking


def format_missing(requirements: list[Requirement]) -> str:
    """Human-readable text for :func:`missing`, including install hints."""
    tools: list[Tool] = []
    for requirement in requirements:
        for tool in requirement.any_of:
            if tool not in tools:
                tools.append(tool)
    names = ", ".join(tool.key for tool in tools)
    lines = [i18n.t("external.error.missing", tools=names)]
    for tool in tools:
        if tool.hint_key:
            lines.append(i18n.t(tool.hint_key))
    return "\n".join(lines)
