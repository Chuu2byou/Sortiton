"""Gemeinsame Beschreibungen der vier Kernaufträge für CLI und GUI."""

from __future__ import annotations

from dataclasses import dataclass

from . import settings
from .features.base import Option, OptionKind

PATTERN_DEFAULT = "%artist% - %title%"


@dataclass(frozen=True)
class CoreFeature:
    """Argumente und sichtbare Seitenbesonderheiten eines Kernauftrags."""

    key: str
    options: tuple[Option, ...]
    source_var: str
    target_var: str
    mode_var: str
    run_method: str
    execute_key: str
    pattern_var: str = ""
    show_rules: bool = False
    show_pattern_hint: bool = False


def _folder(page: str, name: str, optional: bool = False) -> Option:
    return Option(name, "folder", help_key=f"cli.{page}.{name}",
                  positional=True, optional_positional=optional)


def _flag(page: str, name: str, kind: OptionKind = "bool", default=None,
          choices: tuple[str, ...] = ()) -> Option:
    return Option(name, kind, default=default, help_key=f"cli.{page}.{name}",
                  flags=("--" + name.replace("_", "-"),), choices=choices)


def _advanced(page: str) -> tuple[Option, ...]:
    return (_flag(page, "backup"),
            _flag(page, "track_format", "choice", choices=tuple(settings.TRACK_FORMATS)),
            _flag(page, "diff"), _flag(page, "diff_csv", "text"))


def _options(page: str, source: str, optional_target: bool,
             pattern: bool, advanced: bool) -> tuple[Option, ...]:
    options = [_folder(page, source), _folder(page, "target", optional_target)]
    if pattern:
        options.append(_flag(page, "pattern", "text", PATTERN_DEFAULT))
    options.extend((_flag(page, "move"), _flag(page, "apply")))
    if advanced:
        options.extend(_advanced(page))
    return tuple(options)


CORE_FEATURES = (
    CoreFeature("tags", _options("tags", "folder", True, False, True),
                "var_tags_folder", "var_tags_target", "var_tags_mode",
                "_run_tags", "gui.button.write_tags", show_rules=True),
    CoreFeature("rename", _options("rename", "folder", True, True, False),
                "var_ren_folder", "var_ren_target", "var_ren_mode",
                "_run_rename", "gui.button.rename", pattern_var="var_ren_pattern",
                show_pattern_hint=True),
    CoreFeature("sort", _options("sort", "source", False, True, False),
                "var_source", "var_target", "var_sort_mode",
                "_run_sort", "gui.button.sort", pattern_var="var_sort_pattern"),
    CoreFeature("all", _options("all", "source", False, True, True),
                "var_all_source", "var_all_target", "var_all_mode",
                "_run_all", "gui.button.run_all", pattern_var="var_all_pattern"),
)


def core_feature(key: str) -> CoreFeature:
    """Beschreibung eines Kernauftrags anhand seines Schlüssels finden."""
    return next(feature for feature in CORE_FEATURES if feature.key == key)
