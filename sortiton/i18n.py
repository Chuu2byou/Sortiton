"""Translations (English / German)."""

from __future__ import annotations

LANGUAGES: tuple[str, ...] = ("en", "de")
DEFAULT_LANGUAGE = "en"

_EN: dict[str, str] = {
    "cli.description": "Clean tags, rename and sort a music library. Only --apply writes.",
    "cli.tags.help": "Clean tags (artist, album artist, title, album, genre)",
    "cli.tags.folder": "music folder (recursive)",
    "cli.tags.target": "optional target folder to sort into",
    "cli.tags.move": "move to target instead of copy",
    "cli.tags.apply": "write the changes",
    "cli.rename.help": "Rename files from their tags",
    "cli.rename.folder": "music folder (recursive)",
    "cli.rename.target": "optional target folder to sort into",
    "cli.rename.pattern": 'name pattern (default: "%%artist%% - %%title%%")',
    "cli.rename.move": "move to target instead of copy",
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
    "cli.all.fetch_url": "download this URL with yt-dlp before the rest (needs --fetch-confirmed)",
    "cli.all.fetch_confirmed": "confirm that download inside --all (never fetches without this)",
    "cli.rules.help": "Show or create your own rules (my_rules.ini)",
    "cli.rules.template": "write the template if the file does not exist yet",
    "cli.rules.builtin": "print an overview of all built-in rules",
    "journal.error.open": ("  ERROR: the journal could not be created - no file "
                           "was changed, because the run could not be undone."),
    "journal.error.write": ("  WARNING: the journal could not be written ({error}) - "
                            "this run may not be fully undoable."),
    "cli.log_file": "  Log file: {path}",
    "cli.scan.help": "count files, albums and artists (nothing is changed)",
    "cli.scan.folder": "music folder (recursive)",
    "cli.quiet": "suppress the progress line on stderr",
    "cli.export.help": "Read a music folder and write reports for an LLM (read only)",
    "cli.export.folder": "music folder (recursive)",
    "cli.export.output": "output folder (default: a timestamped folder under the export directory)",
    "gui.export.output": "Output folder (leave empty to create a timestamped folder under: {path})",
    "cli.export.chunk": "characters per tracks_partNN.tsv (default: 60000)",
    "cli.export.examples": "examples per report section (default: 40)",
    "cli.export.jsonl": "also write alle_tags.jsonl with all tags",
    "cli.export.check_case": "flag upper/lower case differences only",
    "cli.export.fingerprint": "compare audio fingerprints (needs fpcalc)",
    "cli.export.fp_seconds": "seconds per fingerprint (default: 120)",
    "cli.export.fp_threshold": "similarity threshold 0.0-1.0 (default: 0.70)",
    "cli.export.threads": "parallel readers (default: number of CPUs)",
    "cli.tags.backup": "copy the files into a backup folder before writing",
    "cli.all.backup": "copy the files into a backup folder before writing",
    "cli.rule_warning": "  RULE WARNING: {text}",
    "cli.custom_rules": "  Custom rules: {summary}  ({file})",
    "cli.cancelled": "  Cancelled.",

    "external.error.missing": "  ERROR: missing tool(s): {tools}",
    "external.hint.ffprobe": ("  ffprobe is missing - install ffmpeg "
                              "(Debian/Ubuntu: sudo apt install ffmpeg | "
                              "Fedora: sudo dnf install ffmpeg | "
                              "Arch: sudo pacman -S ffmpeg)."),
    "external.hint.ffmpeg": ("  ffmpeg is missing - install ffmpeg "
                             "(Debian/Ubuntu: sudo apt install ffmpeg | "
                             "Fedora: sudo dnf install ffmpeg | "
                             "Arch: sudo pacman -S ffmpeg)."),
    "external.hint.fpcalc": ("  fpcalc is missing - Debian/Ubuntu: "
                             "sudo apt install libchromaprint-tools | "
                             "Fedora: sudo dnf install chromaprint-tools | "
                             "Arch: sudo pacman -S chromaprint."),
    "external.hint.mutagen": "  mutagen is missing - run: pip install mutagen.",
    "external.hint.ytdlp": "  yt-dlp is missing - install it, e.g.: pip install yt-dlp.",

    "export.title": "EXPORT - reports for an LLM (read only)",
    "export.done": "  Done: {files} file(s) -> {outdir}",
    "export.cancelled": "  Cancelled - partial output kept in {outdir}",
    "export.fp.cache": "  Fingerprints: {cached} from cache, {todo} to compute",
    "export.fp.failed": ("  Note: {count} file(s) without fingerprint, "
                         "details in fpcalc_fehler.log"),
    "export.error.threshold": "  ERROR: --fp-threshold must be between 0.0 and 1.0.",
    "export.error.minimum": "  ERROR: {option} must be at least {minimum}.",
    "export.error.outdir": "  ERROR: cannot create the output folder {path}: {error}",
    "export.error.no_files": "  ERROR: no audio files found.",
    "export.error.write": "  ERROR: cannot write into {path}: {error}",
    "cli.export.report_lang": "report language (default: the interface language)",
    "export.fp.progress": "computing …",

    "fixes.title": "FIXES - single tag corrections from a CSV",
    "fixes.label.csv": "  CSV: {value}",
    "fixes.label.rows": "  Rows: {value}",
    "fixes.writing": "  Writing {count} correction(s) …",
    "fixes.done": "  Done: {changed} changed, {skipped} skipped of {total} row(s)",
    "fixes.hint.apply": "  Preview only - run again with --apply to write.",
    "fixes.warn.empty": "    note: an empty value deletes the '{field}' field",
    "fixes.skip.changed": ("  line {line}: {path} [{field}] - value changed "
                           "(expected '{expected}', found '{current}'), skipped"),
    "fixes.row_error": "  line {line}: rejected - {reason}",
    "fixes.error.csv": "  ERROR: CSV file not found: {path}",
    "fixes.error.read": "  ERROR: cannot read {path}: {error}",
    "fixes.error.no_rows": "  ERROR: no usable rows in {path}.",
    "fixes.error.columns": "expected 4 columns (path;field;old;new), found {count}",
    "fixes.error.path": "missing path",
    "fixes.error.root_required": "relative path needs --root",
    "fixes.error.outside_root": "path is outside --root",
    "fixes.error.extension": "not an audio file: '{path}'",
    "fixes.error.missing_file": "file not found: '{path}'",
    "fixes.error.field": "unknown field '{field}'",
    "fixes.error.value": "invalid value '{value}' for field '{field}'",
    "fixes.error.duplicate": "duplicate row for '{path}' field '{field}'",
    "fixes.error.unreadable": "cannot read tags of '{path}'",
    "cli.fixes.help": "Apply single tag corrections from a CSV (path;field;old;new)",
    "cli.fixes.file": "CSV file with the corrections",
    "cli.fixes.root": "root folder the CSV paths are relative to",
    "cli.fixes.apply": "write the corrections",
    "cli.fixes.backup": "copy the files into a backup folder before writing",

    "fetch.title": "FETCH - download audio with yt-dlp",
    "fetch.error.url": "  ERROR: no URL given.",
    "fetch.error.url_invalid": "  ERROR: not a usable URL: {url}",
    "fetch.error.preview": "  ERROR: the yt-dlp preview failed: {detail}",
    "fetch.error.empty": "  ERROR: yt-dlp found nothing to download.",
    "fetch.error.download": "  ERROR: the download failed: {detail}",
    "fetch.error.exit": "  ERROR: yt-dlp exited with code {rc}.",
    "fetch.preview.header": "  Preview: {count} entry/entries (nothing downloaded).",
    "fetch.preview.entry": "    {title}  ({duration})",
    "fetch.preview.only": "  Preview only. Use --apply --confirm to download.",
    "fetch.apply.needs_confirm": "  ERROR: refusing to download without --confirm.",
    "fetch.download.start": "  Downloading {count} entry/entries with yt-dlp ...",
    "fetch.download.file": "  Saved: {path}",
    "fetch.download.done": "  Done: {files} file(s) downloaded.",
    "fetch.progress": "downloading",
    "cli.fetch.help": "Download a track or playlist as audio with yt-dlp (needs --confirm)",
    "cli.fetch.url": "URL of the video or playlist to download",
    "cli.fetch.target": "folder the downloaded audio is written to",
    "cli.fetch.audio_format": "audio format: mp3, m4a, opus or flac (default: mp3)",
    "cli.fetch.playlist": "download the whole playlist if the URL is one",
    "cli.fetch.no_archive": "do not use the download archive (re-download everything)",
    "cli.fetch.apply": "download (needs --confirm as well)",
    "cli.fetch.confirm": "confirm the download (never downloads without this)",

    "export.report.summary.title": "# Music folder summary",
    "export.report.summary.folder": "- Folder: `{root}`",
    "export.report.summary.created": "- Created: {date}",
    "export.report.summary.files": "- Files: **{n}** (read errors: {errors})",
    "export.report.summary.size": "- Total size: {gb:.2f} GB",
    "export.report.summary.duration": "- Total duration: {hours:.1f} hours",
    "export.report.summary.loose": ("- Loose files directly in the root folder "
                                    "(unsorted): {count}"),
    "export.report.summary.warning": ("> [!WARNING]\n"
                                      "> No file could be read successfully."),
    "export.report.formats.title": "## Formats",
    "export.report.formats.bitrate": ("- Bitrate {codec}: median {median:.0f} kbps, "
                                      "below {threshold} kbps: {below} of {total}"),
    "export.report.formats.no_cover": "- Without cover: {count}",
    "export.report.tags.title": ("## Missing tags (number of files; `disc` is usually "
                                 "missing for single CDs)"),
    "export.report.tags.entry": "- {field}: {count} ({percent:.1f} %)",
    "export.report.tags.disc": ("- disc: {count} ({percent:.1f} %; usually fine for "
                                "single CDs)"),
    "export.report.folders.title": "## Top folders (files)",
    "export.report.folders.root": "(root)",
    "export.report.genres.title": "## Genres (all, with count)",
    "export.report.dates.title": "## Date formats in the year tag",
    "export.report.dates.entry": "- {format}: {count}{example}",
    "export.report.dates.example": " (e.g. `{path}`)",
    "export.report.decades.title": "## Decades",
    "export.report.decades.entry": "- {prefix}0s: {count}",
    "export.report.artists.title": "## Top artists",
    "export.report.tracks.title": "## Track number quality per multi-track album",
    "export.report.tracks.checked": "- Multi-track albums/folders checked: {count}",
    "export.report.tracks.missing_multi": ("- Files with a missing track tag inside these "
                                           "multi-track albums: {count}"),
    "export.report.tracks.albums_missing": ("- Albums with at least one missing track tag: "
                                            "{count}"),
    "export.report.tracks.all_missing": ("- Albums where all track tags are missing: "
                                         "{count}"),
    "export.report.tracks.gap_albums": "- Albums with reliable track number gaps: {count}",
    "export.report.tracks.sparse": ("- Other albums with very sparse/unclear number "
                                    "sequences: {count}"),
    "export.report.tracks.incomplete.title": "### Missing track tags ({count})",
    "export.report.tracks.incomplete.note": ("_A missing track tag is not automatically "
                                             "counted as a missing track._"),
    "export.report.tracks.incomplete.all": ("{label} / `{album}`: ALL {total} track tags "
                                            "are missing"),
    "export.report.tracks.incomplete.some": ("{label} / `{album}`: {missing} of {total} "
                                             "track tags are missing"),
    "export.report.tracks.gaps.title": "### Reliable track number gaps ({count})",
    "export.report.tracks.gaps.note": ("_Only dense sequences from 1 or explicit totals "
                                       "(e.g. 03/12) count as a gap._"),
    "export.report.tracks.gaps.entry": "{label} / `{album}`: reliable gaps -> {gaps}",
    "export.report.tracks.gaps.more": ", ... ({count} gaps)",
    "export.report.tracks.no_album": "(no album)",
    "export.report.anomalies.title": "# Automatically found anomalies",
    "export.report.anomalies.note": ("_Hints only, no proven errors. The comparison "
                                     "ignores case, accents, spaces and hyphen kinds._"),
    "export.report.variants.title": "## {title} ({count})",
    "export.report.variants.artist": "Artist: spelling differs only",
    "export.report.variants.albumartist": "Album artist: spelling differs only",
    "export.report.variants.album": "Album (per artist): spelling differs only",
    "export.report.variants.genre": "Genre: spelling differs only",
    "export.report.folder_artist.title": ("## Top folder does not match the album "
                                          "artist/artist tag ({count} pairs)"),
    "export.report.folder_artist.note": ("_Already factored out: truncated folder names "
                                         "(from {trunc} characters accepted as the start "
                                         "of the tag) and folders that match one of "
                                         "several artists in the tag ({skipped} files "
                                         "affected, folder and album check together)._"),
    "export.report.folder_album.title": ("## Album folder does not match the album tag "
                                         "({count} pairs)"),
    "export.report.folder_tag": 'Folder "{folder}" <-> tag "{tag}" ({count}x)',
    "export.report.style.title": "## Style problems in tags ({count} files)",
    "export.report.style.junk": "junk in {field} ('{match}')",
    "export.report.style.double_space": "double spaces in {field}",
    "export.report.style.track_in_title": "track number in the title tag",
    "export.report.style.underscores": "underscores instead of spaces in the title",
    "export.report.style.all_caps": "{field} all upper case",
    "export.report.style.all_lower": "{field} all lower case",
    "export.report.field.title": "title",
    "export.report.field.artist": "artist",
    "export.report.field.album": "album",
    "export.report.field.albumartist": "album artist",
    "export.report.field.genre": "genre",
    "export.report.filename.title": ("## File name does not contain the title tag "
                                     "({count}; `: / ? * |` -> `_` and truncated names are "
                                     "already factored out)"),
    "export.report.filename.entry": '`{path}` (title tag: "{title}")',
    "export.report.duplicates.title": ("## Possible duplicates (same artist+title) "
                                       "({count} groups)"),
    "export.report.inconsistent.title": ("## Folders with inconsistent album/album "
                                         "artist/genre ({count}; root excluded)"),
    "export.report.dup_tracks.title": ("## Duplicate track numbers in the same folder+album "
                                       "({count})"),
    "export.report.samplers.title": ("## Suspected samplers without an explicit album "
                                     "artist ({count})"),
    "export.report.sampler.missing_albumartist": ("`{dir}` ({artists} artists, album "
                                                  "artist missing for {missing}/{total})"),
    "export.report.sampler.various": ("`{dir}` ({artists} artists, album artist always "
                                      "\"Various Artists\")"),
    "export.report.errors.title": "## Read errors ({count})",
    "export.report.unreadable": "unreadable",
    "export.report.list.empty": "- (none)",
    "export.report.list.more": "- ... ({count} more)",
    "export.report.date.empty": "(empty)",
    "export.report.date.year": "YYYY",
    "export.report.date.ymd": "YYYY-MM-DD",
    "export.report.date.ymd_dot": "YYYY.MM.DD",
    "export.report.date.ym": "YYYY-MM",
    "export.report.date.slash_ymd": "YYYY/MM/DD",
    "export.report.date.slash_ym": "YYYY/MM",
    "export.report.date.dmy": "DD.MM.YYYY",
    "export.report.date.iso": "ISO timestamp",
    "export.report.date.range": "YYYY-YYYY (range)",
    "export.report.date.other": "free text / other",
    "export.report.fp.title": ("## Audio fingerprint duplicates ({groups} groups; "
                               "{n_fp}/{n_total} files had a fingerprint; base threshold "
                               "{threshold:.0%})"),
    "export.report.fp.note": ("_The rating combines audio similarity, artist+title, album, "
                              "duration and a duplicate marker in the file name. A high "
                              "fingerprint value alone does not prove an identical "
                              "recording. Versions, covers, instrumentals, edits and "
                              "different language versions can reach high similarity too. "
                              "A technical quality hint names a variant with a higher "
                              "bitrate for likely duplicates but never deletes or prefers "
                              "anything automatically._"),
    "export.report.fp.bucket.title": "### {title} ({count} groups)",
    "export.report.fp.bucket.sehr_wahrscheinlich": "Very likely a real duplicate",
    "export.report.fp.bucket.wahrscheinlich": "Likely duplicate",
    "export.report.fp.bucket.pruefen": "Check - could be another version",
    "export.report.fp.bucket.aehnlich": "Similar recording / possible variant",
    "export.report.fp.flag.same_identity": "artist+title equal",
    "export.report.fp.flag.diff_identity": "artist/title differ",
    "export.report.fp.flag.same_duration": "duration similar",
    "export.report.fp.flag.diff_duration": "duration differs",
    "export.report.fp.flag.same_album": "album equal",
    "export.report.fp.flag.marker": "duplicate marker in the file name",
    "export.report.fp.quality_hint": "; higher bitrate: `{path}` ({kbps}k)",
    "export.prompt": """\
# Task: check a music library and suggest improvements

You get the tag export of my music folder:
- `01_zusammenfassung.md` - summary and statistics
- `02_auffaelligkeiten.md` - automatically found anomalies
- `03_duplikate.md` - audio fingerprint duplicates (if present)
- `tracks_part*.tsv` - one line per file (tab separated): {cols}
  (`path` is relative to the music folder, `sek` = duration in seconds, `cover` = j/n;
  several values of one tag are separated by " | ")

My sorting software (Sortiton) works with rules in a `my_rules.ini`.

## What I want from you
1. **Overview:** What is the state of the library? What are the biggest issues?
2. **Rules for `my_rules.ini`** - for recurring things (spellings of artists,
   unify genres), exactly in this format:
   ```
   [Artist]        ; Wrong = Right
   [Artist Regex]  ; Regular expression = replacement
   [Genre]         ; Wrong = Right   (empty right = delete genre)
   [Protected]     ; Names that are never split/changed (e.g. "Simon & Garfunkel")
   ```
3. **Single corrections** for files a rule does not cover, as a semicolon CSV:
   `path;feld;alt;neu` (feld = artist, albumartist, album, title, track, disc, year, genre)
4. **Folder/file names:** Where does the folder structure not match the tags?
   Suggest a consistent scheme.
5. **Duplicates, samplers, missing covers/tags and track numbers** briefly prioritized.

## Rules for you
- Do not invent anything. Only suggest years, albums or the like when they clearly
  follow from the data; otherwise mark them as a question.
- Do NOT touch upper/lower case: UPPERCASE, lowercase-only and other stylizations
  (e.g. "Ado - KIRA", "amnesia", "deadmau5") are usually the original spelling and correct.
  Report only cases where the SAME album/artist appears in several spellings.
- Special characters in file names were often replaced by the file system with `_` (`: / ? * |`) -
  that is not an error. `(2)` in a file name hints at a duplicate file.
- Genres can contain countries, languages, fandoms, platform categories (e.g. "Music",
  "Film & Animation") or fun tags. Suggest a small, sensible list of real genres
  and ask me about borderline cases (e.g. "Hololive", "Japanese") whether I want to
  keep them. You may correct misspelled abbreviations (EDM, R&B, IDM, UK ...).
- Audio fingerprint groups are graded by similarity. The same recording (copy) and a related
  version (instrumental, cover, another language, edit, short version) are NOT the same.
  Keep versions, merge real copies and name the better file (higher bitrate, full duration,
  correct folder) when doing so.
- If a folder name differs from the tags, tell me whether the folder or the tag
  should be adjusted.
- Tags that match the original are correct - "anomalies" of the summary are only
  hints, not errors. Check yourself whether something is really wrong.
- When unsure, ask rather than guess.
- Work through the parts in order; output only the *changes* per part.
- At the end: one merged, deduplicated `my_rules.ini`.

There are {n} file(s) in {parts} part(s). Start with the summary.
""",

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

    "file.error.no_free_name": "No free target name found for: {path}",

    "task.error.folder": "  ERROR: Folder not found: {path}",
    "task.error.source": "  ERROR: Source folder not found: {path}",
    "task.error.target_required": "  ERROR: --move requires a target folder.",
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
    "task.error.unreadable": "  SKIPPED (no reader could read it): {name}",
    "task.progress.backup": "backing up …",
    "task.backup.done": "  Backup of {count} file(s): {path}",
    "task.backup.failed": "  Backup folder could not be created ({path}): {error}",
    "task.backup.prune_failed": "  Could not remove old backup '{path}': {error}",
    "task.backup.incomplete": ("  Backup is incomplete; no file was changed. "
                               "Partial backup: {path}"),
    "task.backup.aborted": "  Run stopped: the requested backup is not complete.",
    "task.backup.file_error": "  BACKUP FAILED '{name}': {error}",
    "task.scan.done": "  {files} files · {albums} albums · {artists} artists",
    "task.tags.done": "  Done. Files changed: {changed} / {total}",
    "task.rename.done": "  Renamed: {renamed}   Already correct/skipped: {skipped}",
    "task.sort.done": "  Processed: {done} / {total}   Skipped: {skipped}",
    "task.placed": "  Placed: {count}",
    "task.error.count": "  Errors: {count}",
    "task.hint.apply": "  --> Append --apply to write.",
    "task.hint.apply_run": "  --> Append --apply to run it.",
    "task.step": "#  {title}",
    "task.aborted": "  ABORTED in '{title}' (rc={rc}).",
    "task.cancelled": "  Cancelled.",
    "task.all.done": "  ALL-IN-ONE finished. ({mode})",
    "task.mode.applied": "applied",
    "task.mode.preview": "preview",
    "task.step.fetch": "Fetch audio",
    "task.step.tags": "Clean tags",
    "task.step.rename": "Rename",
    "task.step.sort": "Sort",
    "task.step.label": "{index}/{total} · {title}",

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

    "rules.warn.read": "Rule file could not be read ({file}): {error}",
    "rules.warn.invalid": "Rule file is invalid ({file}): {error}",
    "rules.warn.artist_no_equals": 'Artist rule "{rule}" without "=" - skipped (old = new).',
    "rules.warn.regex_no_equals": 'Regex rule "{rule}" without "=" - skipped (pattern = replacement).',
    "rules.warn.regex_invalid": 'Regex rule "{rule}" is invalid - skipped: {error}',
    "rules.warn.regex_too_long": 'Regex rule "{rule}" is too long - skipped.',
    "rules.warn.regex_unsafe": ('Regex rule "{rule}" contains nested/alternating '
                                'quantifiers (ReDoS risk) - skipped.'),
    "rules.warn.genre_no_equals": 'Genre rule "{rule}" without "=" - skipped (old = new).',
    "rules.summary.artists": "{count} artist",
    "rules.summary.artists_plural": "{count} artists",
    "rules.summary.regex": "{count} regex",
    "rules.summary.genre": "{count} genre",
    "rules.summary.protected": "{count} protected",

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
    "rules.overview.artist_sub3": "#   regex rules only run on values up to 512 characters (ReDoS guard).",
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

    "gui.window.title": "Sortiton",
    "gui.button.custom_rules": "Custom Rules …",
    "gui.button.paste_llm": "Paste LLM answer",
    "gui.chip.tool_ok": "{tool} ✓ {version}",
    "gui.chip.tool_ok_noversion": "{tool} ✓",
    "gui.chip.tool_missing": "{tool} missing",
    "gui.tab.tags": "Clean tags",
    "gui.tab.rename": "Rename",
    "gui.tab.sort": "Sort",
    "gui.tab.all": "Apply all",
    "gui.tab.tools": "Tools",
    "gui.button.preview": "Preview",
    "gui.button.change": "Change…",
    "gui.button.write_tags": "Write tags",
    "gui.button.rename": "Rename",
    "gui.button.sort": "Sort",
    "gui.button.run_all": "Run all",
    "gui.button.run_tool": "Run",
    "gui.button.write_fixes": "Write corrections",
    "gui.button.copy_prompt": "Copy prompt",
    "gui.button.open_export": "Open report",
    "gui.button.clear": "Clear",
    "gui.button.open_folder": "Open folder",
    "gui.button.open_logs": "Open logs",
    "gui.button.insert_template": "Insert template",
    "gui.button.builtin_rules": "Built-in rules",
    "gui.button.system_editor": "System editor",
    "gui.button.cancel": "Cancel",
    "gui.button.save": "Save",
    "gui.button.apply_rules": "Apply",
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
    "gui.hint.export": ("Read-only: reads the folder and writes the reports. "
                        "Nothing in the library is changed."),
    "gui.hint.fixes": ("Applies single tag corrections from a CSV (the export "
                       "prompt asks for exactly this shape). Only rows whose "
                       "current value still matches are written."),
    "gui.hint.rename": ("Renames files from their tags. The preview shows the new "
                        "names first - nothing is changed before “Rename”."),
    "gui.hint.fetch": ("Downloads audio with yt-dlp. Only download content you "
                       "have the rights to."),
    "gui.hint.tools": ("Helper tools that run on their own: export reports, apply "
                       "corrections from a CSV, or fetch audio."),
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
    "gui.confirm.tools.title": "Really write the corrections?",
    "gui.confirm.tools.text": ("{changes} corrections from {files} CSV row(s) will "
                               "be written to the audio files."),
    "gui.confirm.fetch.title": "Really download?",
    "gui.confirm.fetch.text": ("yt-dlp will download the URL and write the audio "
                               "into the chosen folder."),
    "gui.confirm.fetch.note": "Only download content you have the rights to.",
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
    "gui.dialog.file_not_found.title": "File not found",
    "gui.dialog.file_not_found.text": "This file does not exist:\n{path}",
    "gui.dialog.save_failed.title": "Saving failed",
    "gui.dialog.save_failed.text": "The rule file could not be written:\n\n{error}",
    "gui.status.ready": "ready",
    "gui.status.running": "running…",
    "gui.status.failed": "failed (rc={rc})",
    "gui.status.cancelled": "cancelled",
    "gui.status.cancelling": "cancelling - closing when done",
    "gui.status.progress": "{current} / {total} · {text}",
    "gui.job.tags": "Tag cleanup",
    "gui.job.rename": "Rename",
    "gui.job.sort": "Sort",
    "gui.job.all": "Apply all",
    "gui.job.export": "Export reports",
    "gui.job.fixes": "Apply CSV corrections",
    "gui.job.fetch": "Fetch audio",
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
    "gui.rules.status.prefilled": "Prefilled from the LLM answer - not saved yet",
    "gui.rules.confirm_replace.title": "Replace the editor content?",
    "gui.rules.confirm_replace.text": ("The editor already contains unsaved text. "
                                       "Replace it with the LLM block?"),
    "gui.rules.confirm_template.title": "Insert template?",
    "gui.rules.confirm_template.text": ("The text in the field will be replaced by the template - "
                                        "the file itself stays unchanged until you save."),
    "gui.llm.title": "Paste LLM answer",
    "gui.llm.hint": ("Paste the LLM's answer here. Its first ```ini block is used - "
                     "without one the whole text. Nothing is saved automatically; the "
                     "rules editor opens pre-filled so you can review it."),
    "gui.llm.status.empty": "Nothing pasted yet",
    "gui.llm.status.ok": "No warnings - opening the rules editor",
    "gui.llm.status.warnings": "{count} warning(s) - see the log; opening the rules editor",
    "gui.language.de": "DE",
    "gui.language.en": "EN",
    "gui.dialog.busy.title": "Please wait",
    "gui.dialog.busy.text": "A task is still running. Wait until it is done.",
    "gui.dialog.preview_stale.title": "Preview needed",
    "gui.dialog.preview_stale.text": ("The inputs changed or the last run already "
                                      "wrote its changes. Create a new preview "
                                      "before writing."),
    "gui.dialog.force_close.title": "Close anyway?",
    "gui.dialog.force_close.text": ("The task is still running. Closing now can "
                                    "interrupt a file in the middle of a write. "
                                    "Close anyway?"),
    "gui.dialog.filetype.csv": "CSV / text",
    "gui.dialog.filetype.all": "All files",
    "gui.dialog.close.title": "A task is still running",
    "gui.dialog.close.text": ("A task is still running. Cancel it and close the window "
                              "when it has stopped?"),

    "gui.button.settings": "Settings",
    "gui.button.choose_folder": "Choose folder",
    "gui.button.choose_file": "Choose file …",
    "gui.button.refresh": "Refresh",
    "gui.button.preview_create": "Create preview",
    "gui.button.details": "Show details",
    "gui.button.back": "Back",
    "gui.button.close": "Close",
    "gui.button.open_backup": "Open backup",
    "gui.button.fine_tuning": "Fine-tuning …",
    "gui.section.music_folder": "Music folder",
    "gui.section.folders": "Folders",
    "gui.section.options": "Options",
    "gui.section.active_rules": "Active cleanup",
    "gui.section.preview": "Preview",
    "gui.section.result": "Result",
    "gui.result.none": "No run yet – the counters of the last run appear here.",
    "gui.choice.report_lang.ui": "Same as the interface",
    "gui.choice.report_lang.en": "English",
    "gui.choice.report_lang.de": "German",
    "gui.tool.export": "Export",
    "gui.tool.export.run": "Start export",
    "gui.tool.fixes": "Fixes",
    "gui.tool.fixes.run": "Write corrections",
    "gui.tool.fetch": "Fetch",
    "gui.tool.fetch.run": "Start download",
    "gui.tools.section.files": "Folder & files",
    "gui.tools.section.report": "Report contents",
    "gui.tools.section.download": "Download",
    "gui.tools.section.advanced": "Duplicates & speed",
    "gui.tools.badge.readonly": "read only",
    "gui.tools.badge.writes": "writes files",
    "gui.tools.readonly_note": "Reads only – nothing is changed.",
    "gui.tools.fine_tuning_hint": ("Report length, duplicate check and reader count "
                                   "are set up in the settings."),
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
    "gui.preview.summary_fetch": "{count} entry/entries found",
    "gui.preview.more": "+{count} more",
    "gui.field.artist": "Artist",
    "gui.field.album_artist": "Album artist",
    "gui.field.title": "Title",
    "gui.field.album": "Album",
    "gui.field.genre": "Genre",
    "gui.field.track": "Track",
    "gui.field.disc": "Disc",
    "gui.field.year": "Year",
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
    "gui.result.parts": "report files",
    "gui.result.duplicates": "duplicate groups",
    "gui.status.scanning": "Analysing files …",
    "gui.status.percent": "{current} / {total} · {percent} %",
    "gui.log.ffprobe_missing": "  Note: ffprobe is missing - reading tags is slower (install ffmpeg).",
    "gui.settings.title": "Settings",
    "gui.settings.heading": "Settings",
    "gui.settings.scale": "Display scale: {percent} % – SORTITON_UI_SCALE overrides it",
    "gui.settings.tools": "External tools",
    "gui.settings.tools_hint": ("Sortiton uses the best program that is available - "
                                "nothing to set up here."),
    "gui.settings.language": "Language",
    "gui.settings.language_hint": "Stored in settings.ini, applied again on the next start.",

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
    "restore.remove_download": "  remove download: {name}",
    "restore.ok.tags": "  OK tags   : {name}",
    "restore.ok.copy": "  OK deleted: {name}",
    "restore.ok.download": "  OK deleted: {name}",
    "restore.ok.move": "  OK back   : {name}",
    "restore.done": "  Done. Undone: {changed}   Skipped: {skipped}   ({total} events)",
    "restore.skip.failed": "  skipped (the run failed): {name}",
    "restore.skip.missing": "  skipped (file is gone): {name}",
    "restore.skip.exists": "  skipped (the old name is taken again): {name}",
    "restore.skip.keep_copy": "  kept (--keep-copies): {name}",
    "restore.skip.keep_download": "  kept (--keep-copies): {name}",
    "restore.skip.only_copy": ("  kept (the original is gone - this is the only copy): "
                                "{name}"),
    "restore.skip.unknown": "  skipped (cannot be undone): {op}",
    "restore.skip.changed": "  skipped (changed since the run: {fields}): {name}",
    "restore.skip.modified": "  kept (the copy differs from the original): {name}",
    "restore.error.archive": ("  ERROR: could not remove the download archive line "
                              "for {name} - the file was kept."),
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
    "gui.restore.busy": "A task is still running - the undo did not start.",
    "gui.restore.run": "Undo now",
    "gui.restore.more": "… and {count} more",
    "gui.restore.op.tags": "Tags",
    "gui.restore.op.move": "Move back",
    "gui.restore.op.copy": "Delete copy",
    "gui.restore.op.download": "Delete download",
    "gui.restore.op.failed": "Failed",
    "gui.restore.op.other": "Other",
    "gui.confirm.restore.title": "Undo now?",
    "gui.confirm.restore.text": ("{changes} changes of this run are undone. "
                                  "Deleted copies do not come back."),
    "gui.confirm.keep_copies": "Keep the copies of a copy run",
}

