"""Translations (English / German).

Every user-visible text lives here as a key; use :func:`t` to translate.
Placeholders use ``str.format`` style. Missing keys fall back to English.
"""

from __future__ import annotations

LANGUAGES: tuple[str, ...] = ("en", "de")
DEFAULT_LANGUAGE = "en"

_EN: dict[str, str] = {
    # command line
    "cli.description": "Clean tags, rename and sort a music library. Only --apply writes.",
    "cli.tags.help": "Clean tags (artist, album artist, title, album, genre)",
    "cli.tags.folder": "music folder (recursive)",
    "cli.tags.apply": "write the changes",
    "cli.rename.help": "Rename files from their tags",
    "cli.rename.folder": "music folder (recursive)",
    "cli.rename.pattern": 'name pattern (default: "%%artist%% - %%title%%")',
    "cli.rename.apply": "rename the files",
    "cli.sort.help": "Sort into artist/album folders",
    "cli.sort.source": "source folder (unsorted)",
    "cli.sort.target": "target folder (library)",
    "cli.sort.pattern": 'file name pattern (default: "%%artist%% - %%title%%")',
    "cli.sort.move": "move instead of copy",
    "cli.sort.apply": "sort the files",
    "cli.all.help": "All-in-one: clean tags + rename + sort",
    "cli.all.source": "source folder (unsorted)",
    "cli.all.target": "target folder (library)",
    "cli.all.pattern": 'file name pattern (default: "%%artist%% - %%title%%")',
    "cli.all.move": "move instead of copy",
    "cli.all.apply": "run everything",
    "cli.rules.help": "Show or create your own rules (my_rules.ini)",
    "cli.rules.template": "write the template if the file does not exist yet",
    "cli.rules.builtin": "print an overview of all built-in rules",
    "cli.error.ffprobe": "  ERROR: ffprobe is missing - install ffmpeg (apt, dnf or pacman).",
    "cli.log_file": "  Log file: {path}",
    "cli.scan.help": "count files, albums and artists (nothing is changed)",
    "cli.scan.folder": "music folder (recursive)",
    "cli.tags.backup": "copy the files into a backup folder before writing",
    "cli.all.backup": "copy the files into a backup folder before writing",
    "cli.rule_warning": "  RULE WARNING: {text}",
    "cli.custom_rules": "  Custom rules: {summary}  ({file})",
    "cli.cancelled": "  Cancelled.",

    # output / log file
    "log.title": "# Sortiton - log",
    "log.start": "# Start   : {time}",
    "log.command": "# Command : {command}",
    "log.system": ("# System  : ffprobe={ffprobe}, mutagen={mutagen}, "
                   "read={read} workers, write={write} workers"),
    "log.end": "# End     : {time}",
    "log.end_rc": "# End     : {time}  (rc={rc})",
    "log.available": "ok",
    "log.missing": "missing",
    "log.mode.preview": "PREVIEW (nothing will be changed)",
    "log.mode.live": "LIVE (changes will be written)",
    "log.mode_line": "  Mode: {mode}",

    # file names
    "file.error.no_free_name": "No free target name found for: {path}",

    # tasks (cli commands)
    "task.error.folder": "  ERROR: Folder not found: {path}",
    "task.error.source": "  ERROR: Source folder not found: {path}",
    "task.label.folder": "  Folder  : {value}",
    "task.label.source": "  Source  : {value}",
    "task.label.target": "  Target  : {value}",
    "task.label.pattern": "  Pattern : {value}",
    "task.label.files": "  Files   : {value}",
    "task.label.mode": "  Mode    : {value}",
    "task.title.tags": "MUSIC - TAG CLEANUP",
    "task.title.rename": "MUSIC - RENAME (tags -> file name)",
    "task.title.sort": "MUSIC - SORT  [{action}]",
    "task.title.all": "MUSIC - ALL-IN-ONE  (tags -> rename -> sort)",
    "task.action.move": "MOVE",
    "task.action.copy": "COPY",
    "task.writing": "  Writing {count} file(s) …",
    "task.progress.writing": "writing …",
    "task.progress.sorting": "sorting …",
    "task.ok": "  OK: {name}",
    "task.error.file": "  ERROR '{name}': {error}",
    "task.progress.backup": "backing up …",
    "task.backup.done": "  Backup of {count} file(s): {path}",
    "task.backup.failed": "  Backup folder could not be created ({path}): {error}",
    "task.backup.file_error": "  BACKUP FAILED '{name}': {error}",
    "task.scan.done": "  {files} files · {albums} albums · {artists} artists",
    "task.tags.done": "  Done. Files changed: {changed} / {total}",
    "task.rename.done": "  Renamed: {renamed}   Already correct/skipped: {skipped}",
    "task.sort.done": "  Processed: {done} / {total}   Skipped: {skipped}",
    "task.error.count": "  Errors: {count}",
    "task.hint.apply": "  --> Append --apply to write.",
    "task.hint.apply_run": "  --> Append --apply to run it.",
    "task.step": "#  {title}",
    "task.aborted": "  ABORTED in '{title}' (rc={rc}).",
    "task.all.done": "  ALL-IN-ONE finished. ({mode})",
    "task.mode.applied": "applied",
    "task.mode.preview": "preview",
    "task.step.tags": "1/3 · Clean tags",
    "task.step.rename": "2/3 · Rename",
    "task.step.sort": "3/3 · Sort",

    # rules subcommand
    "rules.file": "  Rule file : {path}",
    "rules.created": "  Created   : {path}",
    "rules.present": "  Present   : {path}  (unchanged)",
    "rules.error.create": "  ERROR: could not create the template: {error}",
    "rules.loaded": "  Loaded    : {summary}",
    "rules.none": "no entries (file empty or comments only)",
    "rules.warning": "  WARNING   : {text}",
    "rules.status.ok": "  Status    : in order",
    "rules.status.missing": "  Status    : not created yet - only the built-in rules apply.",
    "rules.hint.create": "  --> Create:  python3 sortiton.py rules --template",
    "rules.hint.gui": "  --> Or in the GUI: the “Custom Rules …” button, top right.",
    "rules.hint.builtin": "  --> Overview of all built-in rules:  ... rules --builtin",
    "rules.builtin.note1": "  Your own rules (my_rules.ini) extend this list and run afterwards.",
    "rules.builtin.note2": "  Create:  python3 sortiton.py rules --template",

    # rule file parser warnings
    "rules.warn.read": "Rule file could not be read ({file}): {error}",
    "rules.warn.invalid": "Rule file is invalid ({file}): {error}",
    "rules.warn.artist_no_equals": 'Artist rule "{rule}" without "=" - skipped (old = new).',
    "rules.warn.regex_no_equals": 'Regex rule "{rule}" without "=" - skipped (pattern = replacement).',
    "rules.warn.regex_invalid": 'Regex rule "{rule}" is invalid - skipped: {error}',
    "rules.warn.genre_no_equals": 'Genre rule "{rule}" without "=" - skipped (old = new).',
    "rules.summary.artists": "{count} artist",
    "rules.summary.artists_plural": "{count} artists",
    "rules.summary.regex": "{count} regex",
    "rules.summary.genre": "{count} genre",
    "rules.summary.protected": "{count} protected",

    # name of the rules file / header of the built-in overview
    "rules.overview.header1": "# -- built-in rules, always active (overview only)",
    "rules.overview.header2": "#  Hard-coded. Your own rules (above) extend them and run AFTER",
    "rules.overview.header3": "#  them, so they have the last word.",
    "rules.overview.header4": "#  To keep a built-in fix away from one name, put that name under",
    "rules.overview.header5": "#  [Protected] - it stays untouched then.",
    "rules.overview.genre_title": "#  [Genre] spellings (case does not matter):",
    "rules.overview.genre_fixed": "#    Fixed genre rules:",
    "rules.overview.genre_f1": '#      - is never split at "-" (J-Pop stays J-Pop)',
    "rules.overview.genre_f2": '#      - split at ";" and "," (also "，" and "、")',
    "rules.overview.genre_f3": "#      - empty/duplicate parts are removed",
    "rules.overview.artist_title": "#  [Artist] built-in corrections - applied in THIS order",
    "rules.overview.artist_sub1": "#  (patterns are regular expressions; quoted so that spaces are clear -",
    "rules.overview.artist_sub2": "#   the right-hand side is the literal replacement):",
    "rules.overview.artist_fixed": "#    Fixed artist rules:",
    "rules.overview.artist_f1": '#      - brackets: "Character (CV: Actor)" -> "Actor"; "A (feat. B)" -> "A; B";',
    "rules.overview.artist_f2": '#        idol groups like "A (46)" -> "A; 46"',
    "rules.overview.artist_f3": "#      - invisible characters (zero-width, BIDI …) are removed",
    "rules.overview.artist_f4": '#      - full width becomes western: ＆ -> &, ； -> ;, ， -> ,, 、 -> "; "',
    "rules.overview.artist_f5": '#      - "・" -> "; " (except between single letters, e.g. A・ZU・NA)',
    "rules.overview.artist_f6": '#      - separators "/", "&", " x "/"×" and "," become "; "',
    "rules.overview.artist_f7": '#        "feat./ft./featuring/meets" -> "; "',
    "rules.overview.artist_f8": '#      - empty parts/duplicates are removed ("Art; ; Subculture" -> "Art; Subculture")',
    "rules.overview.artist_f9": '#      - "Orchestr; a; Plays" -> "Orchestra Plays"',
    "rules.overview.protected_title": "#  [Protected] always protected (never split):",

    # template for my_rules.ini
    "rules.template.header": """\
# Your own rules for Sortiton (my_rules.ini).
# Read on every run. The built-in rules stay active - this file only adds to
# them, and no source code is needed.
#
#  Format: one rule per line "old = new"
#
#    [Artist]         replacements for artist / album artist
#                     (case is ignored)
#    [Artist Regex]   replacements using a regular expression (groups like \\1 work)
#    [Genre]          unify genre spellings -
#                     an empty value right of the "=" deletes the genre
#    [Protected]      names that must stay as they are (e.g. containing "&",
#                     "/" or ",") - they are never split. Optional:
#                     "= preferred spelling" after them.
#
#  The examples below are commented out (#) - adjust and extend them.

[Artist]
# Sample Band = Sample Band Official

[Artist Regex]
# (?i)\\bsample\\s+band\\b = Sample Band

[Genre]
# synthpop = Synth-Pop
# junkgenre = 

[Protected]
# Example & Co
# Foo/Bar = Foo / Bar""",

    # GUI
    "gui.window.title": "Sortiton",
    "gui.button.custom_rules": "Custom Rules …",
    "gui.chip.ffprobe_checking": "ffprobe …",
    "gui.chip.mutagen_checking": "mutagen …",
    "gui.chip.ffprobe_ok": "ffprobe ✓",
    "gui.chip.ffprobe_missing": "ffprobe missing!",
    "gui.chip.mutagen_ok": "mutagen ✓",
    "gui.chip.mutagen_missing": "mutagen missing (slower)",
    "gui.tab.tags": "Clean tags",
    "gui.tab.rename": "Rename",
    "gui.tab.sort": "Sort",
    "gui.tab.all": "Apply all",
    "gui.button.preview": "Preview",
    "gui.button.change": "Change…",
    "gui.button.write_tags": "Write tags",
    "gui.button.rename": "Rename",
    "gui.button.sort": "Sort",
    "gui.button.run_all": "Run all",
    "gui.button.clear": "Clear",
    "gui.button.open_folder": "Open folder",
    "gui.button.open_logs": "Open logs",
    "gui.button.insert_template": "Insert template",
    "gui.button.builtin_rules": "Built-in rules",
    "gui.button.system_editor": "System editor",
    "gui.button.cancel": "Cancel",
    "gui.button.save": "Save",
    "gui.label.music_folder": "Music folder",
    "gui.label.source_folder": "Source folder",
    "gui.label.target_folder": "Target folder",
    "gui.label.pattern": "Name pattern",
    "gui.label.mode": "Mode",
    "gui.mode.copy": "Copy",
    "gui.mode.move": "Move",
    "gui.label.log": "Log",
    "gui.hint.tags": ("Cleans artist, album artist, title, album and genre. Own rules go "
                     "into “Custom Rules …”, top right."),
    "gui.hint.rename_placeholders": "Placeholders: %artist%  %albumartist%  %album%  %title%",
    "gui.hint.sort": ("Target: artist/album/file – without an album tag only artist/file. "
                      "A taken name gets “ (2)”, “ (3)” …"),
    "gui.hint.all": "One run: clean tags → rename files → sort into the library.",
    "gui.confirm.tags.title": "Really write the tags?",
    "gui.confirm.tags.text": ("{changes} changes in {files} files:\n"
                              "artist, album artist, title, album and genre.\n\n"
                              "This cannot be undone."),
    "gui.confirm.rename.title": "Really rename the files?",
    "gui.confirm.rename.text": ("{files} files will be renamed using the pattern:\n"
                                "{pattern}\n\nCollisions get “ (2)”, “ (3)” …"),
    "gui.confirm.sort.title": "Really sort?",
    "gui.confirm.sort.text": ("{files} files will be sorted by artist/album ({mode}) into:\n"
                              "{target}\n\nExisting files are never overwritten."),
    "gui.confirm.all.title": "Really run everything?",
    "gui.confirm.all.text": ("Three steps in one run for {files} files:\n\n"
                             "  1. Clean tags\n"
                             "  2. Rename files\n"
                             "  3. Sort into the library ({mode})\n\n"
                             "  Target: {target}"),
    "gui.confirm.note": "A preview changes nothing.",
    "gui.confirm.ok": "Write the changes",
    "gui.confirm.backup": "Create a backup of the original files",
    "gui.confirm.append": "\n\nRun now?",
    "gui.dialog.pick_folder": "Choose folder",
    "gui.dialog.target_missing.title": "Target folder missing",
    "gui.dialog.target_missing.text": "Choose a target folder first.",
    "gui.dialog.folder_missing.title": "Folder missing",
    "gui.dialog.folder_missing.text": "Choose a folder first.",
    "gui.dialog.folder_not_found.title": "Folder not found",
    "gui.dialog.folder_not_found.text": "This folder does not exist:\n{path}",
    "gui.dialog.ffmpeg_missing.title": "ffmpeg missing",
    "gui.dialog.ffmpeg_missing.text": ("ffprobe was not found.\n\nPlease install ffmpeg, e.g.:\n"
                                       "  Debian / Ubuntu:  sudo apt install ffmpeg\n"
                                       "  Fedora:           sudo dnf install ffmpeg\n"
                                       "  Arch / Manjaro:   sudo pacman -S ffmpeg"),
    "gui.dialog.save_failed.title": "Saving failed",
    "gui.dialog.save_failed.text": "The rule file could not be written:\n\n{error}",
    "gui.status.ready": "ready",
    "gui.status.running": "running…",
    "gui.status.failed": "failed (rc={rc})",
    "gui.status.progress": "{current} / {total} · {text}",
    "gui.job.tags": "Tag cleanup",
    "gui.job.rename": "Rename",
    "gui.job.sort": "Sort",
    "gui.job.all": "Apply all",
    "gui.job.preview": "{name} (preview)",
    "gui.job.run": "{name} (run)",
    "gui.log.job": "▶ {description}",
    "gui.log.log_file": "  Log file: {path}",
    "gui.log.error": "ERROR:\n{text}",
    "gui.log.rule_warning": "  Rule warning: {text}",
    "gui.log.rules": "  {prefix}: {summary}  ({file})",
    "gui.log.no_rules": "no rules loaded",
    "gui.rules.prefix": "Custom rules",
    "gui.rules.prefix_saved": "Custom rules saved",
    "gui.rules.editor.title": "Custom Rules – my_rules.ini",
    "gui.rules.editor.heading": "Custom Rules",
    "gui.rules.editor.hint": 'One rule per line "old = new" - saved to {path}',
    "gui.rules.status.template": "Template inserted - not saved yet",
    "gui.rules.status.builtin_present": "The built-in rules are already included",
    "gui.rules.status.builtin_added": "Overview of the built-in rules appended - not saved yet",
    "gui.rules.status.saved_warnings": "Saved, {count} warnings - see the log",
    "gui.rules.status.saved": "Saved ✓  ({summary})",
    "gui.rules.status.none": "no entries",
    "gui.rules.confirm_template.title": "Insert template?",
    "gui.rules.confirm_template.text": ("The text in the field will be replaced by the template - "
                                        "the file itself stays unchanged until you save."),
    "gui.language.de": "DE",
    "gui.language.en": "EN",
    "gui.dialog.busy.title": "Please wait",
    "gui.dialog.busy.text": "A task is still running. Wait until it is done.",

    # cards, sections and result view
    "gui.button.settings": "Settings",
    "gui.button.choose_folder": "Choose folder",
    "gui.button.refresh": "Refresh",
    "gui.button.preview_create": "Create preview",
    "gui.button.details": "Show details",
    "gui.button.back": "Back",
    "gui.button.close": "Close",
    "gui.button.open_backup": "Open backup",
    "gui.section.music_folder": "Music folder",
    "gui.section.options": "Options",
    "gui.section.active_rules": "Active cleanup",
    "gui.section.preview": "Preview",
    "gui.section.result": "Result",
    "gui.label.last_entries": "Latest entries",
    "gui.stats.unknown": "No folder scanned yet",
    "gui.stats.scanning": "Counting files …",
    "gui.stats.press_refresh": "“Refresh” counts the files",
    "gui.stats.summary": "{files} audio files · {albums} albums · {artists} artists",
    "gui.pill.artist": "Artist {count}",
    "gui.pill.regex": "Pattern {count}",
    "gui.pill.genre": "Genre {count}",
    "gui.pill.protected": "Protected {count}",
    "gui.pill.builtin": "Built-in fixes {count}",
    "gui.pill.none": "No custom rules",
    "gui.pill.warnings": "{count} warnings",
    "gui.preview.none": "No preview yet. “Create preview” shows what would change.",
    "gui.preview.run_first": "Create a preview first",
    "gui.preview.running": "Preview is being created …",
    "gui.preview.stale": "Preview is outdated, create it again",
    "gui.preview.unchanged": "Nothing to do - everything is already correct.",
    "gui.preview.summary_tags": "{changes} changes in {files} files",
    "gui.preview.summary_files": "{files} files affected",
    "gui.preview.more": "+{count} more",
    "gui.field.artist": "Artist",
    "gui.field.album_artist": "Album artist",
    "gui.field.title": "Title",
    "gui.field.album": "Album",
    "gui.field.genre": "Genre",
    "gui.field.file": "File",
    "gui.field.folder": "Folder",
    "gui.result.changed": "changed",
    "gui.result.planned": "changes planned",
    "gui.result.analysed": "files analysed",
    "gui.result.skipped": "skipped",
    "gui.result.errors": "errors",
    "gui.result.tags_changed": "tags cleaned",
    "gui.result.renamed": "files renamed",
    "gui.result.sorted": "files sorted",
    "gui.status.scanning": "Analysing files …",
    "gui.status.percent": "{current} / {total} · {percent} %",
    "gui.log.ffprobe_missing": "  Note: ffprobe is missing - reading tags is slower (install ffmpeg).",
    "gui.settings.title": "Settings",
    "gui.settings.heading": "Settings",
    "gui.settings.backend": "Tag backend",
    "gui.settings.backend_hint": ("Tags use the best backend that is available - no setting "
                                  "needed."),
    "gui.settings.language": "Language",
    "gui.settings.language_hint": "Stored in settings.ini, applied again on the next start.",

    # restore / undo (run journal)
    "cli.restore.help": "Undo the changes of an earlier run",
    "cli.restore.journal": "journal to undo (default: the most recent one)",
    "cli.restore.list": "list the available journals and do nothing else",
    "cli.restore.apply": "actually undo the changes",
    "cli.restore.backup": "copy the files into a backup folder before undoing",
    "cli.restore.keep_copies": "keep the copies of a copy-run (default: delete them)",
    "task.title.restore": "MUSIC - UNDO (restore from the journal)",
    "task.label.journal": "  Journal : {value}",
    "task.label.events": "  Events  : {value}",
    "task.progress.restore": "undoing …",
    "restore.error.no_journal": "  ERROR: no journal found (nothing to undo).",
    "restore.error.schema": ("  ERROR: this journal comes from a newer Sortiton "
                             "({version}; this build knows {known})."),
    "restore.nothing": "  The journal contains no changes.",
    "restore.undoing": "  Undoing {count} changes …",
    "restore.remove_copy": "  remove copy: {name}",
    "restore.ok.tags": "  OK tags   : {name}",
    "restore.ok.copy": "  OK deleted: {name}",
    "restore.ok.move": "  OK back   : {name}",
    "restore.done": "  Done. Undone: {changed}   Skipped: {skipped}   ({total} events)",
    "restore.skip.failed": "  skipped (the run failed): {name}",
    "restore.skip.missing": "  skipped (file is gone): {name}",
    "restore.skip.exists": "  skipped (the old name is taken again): {name}",
    "restore.skip.keep_copy": "  kept (--keep-copies): {name}",
    "restore.skip.only_copy": ("  kept (the original is gone - this is the only copy): "
                                "{name}"),
    "restore.skip.unknown": "  skipped (cannot be undone): {op}",
    "restore.list.title": "  Journals in the log folder: {count}",
    "restore.list.none": "  No journals yet ({path}).",
    "restore.list.empty": "no changes",
    "restore.list.entry": "  {name}   {start}   {summary}",
    "gui.button.undo": "Undo last run …",
    "gui.job.restore": "undo",
    "gui.restore.title": "Undo a run",
    "gui.restore.heading": "Undo the changes of an earlier run",
    "gui.restore.journals": "Journals",
    "gui.restore.none": "No journal was found in the log folder.",
    "gui.restore.pick": "Pick a journal on the left.",
    "gui.restore.summary": "{total} events: {parts}",
    "gui.restore.note": ("Only the changes this journal recorded are undone. Deleted copies "
                          "stay gone."),
    "gui.restore.empty": "This journal holds nothing that can be undone.",
    "gui.restore.run": "Undo now",
    "gui.restore.more": "… and {count} more",
    "gui.restore.op.tags": "Tags",
    "gui.restore.op.move": "Move back",
    "gui.restore.op.copy": "Delete copy",
    "gui.restore.op.failed": "Failed",
    "gui.restore.op.other": "Other",
    "gui.confirm.restore.title": "Undo now?",
    "gui.confirm.restore.text": ("{changes} changes of this run are undone. "
                                  "Deleted copies do not come back."),
    "gui.confirm.keep_copies": "Keep the copies of a copy run",
}

