"""Feature description: the one interface between a feature, the CLI and the GUI.

A feature does not build its own parser: it declares its :class:`Option` list
once, and the CLI (and later the GUI) reads that list. Keeping the description
in data - not in code that fills an ``argparse`` parser - is what lets both
front ends share it.

``Requirement`` and ``Tool`` live in :mod:`sortiton.external`; they are imported
here and never the other way round, so this module stays free of import cycles.
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from types import SimpleNamespace
from typing import Callable, Literal

from .. import i18n
from ..external import Requirement, Tool

# CLI: argparse.Namespace, GUI: SimpleNamespace. tasks.py re-exports this name.
CmdArgs = argparse.Namespace | SimpleNamespace

OptionKind = Literal["folder", "text", "bool", "int", "float", "choice"]


@dataclass(frozen=True)
class Option:
    """One command line option, described as data (CLI and GUI share it)."""

    name: str                          # argparse dest and GUI variable name, e.g. "fp_threshold"
    kind: OptionKind
    default: object = None
    help_key: str = ""                 # i18n key; "%" in help texts must be written "%%"
    flags: tuple[str, ...] = ()        # ("--fp-threshold", "--fp-schwelle"); empty if positional
    positional: bool = False
    choices: tuple[str, ...] = ()      # kind == "choice"
    minimum: float | None = None       # int/float, validated in run(), not in argparse
    maximum: float | None = None


@dataclass(frozen=True)
class Feature:
    """A feature the CLI and the GUI can start from the very same description."""

    key: str                           # "export" -- also the CLI sub-command
    title_key: str                     # i18n key, GUI tab entry and banner
    help_key: str                      # i18n key, CLI --help line
    run: Callable[[CmdArgs], int]
    options: tuple[Option, ...]
    requires: tuple[Requirement, ...] = ()
    writes: bool = False               # True: needs --apply, journal, backup
    uses_rules: bool = False           # True: cli.main prints the my_rules.ini summary


def _add_option(parser: argparse.ArgumentParser, option: Option) -> None:
    """Add one :class:`Option` to ``parser``.

    Flagged options get ``dest=option.name`` explicitly, so the destination is
    stable even when the first flag is a short one. A positional name already
    is its own destination.
    """
    help_text = i18n.t(option.help_key) if option.help_key else None

    if option.positional:
        # argparse derives dest from the name; passing it again is an error
        # ("dest supplied twice for positional argument") on Python 3.14.
        parser.add_argument(option.name, help=help_text)
        return

    if not option.flags:
        raise ValueError(f"option {option.name!r} is neither positional nor flagged")

    if option.kind == "bool":
        if option.default:
            # A flag that defaults to True would need --no-<name>; not needed yet.
            raise NotImplementedError(
                f"bool option {option.name!r} with default True is not supported")
        parser.add_argument(*option.flags, dest=option.name, action="store_true",
                            default=False, help=help_text)
        return

    kwargs: dict[str, object] = {"dest": option.name, "default": option.default,
                                 "help": help_text}
    if option.kind in ("folder", "text", "choice"):
        kwargs["type"] = str
    elif option.kind == "int":
        kwargs["type"] = int
    elif option.kind == "float":
        kwargs["type"] = float
    else:
        raise ValueError(f"unknown option kind: {option.kind!r}")
    if option.kind == "choice":
        kwargs["choices"] = option.choices
    parser.add_argument(*option.flags, **kwargs)


def add_feature_parser(subparsers, feature: Feature,
                       common_parent: argparse.ArgumentParser | None = None
                       ) -> argparse.ArgumentParser:
    """Register ``feature`` as a sub-command built from its :class:`Option` list.

    ``common_parent`` is an optional ``argparse`` parser whose arguments (e.g.
    ``-q/--quiet``) every sub-command inherits via ``parents=[...]``. Call this
    only after ``settings.apply_language()``, so the help texts are translated.
    """
    parents = [common_parent] if common_parent is not None else []
    parser = subparsers.add_parser(feature.key, parents=parents,
                                   help=i18n.t(feature.help_key))
    for option in feature.options:
        _add_option(parser, option)
    parser.set_defaults(func=feature.run, feature=feature)
    return parser


def resolve_args(feature: Feature, args: CmdArgs) -> SimpleNamespace:
    """Fill every option the caller left out with its default.

    The GUI builds a ``SimpleNamespace`` with only the fields it knows; the CLI
    passes the ``argparse`` result. Either way the result carries every option
    name. Range checks (``minimum``/``maximum``) happen in the feature's
    ``run``, not here, so the GUI gets the same validation.
    """
    values = dict(vars(args))
    for option in feature.options:
        if option.name not in values:
            values[option.name] = option.default
    return SimpleNamespace(**values)
