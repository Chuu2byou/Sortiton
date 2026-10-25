"""Cleaning rules and the custom-rule file."""

from __future__ import annotations

from _support import (
    Path,
    check,
    rules,
    tempfile,
)


def test_rules() -> None:
    check("genre keeps J-Pop", rules.clean_genre("Jpop") == "J-Pop")
    check("genre splits at comma", rules.clean_genre("Rock,Pop") == "Rock; Pop")
    check("artist splits at &", rules.clean_artist("Sample Band & Guest") == "Sample Band; Guest")
    check("artist feat", rules.clean_artist("Sample Band feat. Guest") == "Sample Band; Guest")
    check("artist idempotent",
          rules.clean_artist(rules.clean_artist("Sample Band & Guest")) == "Sample Band; Guest")
    check("builtin overview has content", len(rules.builtin_rules_text().splitlines()) > 40)
    check("template contains both sections",
          "[Artist]" in rules.rules_template() and "[Protected]" in rules.rules_template())


def test_custom_rules() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "my_rules.ini"
        path.write_text(
            "[Artist]\n"
            "DJ Example = Example DJ\n"
            "\n"
            "[Artist Regex]\n"
            "(?i)\\bexample\\s+group\\b = Example Group\n"
            "\n"
            "[Genre]\n"
            "junkgenre = \n"
            "\n"
            "[Protected]\n"
            "Demo & Co\n"
            "Foo/Bar = Foo / Bar\n",
            encoding="utf-8")

        warnings = rules.load_custom_rules(path)
        check("no warnings", not warnings, str(warnings))
        check("simple replacement", rules.clean_artist("dj example") == "Example DJ")
        check("regex replacement", rules.clean_artist("example  group") == "Example Group")
        check("protected is not split", rules.clean_artist("Demo & Co") == "Demo & Co")
        check("protected spelling", rules.clean_artist("Foo/Bar") == "Foo / Bar")
        check("empty genre deletes", rules.clean_genre("junkgenre") == "")
        snapshot = rules._custom_rules()
        check("load swaps one consistent snapshot",
              len(snapshot.artists) == 1 and len(snapshot.regex) == 1
              and snapshot.genres.get("junkgenre") == ""
              and len(snapshot.protected) == 2,
              str((len(snapshot.artists), len(snapshot.regex), snapshot.genres,
                   len(snapshot.protected))))

    # parse_custom_rules does the same work without the file system - the GUI
    # uses it to check a pasted LLM answer before it reaches the editor.
    parsed, warnings = rules.parse_custom_rules("[Artist]\nDJ Example = Example DJ\n")
    check("parse_custom_rules is warning-free", not warnings, str(warnings))
    check("parse_custom_rules reads a rule", len(parsed.artists) == 1, str(parsed.artists))
    _parsed, warnings = rules.parse_custom_rules("[Genre]\njunkgenre\n")
    check("parse_custom_rules reports a missing '='", len(warnings) == 1, str(warnings))
    _parsed, warnings = rules.parse_custom_rules("this is = not an ini\n")
    check("parse_custom_rules reports broken INI", len(warnings) == 1, str(warnings))

    # extract_ini_block: the first ```ini block wins, otherwise the whole text.
    answer = ("Sure, here are the rules:\n\n"
              "```ini\n[Artist]\nDJ Example = Example DJ\n```\n\n"
              "Tell me if you need more.")
    check("extract_ini_block takes the fenced block",
          rules.extract_ini_block(answer) == "[Artist]\nDJ Example = Example DJ",
          repr(rules.extract_ini_block(answer)))
    check("extract_ini_block falls back to the whole text",
          rules.extract_ini_block("[Genre]\njunkgenre = ") == "[Genre]\njunkgenre = ")
    check("extract_ini_block tolerates an unterminated fence",
          rules.extract_ini_block("```ini\n[Artist]\na = b") == "[Artist]\na = b")

    rules.load_custom_rules()


def test_separator_and_protected_order() -> None:
    """``|`` works like ``;`` in [Artist]; [Protected] wins over [Artist]."""
    parsed, warnings = rules.parse_custom_rules(
        "[Artist]\nMori Calliope | 森カリオペ = Mori Calliope\n")
    check("pipe rule matches the internal semicolon form",
          rules.clean_artist("Mori Calliope; 森カリオペ", parsed) == "Mori Calliope",
          rules.clean_artist("Mori Calliope; 森カリオペ", parsed))
    check("pipe rule matches the export spelling",
          rules.clean_artist("Mori Calliope | 森カリオペ", parsed) == "Mori Calliope",
          rules.clean_artist("Mori Calliope | 森カリオペ", parsed))
    check("pipe rule warns once", len(warnings) == 1, str(warnings))

    parsed, warnings = rules.parse_custom_rules("[Artist Regex]\n(A|B) = X\n")
    check("regex alternation is not reported as a separator", not warnings, str(warnings))

    parsed, _warnings = rules.parse_custom_rules("[Artist]\nK/DA = K／DA\n")
    check("artist rule replaces before the split",
          rules.clean_artist("K/DA", parsed) == "K／DA",
          rules.clean_artist("K/DA", parsed))

    parsed, _warnings = rules.parse_custom_rules("[Artist]\nK/DA = K/DA\n")
    check("a no-op rule does not protect a name",
          rules.clean_artist("K/DA", parsed) == "K; DA",
          rules.clean_artist("K/DA", parsed))

    parsed, warnings = rules.parse_custom_rules(
        "[Protected]\nK/DA\n[Artist]\nK/DA = K／DA\n")
    check("protected wins over artist", rules.clean_artist("K/DA", parsed) == "K/DA",
          rules.clean_artist("K/DA", parsed))
    check("the conflict is reported", len(warnings) == 1, str(warnings))

    parsed, _warnings = rules.parse_custom_rules("[Protected]\nK/DA = K／DA\n")
    check("protected can carry the wanted spelling",
          rules.clean_artist("K/DA", parsed) == "K／DA",
          rules.clean_artist("K/DA", parsed))

    check("genres split at the export separator",
          rules.clean_genre("Rock | Pop") == "Rock; Pop",
          rules.clean_genre("Rock | Pop"))


def test_unsafe_regex_rules_are_rejected() -> None:
    """Verschachtelte/alternierende Quantoren und überlange Muster werden verworfen."""
    text = ("[Artist Regex]\n"
            "(a+)+$ = nested\n"
            "(ab|cd)+$ = alternating\n"
            + "a" * 501 + " = too_long\n"
            "safe = done\n")
    parsed, warnings = rules.parse_custom_rules(text)

    check("only the safe rule was loaded",
          len(parsed.regex) == 1, str([pattern.pattern for pattern, _ in parsed.regex]))
    check("all three unsafe rules were reported", len(warnings) == 3, str(warnings))
    check("the safe rule is the expected one",
          parsed.regex[0][0].pattern == "safe", parsed.regex[0][0].pattern)
