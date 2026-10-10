# Automatisch gefundene Auffälligkeiten

_Nur Hinweise, keine bewiesenen Fehler. Verglichen wird ohne Groß/Klein, Akzente, Leerzeichen und Bindestrich-Arten._

## Künstler: nur Schreibweise verschieden (2)

- "Artist A" (2x) <-> "artist a" (1x)
- "Ünïcode" (1x) <-> "Unicode" (1x)

## Album-Künstler: nur Schreibweise verschieden (1)

- "Ünïcode" (1x) <-> "Unicode" (1x)

## Album (pro Künstler): nur Schreibweise verschieden (0)

- (keine)

## Genre: nur Schreibweise verschieden (0)

- (keine)

## Oberster Ordner passt nicht zu Album-Künstler/Künstler-Tag (9 Paare)

_Schon herausgerechnet: gekappte Ordnernamen (ab 25 Zeichen als Anfang des Tags akzeptiert) und Ordner, die einem von mehreren Künstlern im Tag entsprechen (0 Dateien betroffen, Ordner- und Album-Prüfung zusammen)._

- Ordner "Fp" <-> Tag "Fp Artist" (3x)
- Ordner ".hidden" <-> Tag "Hidden Artist" (1x)
- Ordner "Sampler" <-> Tag "Alpha" (1x)
- Ordner "Sampler" <-> Tag "Beta" (1x)
- Ordner "Sampler" <-> Tag "Gamma" (1x)
- ... (4 weitere)

## Album-Ordner passt nicht zum Album-Tag (1 Paare)

- Ordner "Album Three" <-> Tag "Different Album" (1x)

## Stil-Probleme in Tags (2 Dateien)

- `Artist B/Album Two/01 Song (Official Video).ogg`: Junk im Titel ('Official Video'), Doppelte Leerzeichen im Titel, Tracknummer im Titel-Tag
- `Artist B/Album Two/02 - snake_case_title.opus`: Unterstriche statt Leerzeichen im Titel

## Dateiname enthält den Titel-Tag nicht (10; `: / ? * |` -> `_` und gekürzte Namen sind schon herausgerechnet)

- `Fp/other.opus` (Titel-Tag: "Other Song")
- `Fp/same_a.opus` (Titel-Tag: "Same Song")
- `Fp/same_b.mp3` (Titel-Tag: "Same Song")
- `loose.mp3` (Titel-Tag: "Loose Track")
- `Sampler/01.mp3` (Titel-Tag: "Alpha One")
- ... (5 weitere)

## Mögliche Duplikate (gleicher Künstler+Titel) (2 Gruppen)

- `Artist B/Album Two/03 - Same Song (2).m4a` (69k, 1s, 0.0MB) ; `Artist B/Singles/Same Song.m4a` (69k, 1s, 0.0MB)
- `Fp/same_a.opus` (50k, 6s, 0.0MB) ; `Fp/same_b.mp3` (48k, 6s, 0.0MB)

## Ordner mit uneinheitlichem Album/Album-Künstler/Genre (2; Wurzel ausgenommen)

- `Artist E/Album Five` - Genre: ['J-Pop', 'J-Pop | Rock', 'Rock']
- `Ünïcode` - Album-Künstler: ['Unicode', 'Ünïcode']

## Doppelte Tracknummern im selben Ordner+Album (2)

- `Fp`: ['CD1#1']
- `Sampler`: ['CD1#1']

## Vermutliche Sampler ohne expliziten Album-Künstler (1)

- `Sampler` (5 Künstler, Album-Künstler fehlt bei 5/5)

## Lesefehler (1)

- `broken.mp3`: nicht lesbar
