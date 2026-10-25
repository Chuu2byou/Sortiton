# Sortiton: UI-Handoff

Stand: 25.10.2026. Status: Gestaltungsempfehlung, keine implementierte UI.

## Entscheidung

Sortiton soll sich wie ein Werkzeug zum Pruefen und Bearbeiten einer
Musiksammlung anfuehlen, nicht wie eine lange Einstellungsseite.
Empfohlen wird eine kompakte Zwei-Spalten-Arbeitsflaeche:
Auftrag und Regeln links, Vorschau rechts, Freigabe und Status unten.
Zusaetzlicher Fensterplatz soll mehr pruefbare Inhalte zeigen.

Zunaechst Tkinter beibehalten. Der groesste Nutzen entsteht durch die
Informationsarchitektur, nicht durch neue Farben oder einen Frameworkwechsel.
Eine spaetere PySide6-Migration separat entscheiden, falls eine grosse
Dateitabelle, native Barrierefreiheit und bessere Desktop-Integration mit
Tkinter nicht ausreichend erreichbar sind. Das waere ein eigener Auftrag
mit neuen Abhaengigkeiten und Packaging-Arbeit.

## Befunde und Evidenz

Gesichtet wurden der README-Screenshot, der aktuelle Fensteraufbau,
Designwerte, Vorschau-/Ergebniswidgets und die vorhandenen GUI-Tests.
Die aktuelle Anwendung wurde unter Xvfb mit UI-Skalierung 100 Prozent
bei drei Fenstergroessen vermessen und bei 1920 x 1080 fotografiert.
Die aktuelle UI unterscheidet sich vom README-Screenshot: Sie hat unter
anderem fuenf Seiten, Seitenueberschriften und weitere Ordner-/Modusfelder.

| Fenster | Formularbreite | Formularhoehe | Aktionszeile y | Ergebnishoehe |
| --- | ---: | ---: | ---: | ---: |
| 900 x 600 | 841 px | 714 px | 321 px | 176 px |
| 1920 x 1080 | 1120 px | 714 px | 801 px | 176 px |
| 2560 x 1440 | 1120 px | 714 px | 1161 px | 176 px |

Diese Werte beschreiben den Startzustand der Seite "Tags bereinigen".
Bei 900 x 600 ist das Formular erwartungsgemaess scrollbar.
Bei 2560 x 1440 nutzt es nur rund 44 Prozent der Fensterbreite;
zwischen Formularende und Aktionszeile bleiben etwa 360 Pixel ungenutzt.
Die Ergebnisflaeche waechst nicht mit.

