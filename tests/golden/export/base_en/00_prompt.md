# Task: check a music library and suggest improvements

You get the tag export of my music folder:
- `01_zusammenfassung.md` - summary and statistics
- `02_auffaelligkeiten.md` - automatically found anomalies
- `03_duplikate.md` - audio fingerprint duplicates (if present)
- `tracks_part*.tsv` - one line per file (tab separated): `path`, `artist`, `albumartist`, `album`, `title`, `track`, `disc`, `year`, `genre`, `sek`, `kbps`, `codec`, `cover`
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

There are 42 file(s) in 3 part(s). Start with the summary.
