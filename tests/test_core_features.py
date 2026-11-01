"""Gemeinsame Beschreibungen der Kernaufträge."""

from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from sortiton import cli
from sortiton.core_features import CORE_FEATURES, PATTERN_DEFAULT
from sortiton.gui.mixins.pages import PageMixin


@pytest.mark.parametrize("key", ["tags", "rename", "sort", "all"])
def test_core_parser_defaults_and_choices(key):
    parser = cli._build_parser()
    arguments = [key, "source"] + (["target"] if key in ("sort", "all") else [])
    args = parser.parse_args(arguments)
    assert args.command == key
    assert args.target == ("target" if key in ("sort", "all") else None)
    assert args.quiet is False
    assert args.move is False
    assert args.apply is False
    assert not hasattr(args, "feature")
    if key != "tags":
        assert args.pattern == PATTERN_DEFAULT
    if key in ("tags", "all"):
        assert (args.backup, args.track_format, args.diff, args.diff_csv) == (False, None, False, None)
        with pytest.raises(SystemExit) as error:
            parser.parse_args(arguments + ["--track-format", "invalid"])
        assert error.value.code == 2


def test_optional_targets_and_cli_only_options():
    parser = cli._build_parser()
    tags = parser.parse_args(["tags", "source", "target", "--move", "--apply", "--backup",
                              "--track-format", "padded", "--diff", "--diff-csv", "out.csv", "-q"])
    assert (tags.folder, tags.target, tags.move, tags.apply, tags.backup, tags.track_format,
            tags.diff, tags.diff_csv, tags.quiet) == (
                "source", "target", True, True, True, "padded", True, "out.csv", True)
    assert parser.parse_args(["rename", "source", "target"]).target == "target"
    assert [feature.key for feature in CORE_FEATURES] == ["tags", "rename", "sort", "all"]


def test_core_help_retains_options(capsys):
    parser = cli._build_parser()
    with pytest.raises(SystemExit) as error:
        parser.parse_args(["all", "--help"])
    help_text = capsys.readouterr().out
    assert error.value.code == 0
    for text in ("source", "target", "--pattern", "--move", "--apply", "--backup",
                 "--track-format", "--diff", "--diff-csv", "--quiet"):
        assert text in help_text


@pytest.mark.parametrize("feature", CORE_FEATURES, ids=lambda feature: feature.key)
def test_core_page_uses_declared_fields_and_actions(feature):
    page, options, source, target, mode, pattern = (object() for _ in range(6))
    run = Mock()
    app = SimpleNamespace(_new_page=Mock(return_value=page), _page_header=Mock(),
                          _folder_card=Mock(), _card=Mock(return_value=options),
                          _pattern_row=Mock(), _mode_row=Mock(), _hint=Mock(),
                          _rules_card=Mock(), _preview_card=Mock(), _actions=Mock())
    setattr(app, feature.source_var, source)
    setattr(app, feature.target_var, target)
    setattr(app, feature.mode_var, mode)
    setattr(app, feature.run_method, run)
    if feature.pattern_var:
        setattr(app, feature.pattern_var, pattern)
    assert PageMixin._core_page(app, object(), feature.key) is page
    assert [entry[1] for entry in app._folder_card.call_args.args[3]] == [source, target]
    app._mode_row.assert_called_once_with(options, 2 if feature.pattern_var else 0, mode)
    assert app._pattern_row.call_count == bool(feature.pattern_var)
    assert app._rules_card.call_count == feature.show_rules
    assert app._hint.call_count == feature.show_pattern_hint
    actions = app._actions.call_args.kwargs
    actions["preview"]()
    actions["execute"]()
    assert [call.args for call in run.call_args_list] == [(False,), (True,)]