_DE: dict[str, str] = {
    "cli.description": "Tags bereinigen, umbenennen und eine Bibliothek sortieren. Geschrieben wird nur mit --apply.",
    "cli.tags.help": "Tags bereinigen (Künstler, Album-Künstler, Titel, Album, Genre)",
    "cli.tags.folder": "Musikordner (rekursiv)",
    "cli.tags.target": "Optionaler Zielordner zum Einsortieren",
    "cli.tags.move": "In Ziel verschieben statt kopieren",
    "cli.tags.apply": "Änderungen schreiben",
    "cli.rename.help": "Dateien aus Tags umbenennen",
    "cli.rename.folder": "Musikordner (rekursiv)",
    "cli.rename.target": "Optionaler Zielordner zum Einsortieren",
    "cli.rename.pattern": 'Namensmuster (Standard: "%%artist%% - %%title%%")',
    "cli.rename.move": "In Ziel verschieben statt kopieren",
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
    "cli.all.fetch_url": "diese URL vorab mit yt-dlp laden (braucht --fetch-confirmed)",
    "cli.all.fetch_confirmed": "den Download in --all bestätigen (lädt nie ohne diese Bestätigung)",
    "cli.rules.help": "Eigene Regeln (my_rules.ini) anzeigen/anlegen",
    "cli.rules.template": "Vorlage anlegen, falls die Datei noch fehlt",
    "cli.rules.builtin": "Übersicht aller eingebauten Regeln ausgeben",
    "journal.error.open": ("  FEHLER: Das Journal konnte nicht angelegt werden - "
                           "es wurde nichts geändert, weil sich der Lauf nicht "
                           "rückgängig machen ließe."),
    "journal.error.write": ("  WARNUNG: Das Journal konnte nicht geschrieben werden "
                            "({error}) - dieser Lauf ist möglicherweise nicht vollständig "
                            "rückgängig zu machen."),
    "cli.log_file": "  Protokoll: {path}",
    "cli.scan.help": "Dateien, Alben und Künstler zählen (ändert nichts)",
    "cli.scan.folder": "Musikordner (rekursiv)",
    "cli.quiet": "Fortschrittszeile auf stderr unterdrücken",
    "cli.export.help": "Musikordner lesen und Berichte für ein LLM schreiben (nur lesend)",
    "cli.export.folder": "Musikordner (rekursiv)",
    "cli.export.output": "Ausgabeordner (Standard: neuer Ordner mit Zeitstempel im Export-Verzeichnis)",
    "gui.export.output": "Ausgabeordner (leer = neuer Ordner mit Zeitstempel unter: {path})",
    "cli.export.chunk": "Zeichen pro tracks_partNN.tsv (Standard: 60000)",
    "cli.export.examples": "Beispiele pro Report-Abschnitt (Standard: 40)",
    "cli.export.jsonl": "zusätzlich alle_tags.jsonl mit allen Tags schreiben",
    "cli.export.check_case": "nur Groß-/Kleinschreibungs-Unterschiede melden",
    "cli.export.fingerprint": "Audio-Fingerprints vergleichen (braucht fpcalc)",
    "cli.export.fp_seconds": "Sekunden pro Fingerprint (Standard: 120)",
    "cli.export.fp_threshold": "Ähnlichkeitsschwelle 0.0-1.0 (Standard: 0.70)",
    "cli.export.threads": "parallele Leser (Standard: Anzahl der CPUs)",
    "cli.tags.backup": "Dateien vor dem Schreiben in einen Backup-Ordner kopieren",
    "cli.all.backup": "Dateien vor dem Schreiben in einen Backup-Ordner kopieren",
    "cli.rule_warning": "  REGEL-WARNUNG: {text}",
    "cli.custom_rules": "  Eigene Regeln: {summary}  ({file})",
    "cli.cancelled": "  Abgebrochen.",

    "external.error.missing": "  FEHLER: fehlende(s) Werkzeug(e): {tools}",
    "external.hint.ffprobe": ("  ffprobe fehlt - bitte ffmpeg installieren "
                              "(Debian/Ubuntu: sudo apt install ffmpeg | "
                              "Fedora: sudo dnf install ffmpeg | "
                              "Arch: sudo pacman -S ffmpeg)."),
    "external.hint.ffmpeg": ("  ffmpeg fehlt - bitte ffmpeg installieren "
                             "(Debian/Ubuntu: sudo apt install ffmpeg | "
                             "Fedora: sudo dnf install ffmpeg | "
                             "Arch: sudo pacman -S ffmpeg)."),
    "external.hint.fpcalc": ("  fpcalc fehlt - Debian/Ubuntu: "
                             "sudo apt install libchromaprint-tools | "
                             "Fedora: sudo dnf install chromaprint-tools | "
                             "Arch: sudo pacman -S chromaprint."),
    "external.hint.mutagen": "  mutagen fehlt - bitte ausführen: pip install mutagen.",
    "external.hint.ytdlp": "  yt-dlp fehlt - bitte installieren, z. B.: pip install yt-dlp.",

    "export.title": "EXPORT - Berichte für ein LLM (nur lesend)",
    "export.done": "  Fertig: {files} Datei(en) -> {outdir}",
    "export.cancelled": "  Abgebrochen - unvollständige Ausgabe bleibt in {outdir}",
    "export.fp.cache": "  Fingerprints: {cached} aus Cache, {todo} neu zu berechnen",
    "export.fp.failed": ("  Hinweis: {count} Datei(en) ohne Fingerprint, "
                         "Details in fpcalc_fehler.log"),
    "export.error.threshold": "  FEHLER: --fp-schwelle muss zwischen 0.0 und 1.0 liegen.",
    "export.error.minimum": "  FEHLER: {option} muss mindestens {minimum} sein.",
    "export.error.outdir": "  FEHLER: Ausgabeordner {path} lässt sich nicht anlegen: {error}",
    "export.error.no_files": "  FEHLER: Keine Audiodateien gefunden.",
    "export.error.write": "  FEHLER: Schreiben in {path} nicht möglich: {error}",
    "cli.export.report_lang": "Sprache der Berichte (Standard: wie die Oberfläche)",
    "export.fp.progress": "berechnen …",

    "fixes.title": "FIXES - Einzelkorrekturen aus einer CSV",
    "fixes.label.csv": "  CSV: {value}",
    "fixes.label.rows": "  Zeilen: {value}",
    "fixes.writing": "  Schreibe {count} Korrektur(en) …",
    "fixes.done": ("  Fertig: {changed} geändert, {skipped} übersprungen "
                    "von {total} Zeile(n)"),
    "fixes.hint.apply": "  Nur Vorschau - erneut mit --apply ausführen, um zu schreiben.",
    "fixes.warn.empty": "    Hinweis: ein leerer Wert löscht das Feld '{field}'",
    "fixes.skip.changed": ("  Zeile {line}: {path} [{field}] - Wert hat sich geändert "
                           "(erwartet '{expected}', gefunden '{current}'), übersprungen"),
    "fixes.row_error": "  Zeile {line}: abgelehnt - {reason}",
    "fixes.error.csv": "  FEHLER: CSV-Datei nicht gefunden: {path}",
    "fixes.error.read": "  FEHLER: {path} kann nicht gelesen werden: {error}",
    "fixes.error.no_rows": "  FEHLER: keine verwendbaren Zeilen in {path}.",
    "fixes.error.columns": "4 Spalten erwartet (path;field;old;new), {count} gefunden",
    "fixes.error.path": "Pfad fehlt",
    "fixes.error.root_required": "relativer Pfad braucht --root",
    "fixes.error.outside_root": "Pfad liegt außerhalb von --root",
    "fixes.error.extension": "keine Audiodatei: '{path}'",
    "fixes.error.missing_file": "Datei nicht gefunden: '{path}'",
    "fixes.error.field": "unbekanntes Feld '{field}'",
    "fixes.error.value": "ungültiger Wert '{value}' für Feld '{field}'",
    "fixes.error.duplicate": "doppelte Zeile für '{path}' Feld '{field}'",
    "fixes.error.unreadable": "Tags von '{path}' können nicht gelesen werden",
    "cli.fixes.help": "Einzelkorrekturen aus einer CSV anwenden (path;field;old;new)",
    "cli.fixes.file": "CSV-Datei mit den Korrekturen",
    "cli.fixes.root": "Wurzelordner, auf den sich die CSV-Pfade beziehen",
    "cli.fixes.apply": "die Korrekturen schreiben",
    "cli.fixes.backup": "Dateien vor dem Schreiben in einen Backup-Ordner kopieren",

    "fetch.title": "FETCH - Audio mit yt-dlp herunterladen",
    "fetch.error.url": "  FEHLER: keine URL angegeben.",
    "fetch.error.url_invalid": "  FEHLER: keine brauchbare URL: {url}",
    "fetch.error.preview": "  FEHLER: die yt-dlp-Vorschau ist fehlgeschlagen: {detail}",
    "fetch.error.empty": "  FEHLER: yt-dlp hat nichts zum Herunterladen gefunden.",
    "fetch.error.download": "  FEHLER: der Download ist fehlgeschlagen: {detail}",
    "fetch.error.exit": "  FEHLER: yt-dlp wurde mit Code {rc} beendet.",
    "fetch.preview.header": "  Vorschau: {count} Eintrag/Einträge (nichts geladen).",
    "fetch.preview.entry": "    {title}  ({duration})",
    "fetch.preview.only": "  Nur Vorschau. Zum Laden mit --apply --confirm erneut starten.",
    "fetch.apply.needs_confirm": "  FEHLER: ohne --confirm wird nichts geladen.",
    "fetch.download.start": "  Lade {count} Eintrag/Einträge mit yt-dlp ...",
    "fetch.download.file": "  Gespeichert: {path}",
    "fetch.download.done": "  Fertig: {files} Datei(en) geladen.",
    "fetch.progress": "lädt",
    "cli.fetch.help": ("Einen Titel oder eine Playlist als Audio mit yt-dlp laden "
                       "(braucht --confirm)"),
    "cli.fetch.url": "URL des Videos oder der Playlist",
    "cli.fetch.target": "Ordner, in den das geladene Audio geschrieben wird",
    "cli.fetch.audio_format": "Audioformat: mp3, m4a, opus oder flac (Standard: mp3)",
    "cli.fetch.playlist": "die ganze Playlist laden, wenn die URL eine ist",
    "cli.fetch.no_archive": "das Download-Archiv nicht verwenden (alles erneut laden)",
    "cli.fetch.apply": "herunterladen (zusätzlich --confirm nötig)",
    "cli.fetch.confirm": "den Download bestätigen (lädt nie ohne diese Bestätigung)",

    "export.report.summary.title": "# Zusammenfassung Musikordner",
    "export.report.summary.folder": "- Ordner: `{root}`",
    "export.report.summary.created": "- Erstellt: {date}",
    "export.report.summary.files": "- Dateien: **{n}** (Lesefehler: {errors})",
    "export.report.summary.size": "- Gesamtgröße: {gb:.2f} GB",
    "export.report.summary.duration": "- Gesamtdauer: {hours:.1f} Stunden",
    "export.report.summary.loose": ("- Lose Dateien direkt im Wurzelordner "
                                    "(unsortiert): {count}"),
    "export.report.summary.warning": ("> [!WARNING]\n"
                                      "> Es konnten keine Dateien erfolgreich gelesen "
                                      "werden."),
    "export.report.formats.title": "## Formate",
    "export.report.formats.bitrate": ("- Bitrate {codec}: Median {median:.0f} kbps, "
                                      "unter {threshold} kbps: {below} von {total}"),
    "export.report.formats.no_cover": "- Ohne Cover: {count}",
    "export.report.tags.title": ("## Fehlende Tags (Anzahl Dateien; `disc` fehlt bei "
                                 "Einzel-CDs normal)"),
    "export.report.tags.entry": "- {field}: {count} ({percent:.1f} %)",
    "export.report.tags.disc": ("- disc: {count} ({percent:.1f} %; meist normal bei "
                                "Einzel-CDs)"),
    "export.report.folders.title": "## Oberste Ordner (Dateien)",
    "export.report.folders.root": "(Wurzel)",
    "export.report.genres.title": "## Genres (alle, mit Anzahl)",
    "export.report.dates.title": "## Datumsformate im Jahr-Tag",
    "export.report.dates.entry": "- {format}: {count}{example}",
    "export.report.dates.example": " (z. B. `{path}`)",
    "export.report.decades.title": "## Jahrzehnte",
    "export.report.decades.entry": "- {prefix}0er: {count}",
    "export.report.artists.title": "## Top-Künstler",
    "export.report.tracks.title": "## Tracknummern-Qualität pro Mehrspur-Album",
    "export.report.tracks.checked": "- Mehrspur-Alben/Ordner geprüft: {count}",
    "export.report.tracks.missing_multi": ("- Dateien mit fehlendem Track-Tag innerhalb "
                                           "dieser Mehrspur-Alben: {count}"),
    "export.report.tracks.albums_missing": ("- Alben mit mindestens einem fehlenden "
                                            "Track-Tag: {count}"),
    "export.report.tracks.all_missing": ("- Alben, bei denen sämtliche Track-Tags fehlen: "
                                         "{count}"),
    "export.report.tracks.gap_albums": "- Alben mit belastbaren Tracknummern-Lücken: {count}",
    "export.report.tracks.sparse": ("- Weitere Alben mit sehr sparsamen/unklaren "
                                    "Nummernfolgen: {count}"),
    "export.report.tracks.incomplete.title": "### Fehlende Track-Tags ({count})",
    "export.report.tracks.incomplete.note": ("_Ein fehlender Track-Tag wird nicht "
                                             "automatisch als fehlender Track gewertet._"),
    "export.report.tracks.incomplete.all": ("{label} / `{album}`: ALLE {total} Track-Tags "
                                            "fehlen"),
    "export.report.tracks.incomplete.some": ("{label} / `{album}`: {missing} von {total} "
                                             "Track-Tags fehlen"),
    "export.report.tracks.gaps.title": "### Belastbare Tracknummern-Lücken ({count})",
    "export.report.tracks.gaps.note": ("_Nur dichte Folgen ab 1 oder explizite "
                                       "Gesamtzahlen (z. B. 03/12) werden als Lücke "
                                       "gewertet._"),
    "export.report.tracks.gaps.entry": "{label} / `{album}`: belastbare Lücken -> {gaps}",
    "export.report.tracks.gaps.more": ", ... ({count} Lücken)",
    "export.report.tracks.no_album": "(ohne Album)",
    "export.report.anomalies.title": "# Automatisch gefundene Auffälligkeiten",
    "export.report.anomalies.note": ("_Nur Hinweise, keine bewiesenen Fehler. Verglichen "
                                     "wird ohne Groß/Klein, Akzente, Leerzeichen und "
                                     "Bindestrich-Arten._"),
    "export.report.variants.title": "## {title} ({count})",
    "export.report.variants.artist": "Künstler: nur Schreibweise verschieden",
    "export.report.variants.albumartist": "Album-Künstler: nur Schreibweise verschieden",
    "export.report.variants.album": "Album (pro Künstler): nur Schreibweise verschieden",
    "export.report.variants.genre": "Genre: nur Schreibweise verschieden",
    "export.report.folder_artist.title": ("## Oberster Ordner passt nicht zu "
                                          "Album-Künstler/Künstler-Tag ({count} Paare)"),
    "export.report.folder_artist.note": ("_Schon herausgerechnet: gekappte Ordnernamen "
                                         "(ab {trunc} Zeichen als Anfang des Tags "
                                         "akzeptiert) und Ordner, die einem von mehreren "
                                         "Künstlern im Tag entsprechen ({skipped} Dateien "
                                         "betroffen, Ordner- und Album-Prüfung zusammen)._"),
    "export.report.folder_album.title": ("## Album-Ordner passt nicht zum Album-Tag "
                                         "({count} Paare)"),
    "export.report.folder_tag": 'Ordner "{folder}" <-> Tag "{tag}" ({count}x)',
    "export.report.style.title": "## Stil-Probleme in Tags ({count} Dateien)",
    "export.report.style.junk": "Junk im {field} ('{match}')",
    "export.report.style.double_space": "Doppelte Leerzeichen im {field}",
    "export.report.style.track_in_title": "Tracknummer im Titel-Tag",
    "export.report.style.underscores": "Unterstriche statt Leerzeichen im Titel",
    "export.report.style.all_caps": "{field} nur in GROSSBUCHSTABEN",
    "export.report.style.all_lower": "{field} nur kleingeschrieben",
    "export.report.field.title": "Titel",
    "export.report.field.artist": "Künstler",
    "export.report.field.album": "Album",
    "export.report.field.albumartist": "Album-Künstler",
    "export.report.field.genre": "Genre",
    "export.report.filename.title": ("## Dateiname enthält den Titel-Tag nicht ({count}; "
                                     "`: / ? * |` -> `_` und gekürzte Namen sind schon "
                                     "herausgerechnet)"),
    "export.report.filename.entry": '`{path}` (Titel-Tag: "{title}")',
    "export.report.duplicates.title": ("## Mögliche Duplikate (gleicher Künstler+Titel) "
                                       "({count} Gruppen)"),
    "export.report.inconsistent.title": ("## Ordner mit uneinheitlichem Album/"
                                         "Album-Künstler/Genre ({count}; Wurzel "
                                         "ausgenommen)"),
    "export.report.dup_tracks.title": ("## Doppelte Tracknummern im selben Ordner+Album "
                                       "({count})"),
    "export.report.samplers.title": ("## Vermutliche Sampler ohne expliziten "
                                     "Album-Künstler ({count})"),
    "export.report.sampler.missing_albumartist": ("`{dir}` ({artists} Künstler, "
                                                  "Album-Künstler fehlt bei "
                                                  "{missing}/{total})"),
    "export.report.sampler.various": ("`{dir}` ({artists} Künstler, Album-Künstler "
                                      "überall \"Various Artists\")"),
    "export.report.errors.title": "## Lesefehler ({count})",
    "export.report.unreadable": "nicht lesbar",
    "export.report.list.empty": "- (keine)",
    "export.report.list.more": "- ... ({count} weitere)",
    "export.report.date.empty": "(leer)",
    "export.report.date.year": "YYYY",
    "export.report.date.ymd": "YYYY-MM-DD",
    "export.report.date.ymd_dot": "YYYY.MM.DD",
    "export.report.date.ym": "YYYY-MM",
    "export.report.date.slash_ymd": "YYYY/MM/DD",
    "export.report.date.slash_ym": "YYYY/MM",
    "export.report.date.dmy": "DD.MM.YYYY",
    "export.report.date.iso": "ISO-Zeitstempel",
    "export.report.date.range": "YYYY-YYYY (Bereich)",
    "export.report.date.other": "Freitext / Sonstiges",
    "export.report.fp.title": ("## Audio-Fingerprint-Duplikate ({groups} Gruppen; "
                               "{n_fp}/{n_total} Dateien hatten einen Fingerprint; "
                               "Basisschwelle {threshold:.0%})"),
    "export.report.fp.note": ("_Die Einstufung kombiniert Audio-Ähnlichkeit, "
                              "Künstler+Titel, Album, Dauer und Duplikat-Marker im "
                              "Dateinamen. Ein hoher Fingerprint-Wert allein beweist keine "
                              "identische Aufnahme. Versionen, Cover, Instrumentals, Edits "
                              "und verschiedene Sprachfassungen können ebenfalls hohe "
                              "Ähnlichkeit erreichen. Ein technischer Qualitätshinweis "
                              "nennt bei wahrscheinlichen Dubletten eine Variante mit "
                              "höherer Bitrate, löscht oder bevorzugt aber nichts "
                              "automatisch._"),
    "export.report.fp.bucket.title": "### {title} ({count} Gruppen)",
    "export.report.fp.bucket.sehr_wahrscheinlich": "Sehr wahrscheinlich echte Dublette",
    "export.report.fp.bucket.wahrscheinlich": "Wahrscheinliche Dublette",
    "export.report.fp.bucket.pruefen": "Prüfen – könnte andere Version sein",
    "export.report.fp.bucket.aehnlich": "Ähnliche Aufnahme / mögliche Variante",
    "export.report.fp.flag.same_identity": "Künstler+Titel gleich",
    "export.report.fp.flag.diff_identity": "Künstler/Titel verschieden",
    "export.report.fp.flag.same_duration": "Länge ähnlich",
    "export.report.fp.flag.diff_duration": "Länge verschieden",
    "export.report.fp.flag.same_album": "Album gleich",
    "export.report.fp.flag.marker": "Duplikat-Marker im Dateinamen",
    "export.report.fp.quality_hint": "; höhere Bitrate: `{path}` ({kbps}k)",
    "export.prompt": """\
# Aufgabe: Musikbibliothek prüfen und Verbesserungen vorschlagen

Du bekommst den Tag-Export meines Musikordners:
- `01_zusammenfassung.md` - Zusammenfassung und Statistik
- `02_auffaelligkeiten.md` - automatisch gefundene Auffälligkeiten
- `03_duplikate.md` - Audio-Fingerprint-Duplikate (falls vorhanden)
- `tracks_part*.tsv` - eine Zeile pro Datei (tab-getrennt): {cols}
  (`path` ist relativ zum Musikordner, `sek` = Dauer in Sekunden, `cover` = j/n;
  mehrere Werte in einem Tag sind mit " | " getrennt)

Meine Sortier-Software (Sortiton) arbeitet mit Regeln in einer `my_rules.ini`.

## Was ich von dir möchte
1. **Überblick:** Was ist der Zustand der Bibliothek? Was sind die größten Baustellen?
2. **Regeln für `my_rules.ini`** - für Wiederkehrendes (Schreibweisen von Künstlern,
   Genres vereinheitlichen), exakt in diesem Format:
   ```
   [Artist]        ; Falsch = Richtig
   [Artist Regex]  ; Regulärer Ausdruck = Ersatz
   [Genre]         ; Falsch = Richtig   (leer rechts = Genre löschen)
   [Protected]     ; Namen, die nie getrennt/geändert werden (z. B. "Simon & Garfunkel")
   ```
3. **Einzelkorrekturen** für Dateien, die eine Regel nicht abdeckt, als CSV mit Semikolon:
   `path;feld;alt;neu` (feld = artist, albumartist, album, title, track, disc, year, genre)
4. **Ordner-/Dateinamen:** Wo passt die Ordnerstruktur nicht zu den Tags?
   Vorschläge für ein einheitliches Schema.
5. **Duplikate, Sampler, fehlende Cover/Tags und Tracknummern** kurz priorisiert auflisten.

## Regeln für dich
- Erfinde nichts. Jahre, Alben o. Ä. nur vorschlagen, wenn sie aus den Daten
  eindeutig hervorgehen; sonst als Rückfrage markieren.
- Groß-/Kleinschreibung NICHT anfassen: GROSSBUCHSTABEN, nur-klein und andere Stilisierungen
  (z. B. "Ado - KIRA", "amnesia", "deadmau5") sind meist die Originalschreibweise und korrekt.
  Melde nur Fälle, in denen DASSELBE Album/derselbe Künstler in mehreren Schreibweisen vorkommt.
- Sonderzeichen in Dateinamen wurden vom Dateisystem oft durch `_` ersetzt (`: / ? * |`) -
  das ist kein Fehler. `(2)` am Dateinamen deutet auf eine doppelte Datei hin.
- Genres können Länder, Sprachen, Fandoms, Plattform-Kategorien (z. B. "Music",
  "Film & Animation") oder Spaß-Tags enthalten. Schlage eine kleine, sinnvolle Liste echter
  Genres vor und frage mich bei Grenzfällen (z. B. "Hololive", "Japanese"), ob ich sie
  behalten will. Falsch geschriebene Kürzel (EDM, R&B, IDM, UK ...) darfst du korrigieren.
- Audio-Fingerprint-Gruppen sind nach Ähnlichkeit gestuft. Gleiche Aufnahme (Kopie) und verwandte Version (Instrumental,
  Cover, andere Sprache, Edit, Kurzfassung) sind NICHT dasselbe. Versionen behalten, echte
  Kopien zusammenfassen und dabei die bessere Datei (höhere Bitrate, vollständige Dauer,
  richtiger Ordner) nennen.
- Weicht ein Ordnername von den Tags ab, sag mir, ob eher der Ordner oder der Tag
  angepasst werden sollte.
- Tags, die zum Original passen, sind korrekt - "Auffälligkeiten" der Zusammenfassung sind nur
  Hinweise, keine Fehler. Prüfe selbst, ob wirklich etwas falsch ist.
- Bei Unsicherheit lieber fragen als raten.
- Arbeite die Teile der Reihe nach ab; gib pro Teil nur die *Änderungen* aus.
- Am Ende: eine zusammengeführte, deduplizierte `my_rules.ini`.

Es gibt {n} Datei(en) in {parts} Teil(en). Fang mit der Zusammenfassung an.
""",

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

    "file.error.no_free_name": "Kein freier Zielname gefunden für: {path}",

    "task.error.folder": "  FEHLER: Ordner nicht gefunden: {path}",
    "task.error.source": "  FEHLER: Quellordner nicht gefunden: {path}",
    "task.error.target_required": "  FEHLER: --move erfordert einen Zielordner.",
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
    "task.error.unreadable": "  ÜBERSPRUNGEN (kein Leseprogramm konnte sie lesen): {name}",
    "task.progress.backup": "sichere …",
    "task.backup.done": "  Backup von {count} Datei(en): {path}",
    "task.backup.failed": "  Backup-Ordner konnte nicht angelegt werden ({path}): {error}",
    "task.backup.prune_failed": "  Altes Backup '{path}' konnte nicht entfernt werden: {error}",
    "task.backup.incomplete": ("  Backup unvollständig; es wurde keine Datei geändert. "
                               "Teil-Backup: {path}"),
    "task.backup.aborted": "  Lauf gestoppt: Das gewünschte Backup ist nicht vollständig.",
    "task.backup.file_error": "  BACKUP FEHLGESCHLAGEN '{name}': {error}",
    "task.scan.done": "  {files} Dateien · {albums} Alben · {artists} Künstler",
    "task.tags.done": "  Fertig. Dateien mit Änderungen: {changed} / {total}",
    "task.rename.done": "  Umbenannt: {renamed}   Bereits korrekt/übersprungen: {skipped}",
    "task.sort.done": "  Verarbeitet: {done} / {total}   Übersprungen: {skipped}",
    "task.placed": "  Einsortiert: {count}",
    "task.error.count": "  Fehler: {count}",
    "task.hint.apply": "  --> Zum Schreiben: --apply anhängen.",
    "task.hint.apply_run": "  --> Zum Ausführen: --apply anhängen.",
    "task.step": "#  {title}",
    "task.aborted": "  ABBRUCH in '{title}' (rc={rc}).",
    "task.cancelled": "  Abgebrochen.",
    "task.all.done": "  ALL-IN-ONE fertig. ({mode})",
    "task.mode.applied": "ausgeführt",
    "task.mode.preview": "Vorschau",
    "task.step.fetch": "Audio laden",
    "task.step.tags": "Tags bereinigen",
    "task.step.rename": "Umbenennen",
    "task.step.sort": "Sortieren",
    "task.step.label": "{index}/{total} · {title}",

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

    "rules.warn.read": "Regeldatei konnte nicht gelesen werden ({file}): {error}",
    "rules.warn.invalid": "Regeldatei ist fehlerhaft ({file}): {error}",
    "rules.warn.artist_no_equals": 'Künstler-Regel „{rule}“ ohne „=“ – übersprungen (alt = neu).',
    "rules.warn.regex_no_equals": 'Regex-Regel „{rule}“ ohne „=“ – übersprungen (MUSTER = ERSATZ).',
    "rules.warn.regex_invalid": 'Regex-Regel „{rule}“ ungültig – übersprungen: {error}',
    "rules.warn.regex_too_long": 'Regex-Regel „{rule}“ ist zu lang – übersprungen.',
    "rules.warn.regex_unsafe": ('Regex-Regel „{rule}“ enthält verschachtelte/alternierende '
                                'Quantoren (ReDoS-Risiko) – übersprungen.'),
    "rules.warn.genre_no_equals": 'Genre-Regel „{rule}“ ohne „=“ – übersprungen (alt = neu).',
    "rules.summary.artists": "{count} Künstler",
    "rules.summary.artists_plural": "{count} Künstler",
    "rules.summary.regex": "{count} Regex",
    "rules.summary.genre": "{count} Genre",
    "rules.summary.protected": "{count} geschützt",

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
    "rules.overview.artist_sub3": "#   Regex-Regeln greifen nur auf Werte bis 512 Zeichen (ReDoS-Schutz).",
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

    "gui.window.title": "Sortiton",
    "gui.button.custom_rules": "Eigene Regeln …",
    "gui.button.paste_llm": "LLM-Antwort einfügen",
    "gui.chip.tool_ok": "{tool} ✓ {version}",
    "gui.chip.tool_ok_noversion": "{tool} ✓",
    "gui.chip.tool_missing": "{tool} fehlt",
    "gui.tab.tags": "Tags bereinigen",
    "gui.tab.rename": "Umbenennen",
    "gui.tab.sort": "Sortieren",
    "gui.tab.all": "Alles anwenden",
    "gui.tab.tools": "Werkzeuge",
    "gui.button.preview": "Vorschau",
    "gui.button.change": "Ändern…",
    "gui.button.write_tags": "Tags schreiben",
    "gui.button.rename": "Umbenennen",
    "gui.button.sort": "Sortieren",
    "gui.button.run_all": "Alles ausführen",
    "gui.button.run_tool": "Ausführen",
    "gui.button.write_fixes": "Korrekturen schreiben",
    "gui.button.copy_prompt": "Prompt kopieren",
    "gui.button.open_export": "Report öffnen",
    "gui.button.clear": "Leeren",
    "gui.button.open_folder": "Ordner öffnen",
    "gui.button.open_logs": "Logs öffnen",
    "gui.button.insert_template": "Vorlage einfügen",
    "gui.button.builtin_rules": "Eingebaute Regeln",
    "gui.button.system_editor": "System-Editor",
    "gui.button.cancel": "Abbrechen",
    "gui.button.save": "Speichern",
    "gui.button.apply_rules": "Übernehmen",
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
    "gui.hint.rename": ("Benennt Dateien nach ihren Tags um. Die Vorschau zeigt zuerst "
                        "die neuen Namen – vor „Umbenennen“ ändert sich nichts."),
    "gui.hint.tools": ("Hilfswerkzeuge mit eigenem Ablauf: Berichte exportieren, "
                       "Korrekturen aus einer CSV anwenden oder Audio herunterladen."),
    "gui.hint.export": ("Nur lesend: liest den Ordner und schreibt die Berichte. "
                        "In der Bibliothek ändert sich nichts."),
    "gui.hint.fetch": ("Lädt Audio mit yt-dlp. Nur Inhalte laden, für die du die "
                       "Rechte hast."),
    "gui.hint.fixes": ("Wendet Einzelkorrekturen aus einer CSV an (der Export-Prompt "
                       "verlangt genau dieses Format). Nur Zeilen, deren aktueller "
                       "Wert noch passt, werden geschrieben."),
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
    "gui.confirm.tools.title": "Korrekturen wirklich schreiben?",
    "gui.confirm.fetch.title": "Wirklich herunterladen?",
    "gui.confirm.fetch.text": ("yt-dlp lädt die URL herunter und schreibt das Audio "
                               "in den gewählten Ordner."),
    "gui.confirm.fetch.note": "Nur Inhalte laden, für die du die Rechte hast.",
    "gui.confirm.tools.text": ("{changes} Korrekturen aus {files} CSV-Zeile(n) werden "
                               "in die Audiodateien geschrieben."),
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
    "gui.dialog.file_not_found.title": "Datei nicht gefunden",
    "gui.dialog.file_not_found.text": "Diese Datei existiert nicht:\n{path}",
    "gui.dialog.save_failed.title": "Speichern fehlgeschlagen",
    "gui.dialog.save_failed.text": "Die Regeldatei konnte nicht geschrieben werden:\n\n{error}",
    "gui.status.ready": "bereit",
    "gui.status.running": "läuft…",
    "gui.status.failed": "fehlgeschlagen (rc={rc})",
    "gui.status.cancelled": "abgebrochen",
    "gui.status.cancelling": "wird abgebrochen – Fenster schließt danach",
    "gui.status.progress": "{current} / {total} · {text}",
    "gui.job.tags": "Tag-Bereinigung",
    "gui.job.rename": "Umbenennen",
    "gui.job.sort": "Sortieren",
    "gui.job.all": "Alles anwenden",
    "gui.job.export": "Berichte exportieren",
    "gui.job.fixes": "CSV-Korrekturen anwenden",
    "gui.job.fetch": "Audio herunterladen",
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
    "gui.rules.status.prefilled": "Aus der LLM-Antwort vorbelegt – noch nicht gespeichert",
    "gui.rules.confirm_replace.title": "Editorinhalt ersetzen?",
    "gui.rules.confirm_replace.text": ("Im Editor steht noch ungespeicherter Text. "
                                       "Durch den LLM-Block ersetzen?"),
    "gui.rules.confirm_template.title": "Vorlage einfügen?",
    "gui.rules.confirm_template.text": ("Der Text im Feld wird durch die Vorlage ersetzt – die Datei "
                                        "selbst bleibt unverändert, bis du speicherst."),
    "gui.llm.title": "LLM-Antwort einfügen",
    "gui.llm.hint": ("Hier die Antwort des LLM einfügen. Es wird der erste ```ini-Block "
                     "verwendet – ohne einen der ganze Text. Nichts wird automatisch "
                     "gespeichert; der Regeleditor öffnet vorbelegt zur Prüfung."),
    "gui.llm.status.empty": "Noch nichts eingefügt",
    "gui.llm.status.ok": "Keine Warnungen – Regeleditor wird geöffnet",
    "gui.llm.status.warnings": "{count} Warnung(en) – siehe Protokoll; Regeleditor wird geöffnet",
    "gui.language.de": "DE",
    "gui.language.en": "EN",
    "gui.dialog.busy.title": "Bitte warten",
    "gui.dialog.busy.text": "Es läuft noch ein Auftrag. Bitte warten, bis er fertig ist.",
    "gui.dialog.preview_stale.title": "Vorschau nötig",
    "gui.dialog.preview_stale.text": ("Die Eingaben wurden geändert oder der letzte "
                                      "Lauf hat geschrieben. Bitte vor dem Schreiben "
                                      "eine neue Vorschau erstellen."),
    "gui.dialog.force_close.title": "Trotzdem schließen?",
    "gui.dialog.force_close.text": ("Der Auftrag läuft noch. Beim Schließen kann "
                                    "eine Datei mitten im Schreiben unterbrochen "
                                    "werden. Trotzdem schließen?"),
    "gui.dialog.filetype.csv": "CSV / Text",
    "gui.dialog.filetype.all": "Alle Dateien",
    "gui.dialog.close.title": "Ein Auftrag läuft noch",
    "gui.dialog.close.text": ("Ein Auftrag läuft noch. Abbrechen und das Fenster "
                              "schließen, sobald er beendet ist?"),

    "gui.button.settings": "Einstellungen",
    "gui.button.choose_folder": "Ordner auswählen",
    "gui.button.choose_file": "Datei auswählen …",
    "gui.button.refresh": "Aktualisieren",
    "gui.button.preview_create": "Vorschau erstellen",
    "gui.button.details": "Details anzeigen",
    "gui.button.back": "Zurück",
    "gui.button.close": "Schließen",
    "gui.button.open_backup": "Backup öffnen",
    "gui.button.fine_tuning": "Feineinstellungen …",
    "gui.section.music_folder": "Musikordner",
    "gui.section.folders": "Ordner",
    "gui.section.options": "Optionen",
    "gui.section.active_rules": "Aktive Bereinigung",
    "gui.section.preview": "Vorschau",
    "gui.section.result": "Ergebnis",
    "gui.result.none": "Noch kein Lauf – hier erscheinen die Zahlen des letzten Laufs.",
    "gui.choice.report_lang.ui": "Wie die Oberfläche",
    "gui.choice.report_lang.en": "Englisch",
    "gui.choice.report_lang.de": "Deutsch",
    "gui.tool.export": "Export",
    "gui.tool.export.run": "Export starten",
    "gui.tool.fixes": "Korrekturen",
    "gui.tool.fixes.run": "Korrekturen schreiben",
    "gui.tool.fetch": "Download",
    "gui.tool.fetch.run": "Download starten",
    "gui.tools.section.files": "Ordner & Dateien",
    "gui.tools.section.report": "Inhalt der Berichte",
    "gui.tools.section.download": "Download",
    "gui.tools.section.advanced": "Duplikate & Tempo",
    "gui.tools.badge.readonly": "nur lesend",
    "gui.tools.badge.writes": "schreibt Dateien",
    "gui.tools.readonly_note": "Nur lesend – es ändert sich nichts.",
    "gui.tools.fine_tuning_hint": ("Berichtslänge, Duplikatprüfung und Leseranzahl "
                                   "stehen in den Einstellungen."),
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
    "gui.preview.summary_fetch": "{count} Eintrag/Einträge gefunden",
    "gui.preview.more": "+{count} weitere",
    "gui.field.artist": "Künstler",
    "gui.field.album_artist": "Album-Künstler",
    "gui.field.title": "Titel",
    "gui.field.album": "Album",
    "gui.field.genre": "Genre",
    "gui.field.track": "Track",
    "gui.field.disc": "Disc",
    "gui.field.year": "Jahr",
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
    "gui.result.parts": "Report-Dateien",
    "gui.result.duplicates": "Duplikat-Gruppen",
    "gui.status.scanning": "Analysiere Dateien …",
    "gui.status.percent": "{current} / {total} · {percent} %",
    "gui.log.ffprobe_missing": "  Hinweis: ffprobe fehlt – Tags werden langsamer gelesen (ffmpeg installieren).",
    "gui.settings.title": "Einstellungen",
    "gui.settings.heading": "Einstellungen",
    "gui.settings.scale": "Darstellung: {percent} % – SORTITON_UI_SCALE überschreibt sie",
    "gui.settings.tools": "Externe Programme",
    "gui.settings.tools_hint": ("Sortiton nutzt das beste verfügbare Programm – hier gibt es "
                                "nichts einzustellen."),
    "gui.settings.language": "Sprache",
    "gui.settings.language_hint": "Steht in settings.ini und gilt wieder beim nächsten Start.",

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
    "restore.remove_download": "  Download entfernen: {name}",
    "restore.ok.tags": "  OK Tags    : {name}",
    "restore.ok.copy": "  OK gelöscht: {name}",
    "restore.ok.download": "  OK gelöscht: {name}",
    "restore.ok.move": "  OK zurück  : {name}",
    "restore.done": ("  Fertig. Zurückgenommen: {changed}   Übersprungen: {skipped}   "
                     "({total} Ereignisse)"),
    "restore.skip.failed": "  übersprungen (der Lauf war fehlerhaft): {name}",
    "restore.skip.missing": "  übersprungen (Datei ist weg): {name}",
    "restore.skip.exists": "  übersprungen (der alte Name ist wieder belegt): {name}",
    "restore.skip.keep_copy": "  behalten (--keep-copies): {name}",
    "restore.skip.keep_download": "  behalten (--keep-copies): {name}",
    "restore.skip.only_copy": ("  behalten (das Original ist weg – es ist die letzte Kopie): "
                               "{name}"),
    "restore.skip.unknown": "  übersprungen (nicht rücknehmbar): {op}",
    "restore.skip.changed": "  übersprungen (seit dem Lauf geändert: {fields}): {name}",
    "restore.skip.modified": "  behalten (die Kopie weicht vom Original ab): {name}",
    "restore.error.archive": ("  FEHLER: Die Download-Archivzeile für {name} ließ "
                              "sich nicht entfernen - die Datei wurde behalten."),
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
    "gui.restore.busy": "Es läuft noch ein Auftrag - das Rückgängigmachen startete nicht.",
    "gui.restore.run": "Jetzt zurücknehmen",
    "gui.restore.more": "… und {count} weitere",
    "gui.restore.op.tags": "Tags",
    "gui.restore.op.move": "Zurück",
    "gui.restore.op.copy": "Kopie löschen",
    "gui.restore.op.download": "Download löschen",
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


def t_in(lang: str, key: str, **fmt: object) -> str:
    """Translate ``key`` in ``lang`` without touching the active language."""
    text = _CATALOGS.get(lang, {}).get(key)
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


def t(key: str, **fmt: object) -> str:
    """Translate ``key`` in the active language; fall back to English, then key."""
    return t_in(_language, key, **fmt)


def catalog(code: str) -> dict[str, str]:
    """Raw translation table for ``code`` (empty if unknown)."""
    return dict(_CATALOGS.get(code, {}))