Die Breitenbegrenzung und Zentrierung steuert
[`_resize_content_canvas`](sortiton/gui/mixins/layout.py#L318).
Die flexible Hoehe liegt in der Inhaltszeile, waehrend das Ergebnis eine
feste Mindesthoehe erhaelt:
[`_build_window`](sortiton/gui/mixins/layout.py#L179).
Formular und feste Zeilen verwenden unterschiedliche Breitenberechnungen:
[`_content_inset`](sortiton/gui/mixins/layout.py#L47).
Bei 2560 Pixeln startet das Formular bei x=720, die Aktionszeile bei x=713.
Der Scrollbalken liegt zudem am aeusseren Fensterrand, weit vom Formular.

Das erklaert die schlechte Raumnutzung bei grossen Fenstern. Eine konkrete
Ueberlappung wurde nicht festgestellt. Echtes Maximieren unter KDE/Wayland,
Fensterdekorationen, mehrere Monitore und HiDPI sind noch nicht verifiziert.

Der veraltete Eindruck ist eine gestalterische Bewertung:
Viele grossflaechige Rahmen, verschachtelte Vorschau-Rahmen,
Grossbuchstaben-Labels, ueberwiegend dunkle Flaechen und verstreute Aktionen
geben gleich wichtigen und unwichtigen Informationen aehnliches Gewicht.
Die Vorschau bleibt ein kleiner Zusammenfassungsblock statt Hauptarbeitsraum.

## Zielbild

Breites Desktopfenster, schematisch; Zahlen und Inhalte sind Beispieldaten:

```text
 Sortiton   Tags bereinigen | Umbenennen | Sortieren | Alles | Werkzeuge   [Zahnrad]
 ------------------------------------------------------------------------------
 Auftrag / 320 px             | Vorschau                    [Suche] [Filter]
                             | 120 Dateien / 198 Aenderungen
 Quellordner        [Ordner]  | ------------------------------------------------
 Zielordner         [Ordner]  | Datei       Feld       Bisher          Geplant
 Kopieren | Verschieben      | Track 01    Artist     SAMPLE BAND     Sample Band
                             | Track 03    Titel      Track  03       Track 03
 Regeln                      | Track 08    Genre      jpop            J-Pop
 Eigene Regeln      [Bearb.]  | ... weitere sichtbare Zeilen ...
 Korrekturen        [Details] | ------------------------------------------------
                             | Auswahl: Track 03
 Weitere Optionen       [v]  | Vollstaendige Werte / Pfad / zutreffende Regel
 ------------------------------------------------------------------------------
 Bereit / Backup aktiv       [Vorschau erstellen]       [Aenderungen anwenden]
```

Keine dekorativen Karten um ganze Seitenabschnitte. Eine schmale Trennlinie
trennt Konfiguration und Pruefbereich. Tabellenzeilen und Gruppenabstaende
strukturieren den Inhalt. Das vorhandene App-Icon bleibt die visuelle Marke.
Keine Albumcover, wenn keine verlaesslichen Coverdaten vorhanden sind.

### Navigation und Raumaufteilung

- Die fuenf vorhandenen Funktionen bleiben direkt erreichbar. Echte Tabs
  ersetzen die optisch gleichwertige, breit gestreckte Segmentleiste.
- Links ein veraenderbarer Konfigurationsbereich: Standard 320 logische
  Pixel, Minimum 280, Maximum 420. Lange Pfade mit Volltextzugriff.
- Rechts fuellt die Vorschau den verbleibenden Raum und waechst in der Hoehe.
  Ihre Zeilen scrollen; Navigation und Freigabe bleiben sichtbar.
- Ab 1200 logischen Pixeln zwei Spalten. Zwischen 900 und 1199 Pixeln
  einklappbare Konfiguration. Darunter Konfiguration oberhalb der Vorschau,
  ohne horizontales Scrollen der gesamten Anwendung.
- Kein globales 1120-Pixel-Limit. Nur Lesetexte und einzelne Eingabefelder
  bekommen sinnvolle Maximalbreiten. Scrollbalken direkt am scrollenden Inhalt.
- Die Ergebniszusammenfassung ersetzt nach einem Lauf die Vorschau-Kopfzeile.
  Logs werden bei Bedarf als eigener vergroesserbarer Bereich geoeffnet.
  Kein dauerhaft 176 Pixel hoher, leerer Ergebnisblock.
- Einstellungen bleiben ein eigenes Fenster. Wiederherstellung bleibt ein
  eigener Dialog; Zugang ueber eine erkennbare Rueckgaengig-Aktion.

### Visuelle Spezifikation

| Element | Vorgabe |
| --- | --- |
| Farbschema | Auto (System), Hell oder Dunkel; Auswahl in den Einstellungen, sofort angewendet |
| Hintergrund / Arbeitsflaeche | `#F4F5F7` / `#FFFFFF` |
| Haupttext / Sekundaertext | `#20242B` / `#545D6B` |
| Linien | `#D8DDE4`, sparsam eingesetzt |
| Primarakzent | Petrol `#006B68`, weisser Text |
| Erfolg / Warnung / Fehler | `#187346` / `#875400` / `#B42318` |
| Schrift | Cantarell, danach Noto Sans, danach vorhandener Systemfont |
| Schriftgroessen | Basis 11 pt, Seitentitel 15 pt, Nebenwerte mindestens 10 pt |
| Raster | 4 / 8 / 12 / 16 / 24 logische Pixel |
| Bedienelemente | 36 px Hoehe, Icon-Ziele mindestens 32 x 32 px |
| Tabellenzeilen | 32 px, konstante Hoehe, klarer Auswahlzustand |
| Rundungen | 4 px fuer Felder und Buttons, keine Pillen fuer Statuswerte |

Keine rein farbliche Statuscodierung: immer Text und Symbol ergaenzen.
Kontrast der finalen hellen und dunklen Kombinationen gegen WCAG AA pruefen.
Ein konsistenter Icon-Satz, beispielsweise Lucide als vorbereitete
PNG-Assets fuer Tkinter, ersetzt gemischte Unicode-Symbole.
Ordner, Aktualisieren, Einstellungen und Rueckgaengig erhalten Icons,
Tooltips und zugaengliche Namen. Primaere Befehle behalten Text.
Sichtbarer Tastaturfokus; keine blinkenden Effekte oder dekorativen Animationen.

## Interaktion und Sicherheitsregeln

| Zustand | Anzeige und erlaubte Aktion |
| --- | --- |
| Kein Auftrag | Ordnerfelder sichtbar, Ausfuehren gesperrt |
| Noch keine Vorschau | Leerer Pruefbereich, Vorschau als primaerer Befehl |
| Analyse laeuft | Fortschritt und Abbrechen; keine parallele Ausfuehrung |
| Vorschau aktuell | Anzahl Dateien/Aenderungen; Anwenden primaer |
| Eingaben geaendert | Vorschau als veraltet markieren; Anwenden sperren |
| Keine Aenderungen | Sachlicher Nullzustand; kein scheinbar noetiger Schreiblauf |
| Ausfuehrung laeuft | Fortschritt, Abbrechen, Konfiguration gesperrt |
| Fertig / teilweise fehlgeschlagen | Zaehler, Fehlerdetails, Log und Wiederherstellung |

Vorschau und Ausfuehrung bleiben getrennt. Die bestehende
[`_preview_ready`](sortiton/gui/mixins/run.py#L397)-Pruefung darf durch das
Redesign nicht entfallen. Geaenderte Ordner, Regeln, Muster oder Modi
invalidieren weiterhin die Freigabe. Backup-Status ist sichtbar;
die bestehende Bestaetigung zeigt Umfang, Ziel und Dateioperation.
Verschieben, Duplikate und Downloads behalten ihre speziellen Warnungen.
Abbruch ist kein Rollback; Wiederherstellung ist eine separate Operation.

Tags: Vorschau nach Datei und Tagfeld. Umbenennen/Sortieren: Quellpfad,
Zielpfad und Operation. Alles: Schritte klar unterscheiden.
Werkzeuge: vorhandene feature-spezifische Optionen und Statuswerte erhalten;
Export/Downloads nicht kuenstlich in eine Tag-Tabelle pressen.

## Umsetzungshandoff

### Paket 1: Layout ohne Backend-Umbau

In [`layout.py`](sortiton/gui/mixins/layout.py) Konfiguration und Vorschau
in einen geteilten Arbeitsbereich ueberfuehren. Die flexible Grid-Zeile
gehoert der Vorschau, nicht einer leeren Canvas-Flaeche.
Ein gemeinsamer Aussenabstand ersetzt die getrennten Zentrierformeln.
In [`log.py`](sortiton/gui/mixins/log.py) Ergebnis und Log bedarfsgerecht
oeffnen; Status und Freigabe in einer stabilen unteren Zeile zusammenfassen.
In [`design.py`](sortiton/gui/design.py) Farben, Abstaende und Typografie
zentral pflegen; Widgets und Formulare daran anpassen.

Zunaechst die vorhandene aggregierte Vorschau verwenden und eindeutig als
Zusammenfassung kennzeichnen. Keine Suche oder Filter anbieten, die nur
wenige Beispiele durchsuchen, aber Vollstaendigkeit suggerieren.

### Paket 2: Vollstaendige Pruefansicht

[`PreviewCard`](sortiton/gui/panels.py#L29) zeigt aktuell Beispiele.
[`_absorb_plan`](sortiton/gui/mixins/run.py#L303) aggregiert Ereignisse,
[`_plan_rows`](sortiton/gui/mixins/run.py#L451) zeigt fuer Tags nur das
erste Beispiel pro Feld und fuer Dateioperationen das erste Pfadpaar.
Eine vollstaendige Tabelle ist deshalb mehr als ein Widget-Austausch.

Plan-Ereignisse aus [`output.py`](sortiton/output.py) auf nutzbare Datei- und
Feldinformationen pruefen, dann ein separates, strukturiertes Lesemodell
mit Lauf-ID, Pfad, Operation, Feld, Alt-/Neuwert und belegbarem Status bauen.
Regelherkunft nur anzeigen, wenn sie tatsaechlich mitgeliefert wird.
Zaehler und Signatur-Sperre erhalten. Speicherbedarf begrenzen, grosse Plaene
seitenweise laden oder auf temporaeren Speicher auslagern.
Nicht fuer jede Aenderung neue Tk-Labels erzeugen.

Erst danach dateibezogene Suche, Filter und Detailansicht aktivieren.
Die Tabelle ist zunaechst nur lesend: Auswahl bedeutet Detailansicht,
nicht selektive Ausfuehrung. Checkboxen fuer Einzelaenderungen sind nicht
Teil dieses Auftrags und benoetigen eine eigene Ausfuehrungssemantik.

### Nicht Teil des Auftrags

Kein Backend-Rewrite, keine neue Regelengine, keine CLI-Aenderung,
keine automatische Dateiaenderung, keine neue Musikplayer-Funktion.
Keine neue Persistenz fuer Fensterlayout ohne gesonderte Entscheidung.
Alle sichtbaren Texte bleiben deutsch/englisch in
[`i18n.py`](sortiton/i18n.py); Features und gespeicherte Optionen erhalten.

## Abnahme

- Bei 900 x 600, 1280 x 720, 1920 x 1080 und 2560 x 1440 bleiben Tabs,
  Freigabe und Abbrechen sichtbar; keine ueberlappenden Bedienelemente.
- Bei 100, 150 und 200 Prozent Skalierung zaehlen logische Masse;
  kein doppeltes Skalieren von Fonts und Widgets. Kleine Arbeitsflaechen
  wechseln in das schmale Layout statt grosse Mindestbreiten zu erzwingen.
- Mehr Fensterhoehe vergroessert die Vorschau, nicht eine Leerflaeche
  zwischen Konfiguration und Aktionen. Mehr Breite verbessert die Pruefansicht.
- Formular, Kopf und Fuss haben dieselben Aussenkanten. Scrollbalken
  erscheinen nur bei Ueberlauf und liegen an ihrem Inhaltsbereich.
- Alle fuenf Seiten, deutsche/englische Texte und lange Pfade pruefen.
  Vollstaendige Werte bleiben ueber Detailansicht oder Tooltip erreichbar.
- Tastaturbedienung inklusive Tab-Reihenfolge, Fokus, Seitenwechsel,
  Bestaetigung und Abbruch ist moeglich. Icons allein brauchen Tooltips.
- Tests fuer aktuelle/veraltete Vorschau, Sperren waehrend eines Laufs,
  Backup, Fehler und Wiederherstellung bleiben gruen.
- Paket 2: 10.000 Aenderungen mit synthetischen Daten pruefen;
  Suche, Scrollen und Abbrechen blockieren den UI-Thread nicht merklich.
  Vollstaendigkeit und Zaehler muessen mit dem Plan uebereinstimmen.
- Layout-Regressionen in [`test_gui.py`](tests/test_gui.py) ergaenzen;
  aktuell werden kleine Fenster und Scrollen, aber keine breite adaptive
  Arbeitsflaeche geprueft. Danach das vorhandene Projekt-Gate ausfuehren.
- Screenshots nur mit synthetischen Pfaden und Daten erstellen:
  breite/schmale Ansicht, helle/dunkle Darstellung, Vorschau, Lauf und Fehler.
  Zusaetzlich echtes Maximieren unter KDE/Wayland und Monitorwechsel testen.

Uebergabeziel: Zuerst Paket 1 abnehmen. Paket 2 erst beginnen, wenn
Layout und Sicherheit stabil sind und das Lesemodell abgestimmt ist.
