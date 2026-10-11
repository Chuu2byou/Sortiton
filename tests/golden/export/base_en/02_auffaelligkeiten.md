# Automatically found anomalies

_Hints only, no proven errors. The comparison ignores case, accents, spaces and hyphen kinds._

## Artist: spelling differs only (2)

- "Artist A" (2x) <-> "artist a" (1x)
- "Ünïcode" (1x) <-> "Unicode" (1x)

## Album artist: spelling differs only (1)

- "Ünïcode" (1x) <-> "Unicode" (1x)

## Album (per artist): spelling differs only (0)

- (none)

## Genre: spelling differs only (0)

- (none)

## Top folder does not match the album artist/artist tag (8 pairs)

_Already factored out: truncated folder names (from 25 characters accepted as the start of the tag) and folders that match one of several artists in the tag (0 files affected, folder and album check together)._

- Folder "Fp" <-> tag "Fp Artist" (3x)
- Folder "Sampler" <-> tag "Alpha" (1x)
- Folder "Sampler" <-> tag "Beta" (1x)
- Folder "Sampler" <-> tag "Gamma" (1x)
- Folder "Sampler" <-> tag "Delta" (1x)
- ... (3 more)

## Album folder does not match the album tag (1 pairs)

- Folder "Album Three" <-> tag "Different Album" (1x)

## Style problems in tags (2 files)

- `Artist B/Album Two/01 Song (Official Video).ogg`: junk in title ('Official Video'), double spaces in title, track number in the title tag
- `Artist B/Album Two/02 - snake_case_title.opus`: underscores instead of spaces in the title

## File name does not contain the title tag (10; `: / ? * |` -> `_` and truncated names are already factored out)

- `Fp/other.opus` (title tag: "Other Song")
- `Fp/same_a.opus` (title tag: "Same Song")
- `Fp/same_b.mp3` (title tag: "Same Song")
- `loose.mp3` (title tag: "Loose Track")
- `Sampler/01.mp3` (title tag: "Alpha One")
- ... (5 more)

## Possible duplicates (same artist+title) (2 groups)

- `Artist B/Album Two/03 - Same Song (2).m4a` (69k, 1s, 0.0MB) ; `Artist B/Singles/Same Song.m4a` (69k, 1s, 0.0MB)
- `Fp/same_a.opus` (50k, 6s, 0.0MB) ; `Fp/same_b.mp3` (48k, 6s, 0.0MB)

## Folders with inconsistent album/album artist/genre (2; root excluded)

- `Artist E/Album Five` - genre: ['J-Pop', 'J-Pop | Rock', 'Rock']
- `Ünïcode` - album artist: ['Unicode', 'Ünïcode']

## Duplicate track numbers in the same folder+album (2)

- `Fp`: ['CD1#1']
- `Sampler`: ['CD1#1']

## Suspected samplers without an explicit album artist (1)

- `Sampler` (5 artists, album artist missing for 5/5)

## Read errors (1)

- `broken.mp3`: nicht lesbar
