"""External helpers: programs on the PATH and optional Python modules."""

from __future__ import annotations

import importlib.util
import re
import shutil
import subprocess
from dataclasses import dataclass

from . import config, i18n


@dataclass(frozen=True)
class Tool:
    """A helper the program can use: a program on PATH or a Python module."""

    key: str
    binary: str = ""
    module: str = ""
    hint_key: str = ""


@dataclass(frozen=True)
class Requirement:
    """At least one of ``any_of`` must be available."""

    any_of: tuple[Tool, ...]
    when: str | None = None


FFPROBE = Tool("ffprobe", "ffprobe", hint_key="external.hint.ffprobe")
FFMPEG = Tool("ffmpeg", "ffmpeg", hint_key="external.hint.ffmpeg")
FPCALC = Tool("fpcalc", "fpcalc", hint_key="external.hint.fpcalc")
MUTAGEN = Tool("mutagen", "", module="mutagen", hint_key="external.hint.mutagen")
YT_DLP = Tool("yt-dlp", "yt-dlp", hint_key="external.hint.ytdlp")

TOOLS: tuple[Tool, ...] = (FFPROBE, FFMPEG, FPCALC, MUTAGEN, YT_DLP)

VERSION_FLAGS: tuple[str, ...] = ("--version", "-version")
VERSION_TIMEOUT = 3.0

_VERSION_RE = re.compile(r"\d+(?:\.\d+)+")


def available(tool: Tool) -> bool:
    """True when ``tool`` can be used right now."""
    if tool is MUTAGEN:
        return config.MUTAGEN_AVAILABLE
    if tool.module:
        return importlib.util.find_spec(tool.module) is not None
    return shutil.which(tool.binary) is not None


def version(tool: Tool) -> str:
    """Short version of ``tool``, or ``""`` when it cannot be told."""
    if tool.module:
        return _module_version(tool)
    if not tool.binary or shutil.which(tool.binary) is None:
        return ""
    for flag in VERSION_FLAGS:
        try:
            result = subprocess.run([tool.binary, flag], capture_output=True,
                                    text=True, timeout=VERSION_TIMEOUT, check=False)
        except (OSError, subprocess.SubprocessError):
            continue
        if result.returncode == 0:
            line = _first_line(result.stdout)
            if line:
                return _version_token(line)
    return ""


def _module_version(tool: Tool) -> str:
    """Version attribute of a Python module tool, ``""`` when it is missing."""
    if not tool.module or not available(tool):
        return ""
    try:
        module = importlib.import_module(tool.module)
    except Exception:
        return ""
    raw = getattr(module, "version_string", "") or getattr(module, "__version__", "")
    return _version_token(str(raw).strip()) if raw else ""


def _first_line(text: str) -> str:
    """First non-empty line of ``text``, stripped."""
    for line in (text or "").splitlines():
        if line.strip():
            return line.strip()
    return ""


def _version_token(line: str) -> str:
    """Version-looking part of ``line`` (the whole line when there is none)."""
    match = _VERSION_RE.search(line)
    return match.group(0) if match else line


def missing(feature, args) -> list[Requirement]:
    """Requirements of ``feature`` that are not satisfied right now."""
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
