"""Feature description: the one interface between a feature, the CLI and the GUI."""

from __future__ import annotations

import argparse
from collections.abc import Mapping
from dataclasses import dataclass
from types import SimpleNamespace
from typing import Callable, Literal

from .. import i18n
from ..external import Requirement

CmdArgs = argparse.Namespace | SimpleNamespace

OptionKind = Literal["folder", "text", "bool", "int", "float", "choice"]


@dataclass(frozen=True)
class Option:
    """One command line option, described as data (CLI and GUI share it)."""

    name: str
    kind: OptionKind
    default: object = None
    help_key: str = ""
    flags: tuple[str, ...] = ()
    positional: bool = False
    choices: tuple[str, ...] = ()
    minimum: float | None = None
    maximum: float | None = None


@dataclass(frozen=True)
class Feature:
    """A feature the CLI and the GUI can start from the very same description."""

    key: str
    title_key: str
    help_key: str
    run: Callable[[CmdArgs], int]
    options: tuple[Option, ...]
    requires: tuple[Requirement, ...] = ()
    writes: bool = False
    uses_rules: bool = False


def _add_option(parser: argparse.ArgumentParser, option: Option) -> None:
    """Add one :class:`Option` to ``parser``.

    Eine eigene ``add_argument``-Zeile je ``kind``: so bleibt der Typvertrag
    konkret (``type=str``/``int``/``float``, ``choices``) statt in einem
    untypisierten ``**kwargs``-Dictionary zu verschwinden.
    """
    help_text = i18n.t(option.help_key) if option.help_key else None

    if option.positional:
        parser.add_argument(option.name, help=help_text)
        return

    if not option.flags:
        raise ValueError(f"option {option.name!r} is neither positional nor flagged")

    if option.kind == "bool":
        if option.default:
            raise NotImplementedError(
                f"bool option {option.name!r} with default True is not supported")
        parser.add_argument(*option.flags, dest=option.name, action="store_true",
                            default=False, help=help_text)
    elif option.kind in ("folder", "text"):
        parser.add_argument(*option.flags, dest=option.name, default=option.default,
                            help=help_text, type=str)
    elif option.kind == "choice":
        parser.add_argument(*option.flags, dest=option.name, default=option.default,
                            help=help_text, type=str, choices=option.choices)
    elif option.kind == "int":
        parser.add_argument(*option.flags, dest=option.name, default=option.default,
                            help=help_text, type=int)
    elif option.kind == "float":
        parser.add_argument(*option.flags, dest=option.name, default=option.default,
                            help=help_text, type=float)
    else:
        raise ValueError(f"unknown option kind: {option.kind!r}")


def add_feature_parser(subparsers, feature: Feature,
                       common_parent: argparse.ArgumentParser | None = None
                       ) -> argparse.ArgumentParser:
    """Register ``feature`` as a sub-command built from its :class:`Option` list."""
    parents = [common_parent] if common_parent is not None else []
    parser = subparsers.add_parser(feature.key, parents=parents,
                                   help=i18n.t(feature.help_key))
    for option in feature.options:
        _add_option(parser, option)
    parser.set_defaults(func=feature.run, feature=feature)
    return parser


def resolve_args(feature: Feature, args: CmdArgs) -> SimpleNamespace:
    """Fill every option the caller left out with its default.

    ``args`` darf ein ``Namespace``, ein ``SimpleNamespace`` oder ein Mapping
    sein. Ein Objekt ohne Attribute wird laut abgelehnt: still mit lauter
    Standardwerten weiterzulaufen wäre schlimmer als ein klarer Fehler.
    """
    if isinstance(args, Mapping):
        values = dict(args)
    elif hasattr(args, "__dict__"):
        values = dict(vars(args))
    else:
        raise TypeError(f"cannot read options from {type(args).__name__}")
    for option in feature.options:
        if option.name not in values:
            values[option.name] = option.default
    return SimpleNamespace(**values)