_DE: dict[str, str] = {
    # Kommandozeile
    "cli.description": "Tags bereinigen, umbenennen und eine Bibliothek sortieren. Geschrieben wird nur mit --apply.",
    "cli.tags.help": "Tags bereinigen (Künstler, Album-Künstler, Titel, Album, Genre)",
    "cli.tags.folder": "Musikordner (rekursiv)",
    "cli.tags.apply": "Änderungen schreiben",
    "cli.rename.help": "Dateien aus Tags umbenennen",
    "cli.rename.folder": "Musikordner (rekursiv)",
    "cli.rename.pattern": 'Namensmuster (Standard: "%%artist%% - %%title%%")',
    "cli.rename.apply": "Umbenennen ausführen",
    "cli.sort.help": "Nach Künstler/Album einsortieren",
    "cli.sort.source": "Quellordner (unsortiert)",
    "cli.sort.target": "Zielordner (Bibliothek)",
    "cli.sort.pattern": 'Dateinamensmuster (Standard: "%%artist%% - %%title%%")',
    "cli.sort.move": "Verschieben statt kopieren",
    "cli.sort.apply": "Sortieren ausführen",
    "cli.all.help": "All-in-One: Tags bereinigen + umbenennen + sortieren",
    "cli.all.source": "Quellordner (unsortiert)",
    "cli.all.target": "Zielordner (Bibliothek)",
    "cli.all.pattern": 'Dateinamensmuster (Standard: "%%artist%% - %%title%%")',
    "cli.all.move": "Verschieben statt kopieren",
    "cli.all.apply": "Alles ausführen",
    "cli.rules.help": "Eigene Regeln (my_rules.ini) anzeigen/anlegen",
    "cli.rules.template": "Vorlage anlegen, falls die Datei noch fehlt",
    "cli.rules.builtin": "Übersicht aller eingebauten Regeln ausgeben",
    "cli.error.ffprobe": "  FEHLER: ffprobe fehlt - bitte ffmpeg installieren (apt, dnf oder pacman).",
    "cli.log_file": "  Protokoll: {path}",
    "cli.scan.help": "Dateien, Alben und Künstler zählen (ändert nichts)",
    "cli.scan.folder": "Musikordner (rekursiv)",
    "cli.tags.backup": "Dateien vor dem Schreiben in einen Backup-Ordner kopieren",
    "cli.all.backup": "Dateien vor dem Schreiben in einen Backup-Ordner kopieren",
    "cli.rule_warning": "  REGEL-WARNUNG: {text}",
    "cli.custom_rules": "  Eigene Regeln: {summary}  ({file})",
    "cli.cancelled": "  Abgebrochen.",

    # Ausgabe / Protokolldatei
    "log.title": "# Sortiton - Protokoll",
    "log.start": "# Start   : {time}",
    "log.command": "# Befehl  : {command}",
    "log.system": ("# System  : ffprobe={ffprobe}, mutagen={mutagen}, "
                   "Lesen={read} Worker, Schreiben={write} Worker"),
    "log.end": "# Ende    : {time}",
    "log.end_rc": "# Ende    : {time}  (rc={rc})",
    "log.available": "ok",
    "log.missing": "fehlt",
    "log.mode.preview": "VORSCHAU (nichts wird geändert)",
    "log.mode.live": "LIVE (Änderungen werden ausgeführt)",
    "log.mode_line": "  Modus: {mode}",

    # Dateinamen
    "file.error.no_free_name": "Kein freier Zielname gefunden für: {path}",

    # Aufträge
    "task.error.folder": "  FEHLER: Ordner nicht gefunden: {path}",
    "task.error.source": "  FEHLER: Quellordner nicht gefunden: {path}",
    "task.label.folder": "  Ordner : {value}",
    "task.label.source": "  Quelle : {value}",
    "task.label.target": "  Ziel   : {value}",
    "task.label.pattern": "  Muster : {value}",
    "task.label.files": "  Dateien: {value}",
    "task.label.mode": "  Modus  : {value}",
    "task.title.tags": "MUSIK - TAG-BEREINIGUNG",
    "task.title.rename": "MUSIK - UMBENENNEN (Tags -> Dateiname)",
    "task.title.sort": "MUSIK - SORTIEREN  [{action}]",
    "task.title.all": "MUSIK - ALL-IN-ONE  (Tags -> Umbenennen -> Sortieren)",
    "task.action.move": "MOVE (verschieben)",
    "task.action.copy": "COPY (kopieren)",
    "task.writing": "  Schreibe {count} Datei(en) …",
    "task.progress.writing": "schreibe …",
    "task.progress.sorting": "sortiere …",
    "task.ok": "  OK: {name}",
    "task.error.file": "  FEHLER '{name}': {error}",
    "task.progress.backup": "sichere …",
    "task.backup.done": "  Backup von {count} Datei(en): {path}",
    "task.backup.failed": "  Backup-Ordner konnte nicht angelegt werden ({path}): {error}",
    "task.backup.file_error": "  BACKUP FEHLGESCHLAGEN '{name}': {error}",
    "task.scan.done": "  {files} Dateien · {albums} Alben · {artists} Künstler",
    "task.tags.done": "  Fertig. Dateien mit Änderungen: {changed} / {total}",
    "task.rename.done": "  Umbenannt: {renamed}   Bereits korrekt/übersprungen: {skipped}",
    "task.sort.done": "  Verarbeitet: {done} / {total}   Übersprungen: {skipped}",
    "task.error.count": "  Fehler: {count}",
    "task.hint.apply": "  --> Zum Schreiben: --apply anhängen.",
    "task.hint.apply_run": "  --> Zum Ausführen: --apply anhängen.",
    "task.step": "#  {title}",
    "task.aborted": "  ABBRUCH in '{title}' (rc={rc}).",
    "task.all.done": "  ALL-IN-ONE fertig. ({mode})",
    "task.mode.applied": "ausgeführt",
    "task.mode.preview": "Vorschau",
    "task.step.tags": "1/3 · Tags bereinigen",
    "task.step.rename": "2/3 · Umbenennen",
    "task.step.sort": "3/3 · Sortieren",

    # Unterbefehl „rules“
    "rules.file": "  Regeldatei : {path}",
    "rules.created": "  Angelegt   : {path}",
    "rules.present": "  Vorhanden  : {path}  (nichts geändert)",
    "rules.error.create": "  FEHLER: Vorlage konnte nicht angelegt werden: {error}",
    "rules.loaded": "  Geladen    : {summary}",
    "rules.none": "keine Einträge (Datei leer oder nur Kommentare)",
    "rules.warning": "  WARNUNG    : {text}",
    "rules.status.ok": "  Status     : in Ordnung",
    "rules.status.missing": "  Status     : noch nicht vorhanden – es gelten nur die eingebauten Regeln.",
    "rules.hint.create": "  --> Anlegen:  python3 sortiton.py rules --template",
    "rules.hint.gui": "  --> Oder in der GUI: Button „Custom Rules …“ oben rechts.",
    "rules.hint.builtin": "  --> Übersicht aller eingebauten Regeln:  ... rules --builtin",
    "rules.builtin.note1": "  Eigene Regeln (my_rules.ini) ergänzen diese Liste und laufen danach.",
    "rules.builtin.note2": "  Anlegen:  python3 sortiton.py rules --template",

    # Warnungen des Regel-Parsers
    "rules.warn.read": "Regeldatei konnte nicht gelesen werden ({file}): {error}",
    "rules.warn.invalid": "Regeldatei ist fehlerhaft ({file}): {error}",
    "rules.warn.artist_no_equals": 'Künstler-Regel „{rule}“ ohne „=“ – übersprungen (alt = neu).',
    "rules.warn.regex_no_equals": 'Regex-Regel „{rule}“ ohne „=“ – übersprungen (MUSTER = ERSATZ).',
    "rules.warn.regex_invalid": 'Regex-Regel „{rule}“ ungültig – übersprungen: {error}',
    "rules.warn.genre_no_equals": 'Genre-Regel „{rule}“ ohne „=“ – übersprungen (alt = neu).',
    "rules.summary.artists": "{count} Künstler",
    "rules.summary.artists_plural": "{count} Künstler",
    "rules.summary.regex": "{count} Regex",
    "rules.summary.genre": "{count} Genre",
    "rules.summary.protected": "{count} geschützt",

    # Kopf der eingebauten Regel-Übersicht
    "rules.overview.header1": "# -- Eingebaute Regeln, immer aktiv (nur Übersicht)",
    "rules.overview.header2": "#  Stecken fest im Programm. Eigene Regeln (oben) ergänzen sie und",
    "rules.overview.header3": "#  laufen NACH ihnen – sie haben das letzte Wort.",
    "rules.overview.header4": "#  Damit ein eingebauter Fix bei einem Namen nicht greift: den Namen",
    "rules.overview.header5": "#  unter [Protected] eintragen – dann bleibt er unangetastet.",
    "rules.overview.genre_title": "#  [Genre] Schreibweisen (Groß-/Kleinschreibung ist egal):",
    "rules.overview.genre_fixed": "#    Feste Genre-Regeln:",
    "rules.overview.genre_f1": "#      - „-“ trennt nicht (J-Pop bleibt J-Pop)",
    "rules.overview.genre_f2": "#      - getrennt wird an „;“ und „,“ (auch „，“ und „、“)",
    "rules.overview.genre_f3": "#      - leere und doppelte Teile fallen weg",
    "rules.overview.artist_title": "#  [Künstler] eingebaute Korrekturen – gelten in dieser Reihenfolge",
    "rules.overview.artist_sub1": "#  (Muster sind reguläre Ausdrücke; in Anführungszeichen, damit",
    "rules.overview.artist_sub2": "#   Leerzeichen eindeutig sind – rechts steht der wörtliche Ersatz):",
    "rules.overview.artist_fixed": "#    Feste Künstler-Regeln:",
    "rules.overview.artist_f1": "#      • Klammern: „Figur (CV: Sprecher)“ → „Sprecher“; „A (feat. B)“ → „A; B“;",
    "rules.overview.artist_f2": "#        Idolgruppen wie „A (46)“ → „A; 46“",
    "rules.overview.artist_f3": "#      • unsichtbare Zeichen (Zero-Width, BIDI …) werden entfernt",
    "rules.overview.artist_f4": "#      - Vollbreite wird westlich: ＆ → &, ； → ;, ， → ,, 、 → „; “",
    "rules.overview.artist_f5": "#      • „・“ → „; “ (außer zwischen Einzelbuchstaben, z. B. A・ZU・NA)",
    "rules.overview.artist_f6": "#      - Trenner „/“, „&“, „ x “/„×“ und „,“ werden „; “",
    "rules.overview.artist_f7": "#        „feat./ft./featuring/meets“ → „; “",
    "rules.overview.artist_f8": "#      • leere Segmente/Duplikate werden entfernt („Art; ; Subculture“ → „Art; Subculture“)",
    "rules.overview.artist_f9": "#      • „Orchestr; a; Plays“ → „Orchestra Plays“",
    "rules.overview.protected_title": "#  [Protected] immer geschützt (werden nie getrennt):",

    # Vorlage für my_rules.ini
    "rules.template.header": """\
# Eigene Regeln für Sortiton (my_rules.ini).
# Wird bei jedem Lauf gelesen. Die eingebauten Regeln bleiben aktiv – diese
# Datei ergänzt sie nur, Quellcode ist dafür nicht nötig.
#
#  Aufbau: eine Regel pro Zeile „alt = neu“
#
#    [Artist]         Ersetzungen für Künstler / Album-Künstler
#                     (Groß-/Kleinschreibung wird ignoriert)
#    [Artist Regex]   Ersetzungen per regulärem Ausdruck (Gruppen wie \\1 möglich)
#    [Genre]          Genre-Schreibweisen vereinheitlichen –
#                     ein leerer Wert rechts vom „=“ löscht das Genre
#    [Protected]      Namen, die unverändert bleiben sollen (z. B. mit „&“,
#                     „/“ oder „,“) – sie werden nie getrennt. Optional:
#                     „= Wunsch-Schreibweise“ dahinter.
#
#  Die Beispiele unten sind auskommentiert (#) – einfach anpassen und ergänzen.

[Artist]
# Beispielband = Beispiel Band

[Artist Regex]
# (?i)\\bbeispiel\\s*band\\b = Beispiel Band

[Genre]
# synthiepop = Synth-Pop
# muellgenre = 

[Protected]
# Beispiel & Co
# Foo/Bar = Foo / Bar""",

    # GUI
    "gui.window.title": "Sortiton",
    "gui.button.custom_rules": "Eigene Regeln …",
    "gui.chip.ffprobe_checking": "ffprobe …",
    "gui.chip.mutagen_checking": "mutagen …",
    "gui.chip.ffprobe_ok": "ffprobe ✓",
    "gui.chip.ffprobe_missing": "ffprobe fehlt!",
    "gui.chip.mutagen_ok": "mutagen ✓",
    "gui.chip.mutagen_missing": "mutagen fehlt (langsamer)",
    "gui.tab.tags": "Tags bereinigen",
    "gui.tab.rename": "Umbenennen",
    "gui.tab.sort": "Sortieren",
    "gui.tab.all": "Alles anwenden",
    "gui.button.preview": "Vorschau",
    "gui.button.change": "Ändern…",
    "gui.button.write_tags": "Tags schreiben",
    "gui.button.rename": "Umbenennen",
    "gui.button.sort": "Sortieren",
    "gui.button.run_all": "Alles ausführen",
    "gui.button.clear": "Leeren",
    "gui.button.open_folder": "Ordner öffnen",
    "gui.button.open_logs": "Logs öffnen",
    "gui.button.insert_template": "Vorlage einfügen",
    "gui.button.builtin_rules": "Eingebaute Regeln",
    "gui.button.system_editor": "System-Editor",
    "gui.button.cancel": "Abbrechen",
    "gui.button.save": "Speichern",
    "gui.label.music_folder": "Musikordner",
    "gui.label.source_folder": "Quellordner",
    "gui.label.target_folder": "Zielordner",
    "gui.label.pattern": "Namensmuster",
    "gui.label.mode": "Modus",
    "gui.mode.copy": "Kopieren",
    "gui.mode.move": "Verschieben",
    "gui.label.log": "Protokoll",
    "gui.hint.tags": ("Bereinigt Künstler, Album-Künstler, Titel, Album und Genre. Eigene "
                      "Regeln: „Eigene Regeln …“ oben rechts."),
    "gui.hint.rename_placeholders": "Platzhalter: %artist%  %albumartist%  %album%  %title%",
    "gui.hint.sort": ("Ziel: Künstler/Album/Datei – ohne Album-Tag nur Künstler/Datei. "
                      "Belegte Namen bekommen „ (2)“, „ (3)“ …"),
    "gui.hint.all": ("Ein Durchlauf: Tags bereinigen → Dateien umbenennen → in die Bibliothek "
                     "sortieren."),
    "gui.confirm.tags.title": "Tags wirklich schreiben?",
    "gui.confirm.tags.text": ("{changes} Änderungen in {files} Dateien:\n"
                              "Künstler, Album-Künstler, Titel, Album und Genre.\n\n"
                              "Das lässt sich nicht rückgängig machen."),
    "gui.confirm.rename.title": "Dateien wirklich umbenennen?",
    "gui.confirm.rename.text": ("{files} Dateien werden nach dem Muster umbenannt:\n"
                                "{pattern}\n\nKollisionen bekommen „ (2)“, „ (3)“ …"),
    "gui.confirm.sort.title": "Wirklich sortieren?",
    "gui.confirm.sort.text": ("{files} Dateien werden nach Künstler/Album sortiert ({mode}) nach:\n"
                              "{target}\n\nVorhandene Dateien werden nie überschrieben."),
    "gui.confirm.all.title": "Wirklich alles ausführen?",
    "gui.confirm.all.text": ("Drei Schritte in einem Durchlauf für {files} Dateien:\n\n"
                             "  1. Tags bereinigen\n"
                             "  2. Dateien umbenennen\n"
                             "  3. In die Bibliothek sortieren ({mode})\n\n"
                             "  Ziel: {target}"),
    "gui.confirm.note": "Eine Vorschau ändert nichts.",
    "gui.confirm.ok": "Änderungen schreiben",
    "gui.confirm.backup": "Backup der Originaldateien erstellen",
    "gui.confirm.append": "\n\nJetzt ausführen?",
    "gui.dialog.pick_folder": "Ordner wählen",
    "gui.dialog.target_missing.title": "Zielordner fehlt",
    "gui.dialog.target_missing.text": "Erst einen Zielordner wählen.",
    "gui.dialog.folder_missing.title": "Ordner fehlt",
    "gui.dialog.folder_missing.text": "Erst einen Ordner wählen.",
    "gui.dialog.folder_not_found.title": "Ordner nicht gefunden",
    "gui.dialog.folder_not_found.text": "Dieser Ordner existiert nicht:\n{path}",
    "gui.dialog.ffmpeg_missing.title": "ffmpeg fehlt",
    "gui.dialog.ffmpeg_missing.text": ("ffprobe wurde nicht gefunden.\n\nBitte ffmpeg installieren, z. B.:\n"
                                       "  Debian / Ubuntu:  sudo apt install ffmpeg\n"
                                       "  Fedora:           sudo dnf install ffmpeg\n"
                                       "  Arch / Manjaro:   sudo pacman -S ffmpeg"),
    "gui.dialog.save_failed.title": "Speichern fehlgeschlagen",
    "gui.dialog.save_failed.text": "Die Regeldatei konnte nicht geschrieben werden:\n\n{error}",
    "gui.status.ready": "bereit",
    "gui.status.running": "läuft…",
    "gui.status.failed": "fehlgeschlagen (rc={rc})",
    "gui.status.progress": "{current} / {total} · {text}",
    "gui.job.tags": "Tag-Bereinigung",
    "gui.job.rename": "Umbenennen",
    "gui.job.sort": "Sortieren",
    "gui.job.all": "Alles anwenden",
    "gui.job.preview": "{name} (Vorschau)",
    "gui.job.run": "{name} (ausführen)",
    "gui.log.job": "▶ {description}",
    "gui.log.log_file": "  Protokoll: {path}",
    "gui.log.error": "FEHLER:\n{text}",
    "gui.log.rule_warning": "  Regel-Warnung: {text}",
    "gui.log.rules": "  {prefix}: {summary}  ({file})",
    "gui.log.no_rules": "keine Regeln geladen",
    "gui.rules.prefix": "Eigene Regeln",
    "gui.rules.prefix_saved": "Eigene Regeln gespeichert",
    "gui.rules.editor.title": "Eigene Regeln – my_rules.ini",
    "gui.rules.editor.heading": "Eigene Regeln",
    "gui.rules.editor.hint": 'Eine Regel pro Zeile „alt = neu“ – gespeichert wird nach {path}',
    "gui.rules.status.template": "Vorlage eingesetzt – noch nicht gespeichert",
    "gui.rules.status.builtin_present": "Die eingebauten Regeln sind bereits enthalten",
    "gui.rules.status.builtin_added": "Übersicht der eingebauten Regeln angehängt – noch nicht gespeichert",
    "gui.rules.status.saved_warnings": "Gespeichert, {count} Warnungen – siehe Protokoll",
    "gui.rules.status.saved": "Gespeichert ✓  ({summary})",
    "gui.rules.status.none": "keine Einträge",
    "gui.rules.confirm_template.title": "Vorlage einfügen?",
    "gui.rules.confirm_template.text": ("Der Text im Feld wird durch die Vorlage ersetzt – die Datei "
                                        "selbst bleibt unverändert, bis du speicherst."),
    "gui.language.de": "DE",
    "gui.language.en": "EN",
    "gui.dialog.busy.title": "Bitte warten",
    "gui.dialog.busy.text": "Es läuft noch ein Auftrag. Bitte warten, bis er fertig ist.",

    # Karten, Bereiche und Ergebnisansicht
    "gui.button.settings": "Einstellungen",
    "gui.button.choose_folder": "Ordner auswählen",
    "gui.button.refresh": "Aktualisieren",
    "gui.button.preview_create": "Vorschau erstellen",
    "gui.button.details": "Details anzeigen",
    "gui.button.back": "Zurück",
    "gui.button.close": "Schließen",
    "gui.button.open_backup": "Backup öffnen",
    "gui.section.music_folder": "Musikordner",
    "gui.section.options": "Optionen",
    "gui.section.active_rules": "Aktive Bereinigung",
    "gui.section.preview": "Vorschau",
    "gui.section.result": "Ergebnis",
    "gui.label.last_entries": "Letzte Einträge",
    "gui.stats.unknown": "Noch kein Ordner analysiert",
    "gui.stats.scanning": "Dateien werden gezählt …",
    "gui.stats.press_refresh": "„Aktualisieren“ zählt die Dateien",
    "gui.stats.summary": "{files} Audiodateien · {albums} Alben · {artists} Künstler",
    "gui.pill.artist": "Künstler {count}",
    "gui.pill.regex": "Muster {count}",
    "gui.pill.genre": "Genre {count}",
    "gui.pill.protected": "Geschützt {count}",
    "gui.pill.builtin": "Korrekturen {count}",
    "gui.pill.none": "Keine eigenen Regeln",
    "gui.pill.warnings": "{count} Warnungen",
    "gui.preview.none": "Noch keine Vorschau. „Vorschau erstellen“ zeigt, was sich ändert.",
    "gui.preview.run_first": "Erst eine Vorschau erstellen",
    "gui.preview.running": "Vorschau wird erstellt …",
    "gui.preview.stale": "Vorschau ist veraltet, bitte neu erstellen",
    "gui.preview.unchanged": "Nichts zu tun – alles ist bereits korrekt.",
    "gui.preview.summary_tags": "{changes} Änderungen in {files} Dateien",
    "gui.preview.summary_files": "{files} Dateien betroffen",
    "gui.preview.more": "+{count} weitere",
    "gui.field.artist": "Künstler",
    "gui.field.album_artist": "Album-Künstler",
    "gui.field.title": "Titel",
    "gui.field.album": "Album",
    "gui.field.genre": "Genre",
    "gui.field.file": "Datei",
    "gui.field.folder": "Ordner",
    "gui.result.changed": "geändert",
    "gui.result.planned": "Änderungen geplant",
    "gui.result.analysed": "Dateien analysiert",
    "gui.result.skipped": "übersprungen",
    "gui.result.errors": "Fehler",
    "gui.result.tags_changed": "Tags bereinigt",
    "gui.result.renamed": "Dateien umbenannt",
    "gui.result.sorted": "Dateien sortiert",
    "gui.status.scanning": "Analysiere Dateien …",
    "gui.status.percent": "{current} / {total} · {percent} %",
    "gui.log.ffprobe_missing": "  Hinweis: ffprobe fehlt – Tags werden langsamer gelesen (ffmpeg installieren).",
    "gui.settings.title": "Einstellungen",
    "gui.settings.heading": "Einstellungen",
    "gui.settings.backend": "Tag-Backend",
    "gui.settings.backend_hint": ("Tags nutzen das beste verfügbare Backend – hier gibt es nichts "
                                  "einzustellen."),
    "gui.settings.language": "Sprache",
    "gui.settings.language_hint": "Steht in settings.ini und gilt wieder beim nächsten Start.",

    # Rückgängig machen (Journal)
    "cli.restore.help": "Änderungen eines früheren Laufs rückgängig machen",
    "cli.restore.journal": "Journal, das zurückgenommen wird (Standard: das neueste)",
    "cli.restore.list": "die vorhandenen Journale auflisten und sonst nichts tun",
    "cli.restore.apply": "die Änderungen wirklich zurücknehmen",
    "cli.restore.backup": "die Dateien vor dem Rückgängigmachen in einen Backup-Ordner kopieren",
    "cli.restore.keep_copies": ("die Kopien eines Kopier-Laufs liegen lassen "
                                "(Standard: sie werden gelöscht)"),
    "task.title.restore": "MUSIK - RÜCKGÄNGIG (Wiederherstellung aus dem Journal)",
    "task.label.journal": "  Journal: {value}",
    "task.label.events": "  Ereignisse: {value}",
    "task.progress.restore": "wird zurückgenommen …",
    "restore.error.no_journal": "  FEHLER: kein Journal gefunden (nichts rückgängig zu machen).",
    "restore.error.schema": ("  FEHLER: Dieses Journal stammt von einem neueren Sortiton "
                             "({version}; diese Version kennt {known})."),
    "restore.nothing": "  Das Journal enthält keine Änderungen.",
    "restore.undoing": "  {count} Änderungen werden zurückgenommen …",
    "restore.remove_copy": "  Kopie entfernen: {name}",
    "restore.ok.tags": "  OK Tags    : {name}",
    "restore.ok.copy": "  OK gelöscht: {name}",
    "restore.ok.move": "  OK zurück  : {name}",
    "restore.done": ("  Fertig. Zurückgenommen: {changed}   Übersprungen: {skipped}   "
                     "({total} Ereignisse)"),
    "restore.skip.failed": "  übersprungen (der Lauf war fehlerhaft): {name}",
    "restore.skip.missing": "  übersprungen (Datei ist weg): {name}",
    "restore.skip.exists": "  übersprungen (der alte Name ist wieder belegt): {name}",
    "restore.skip.keep_copy": "  behalten (--keep-copies): {name}",
    "restore.skip.only_copy": ("  behalten (das Original ist weg – es ist die letzte Kopie): "
                               "{name}"),
    "restore.skip.unknown": "  übersprungen (nicht rücknehmbar): {op}",
    "restore.list.title": "  Journale im Log-Ordner: {count}",
    "restore.list.none": "  Noch keine Journale ({path}).",
    "restore.list.empty": "keine Änderungen",
    "restore.list.entry": "  {name}   {start}   {summary}",
    "gui.button.undo": "Letzten Lauf rückgängig …",
    "gui.job.restore": "Rückgängig",
    "gui.restore.title": "Lauf rückgängig machen",
    "gui.restore.heading": "Die Änderungen eines früheren Laufs zurücknehmen",
    "gui.restore.journals": "Journale",
    "gui.restore.none": "Im Log-Ordner wurde kein Journal gefunden.",
    "gui.restore.pick": "Links ein Journal auswählen.",
    "gui.restore.summary": "{total} Ereignisse: {parts}",
    "gui.restore.note": ("Zurückgenommen werden nur die Änderungen aus diesem Journal. "
                          "Gelöschte Kopien bleiben weg."),
    "gui.restore.empty": "Dieses Journal enthält nichts, was sich zurücknehmen lässt.",
    "gui.restore.run": "Jetzt zurücknehmen",
    "gui.restore.more": "… und {count} weitere",
    "gui.restore.op.tags": "Tags",
    "gui.restore.op.move": "Zurück",
    "gui.restore.op.copy": "Kopie löschen",
    "gui.restore.op.failed": "Fehlgeschlagen",
    "gui.restore.op.other": "Sonstiges",
    "gui.confirm.restore.title": "Wirklich zurücknehmen?",
    "gui.confirm.restore.text": ("{changes} Änderungen dieses Laufs werden "
                                  "zurückgenommen. Gelöschte Kopien kommen nicht zurück."),
    "gui.confirm.keep_copies": "Die Kopien eines Kopier-Laufs behalten",
}

_CATALOGS: dict[str, dict[str, str]] = {"en": _EN, "de": _DE}

_language = DEFAULT_LANGUAGE


def available() -> tuple[str, ...]:
    """Language codes that can be selected."""
    return LANGUAGES


def get_language() -> str:
    """Currently active language code."""
    return _language


def set_language(code: str) -> str:
    """Activate a language; unknown codes keep the current one."""
    global _language
    code = (code or "").strip().lower()
    if code in _CATALOGS:
        _language = code
    return _language


def t(key: str, **fmt: object) -> str:
    """Translate ``key``; falls back to English, then to the key itself."""
    text = _CATALOGS.get(_language, {}).get(key)
    if text is None:
        text = _EN.get(key)
    if text is None:
        return key
    if fmt:
        try:
            return text.format(**fmt)
        except (KeyError, IndexError, ValueError):
            return text
    return text


def catalog(code: str) -> dict[str, str]:
    """Raw translation table for ``code`` (empty if unknown)."""
    return dict(_CATALOGS.get(code, {}))
