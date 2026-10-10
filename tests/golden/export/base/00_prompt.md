# Aufgabe: Musikbibliothek prüfen und Verbesserungen vorschlagen

Du bekommst den Tag-Export meines Musikordners:
- `01_zusammenfassung.md` - Zusammenfassung und Statistik
- `02_auffaelligkeiten.md` - automatisch gefundene Auffälligkeiten
- `03_duplikate.md` - Audio-Fingerprint-Duplikate (falls vorhanden)
- `tracks_part*.tsv` - eine Zeile pro Datei (tab-getrennt): `path`, `artist`, `albumartist`, `album`, `title`, `track`, `disc`, `year`, `genre`, `sek`, `kbps`, `codec`, `cover`
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

Es gibt 42 Datei(en) in 3 Teil(en). Fang mit der Zusammenfassung an.
