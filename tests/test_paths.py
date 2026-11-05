"""Gemeinsame Pfadprüfung für Vorschau und Ausführung."""

from pathlib import Path
from types import SimpleNamespace

import pytest

from sortiton.paths import PathProblem, check_core_paths


def test_core_path_rules(tmp_path: Path) -> None:
    """Quelle, optionales Ziel und Zielbeziehungen werden einheitlich geprüft."""
    source = tmp_path / "source"
    source.mkdir()
    assert check_core_paths("", "").problem == PathProblem.SOURCE_MISSING
    assert check_core_paths(tmp_path / "missing", "").problem == PathProblem.SOURCE_INVALID
    assert check_core_paths(source, "").problem is None
    assert check_core_paths(source, "", target_required=True).problem == PathProblem.TARGET_MISSING
    assert check_core_paths(source, source).problem == PathProblem.TARGET_IN_SOURCE
    assert check_core_paths(source, source / "new").problem == PathProblem.TARGET_IN_SOURCE
    assert check_core_paths(source, tmp_path).problem is None
    assert check_core_paths(source, tmp_path / "new" / "library").problem is None
    assert not (tmp_path / "new").exists()


def test_target_preflight(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Dateien und nicht beschreibbare Elternordner werden früh abgewiesen."""
    source = tmp_path / "source"
    source.mkdir()
    file = tmp_path / "file"
    file.write_text("x", encoding="utf-8")
    assert check_core_paths(source, file).problem == PathProblem.TARGET_INVALID
    assert check_core_paths(source, file / "child").problem == PathProblem.TARGET_INVALID
    monkeypatch.setattr("sortiton.paths.os.access", lambda *_: False)
    assert check_core_paths(source, tmp_path / "new").problem == PathProblem.TARGET_UNWRITABLE


def test_invalid_user_expansion(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Nicht auflösbare Home-Verzeichnisse erzeugen strukturierte Fehler."""
    original = Path.expanduser

    def expand(path: Path) -> Path:
        if str(path).startswith("~missing-user"):
            raise RuntimeError("Benutzer unbekannt")
        return original(path)

    monkeypatch.setattr(Path, "expanduser", expand)
    assert check_core_paths("~missing-user/source", "").problem == PathProblem.SOURCE_INVALID
    assert check_core_paths(tmp_path, "~missing-user/target").problem == PathProblem.TARGET_INVALID


def test_target_symlinks(tmp_path: Path) -> None:
    """Aliase der Quelle und kaputte Ziel-Links werden erkannt."""
    source = tmp_path / "source"
    source.mkdir()
    alias = tmp_path / "alias"
    alias.symlink_to(source, target_is_directory=True)
    assert check_core_paths(source, alias / "nested").problem == PathProblem.TARGET_IN_SOURCE
    broken = tmp_path / "broken"
    broken.symlink_to(tmp_path / "missing", target_is_directory=True)
    assert check_core_paths(source, broken / "nested").problem == PathProblem.TARGET_INVALID


@pytest.mark.parametrize("output_kind", ["same", "nested", "symlink", "default"])
def test_export_refuses_output_inside_source(tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
                                             output_kind: str) -> None:
    """Export sperrt auch indirekte und automatisch bestimmte Ziele in der Quelle."""
    from dataclasses import replace
    from sortiton import config
    from sortiton.features.export import cmd_export

    source = tmp_path / "source"
    source.mkdir()
    alias = tmp_path / "alias"
    alias.symlink_to(source, target_is_directory=True)
    outputs = {"same": str(source), "nested": str(source / "reports"),
               "symlink": str(alias / "reports"), "default": ""}
    monkeypatch.setattr("sortiton.features.export.external.missing", lambda *_: [])
    args = SimpleNamespace(folder=str(source), output=outputs[output_kind])
    paths = replace(config.current_paths(), export_dir=source / "exports")
    with config.use_paths(paths):
        assert cmd_export(args) == 2
    assert not list(source.iterdir())


def test_folder_persistence_and_defaults(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Persistierte Ordner, Umgebungswerte und ungültige Ziele haben klare Priorität."""
    from dataclasses import replace
    from sortiton import config, settings

    monkeypatch.delenv("SORTITON_FOLDER", raising=False)
    monkeypatch.delenv("SORTITON_TARGET", raising=False)
    source = tmp_path / "source"
    source.mkdir()
    other = tmp_path / "other"
    other.mkdir()
    paths = replace(config.current_paths(), settings_file=tmp_path / "settings.ini",
                    music_source_dir=source, music_target_dir=source)
    with config.use_paths(paths):
        defaults = settings.restore_folder_values(paths)
        assert defaults["sort_source"] == str(source)
        assert defaults["sort_target"] == defaults["all_target"] == ""
        assert settings.save_folder_values({"sort_source": str(other),
                                            "sort_target": str(tmp_path / "library"),
                                            "all_target": str(source / "nested"),
                                            "tags_target": ""})
        restored = settings.restore_folder_values(paths)
        assert restored["sort_source"] == str(other)
        assert restored["sort_target"] == str(tmp_path / "library")
        assert restored["all_target"] == restored["tags_target"] == ""
        monkeypatch.setenv("SORTITON_FOLDER", str(source))
        monkeypatch.setenv("SORTITON_TARGET", str(tmp_path / "env-target"))
        paths = replace(paths, music_target_dir=tmp_path / "env-target")
        env_values = settings.restore_folder_values(paths)
        assert env_values["sort_source"] == str(source)
        assert env_values["sort_target"] == str(tmp_path / "env-target")


def test_path_metadata_invariants() -> None:
    """Jede Ordneroption trägt eine Rolle und jedes Kernziel eine Regel."""
    from sortiton.core_features import CORE_FEATURES
    from sortiton.features import FEATURES

    for feature in (*CORE_FEATURES, *FEATURES):
        for option in feature.options:
            if option.kind == "folder":
                assert option.path_role in {"source_folder", "target_folder",
                                            "optional_target_folder", "output_folder"}
        if feature in CORE_FEATURES:
            assert sum(option.path_role == "source_folder" for option in feature.options) == 1
            assert sum(option.path_role in {"target_folder", "optional_target_folder"}
                       for option in feature.options) == 1


@pytest.mark.parametrize("page", ["tags", "rename", "sort", "all"])
@pytest.mark.parametrize("apply", [False, True])
def test_tasks_reject_file_as_target(tmp_path: Path, page: str, apply: bool) -> None:
    """Ungültige Ziele werden vor jeder Vorschau und jedem Schreibauftrag abgelehnt."""
    from sortiton import tasks

    source = tmp_path / "source"
    source.mkdir()
    target = tmp_path / "file"
    target.write_text("unverändert", encoding="utf-8")
    args = SimpleNamespace(folder=str(source), source=str(source), target=str(target),
                           pattern="%title%", move=False, apply=apply, backup=False)
    assert getattr(tasks, f"cmd_{page}")(args) == 2
    assert target.read_text(encoding="utf-8") == "unverändert"
