# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

Minimaler Speedrun-Timer für Windows (Python 3.12+, tkinter, pynput). Bewusst
reduziert: keine Splits, keine Bestzeiten, kein Netzwerk.

## Sprache im Code

Kommentare, Docstrings und GUI-Texte sind **auf Deutsch mit echten Umlauten**
(alle Dateien sind UTF-8). Bezeichner sind ebenfalls deutsch, aber ASCII
transkribiert: `Zustand.LAEUFT`, `zuruecksetzen()`, `_baue_oberflaeche()`,
`oeffne_einstellungen()`. Diese Trennung bitte beibehalten — Umlaute in
Texten, ASCII in Namen.

## Befehle

```powershell
pip install -r requirements.txt      # nur pynput; tkinter ist in der Stdlib
python main.py                       # Programm starten
python test_timer_logik.py           # alle Logiktests
python -c "import test_timer_logik as t; t.test_weiterlaufen_nach_stop()"   # ein einzelner Test
```

Die Tests kommen ohne pytest aus: `test_timer_logik.py` sammelt am Dateiende
selbst alle `test_*`-Funktionen ein. Ein Import der Datei führt nichts aus,
deshalb funktioniert der Einzelaufruf oben.

Es gibt keinen Linter und keinen Build-Schritt.

## Architektur

Abhängigkeiten laufen strikt in eine Richtung:

```
timer_logik.py   nur time + enum, kennt weder tkinter noch pynput
stil.py          nur Konstanten, hängt von nichts ab
hotkeys.py       pynput + json; fasst NIE ein Widget an
einstellungen.py -> hotkeys, stil
zeit_eingabe.py  -> timer_logik, stil
main.py          -> timer_logik, hotkeys, einstellungen, zeit_eingabe, stil
```

Auch die Zeiteingabe hält sich an die Trennung: `lies_zeit()` (Text →
Sekunden) steht in `timer_logik.py` und ist ohne GUI getestet, das Fenster in
`zeit_eingabe.py` ruft sie nur auf.

`stil.py` existiert ausschließlich, damit Haupt- und Einstellungsfenster
dieselben Farben teilen können, ohne dass `main` und `einstellungen` sich
gegenseitig importieren müssten.

### Vier Invarianten, die nicht verletzt werden dürfen

**1. `timer_logik.py` bleibt GUI-frei.** Der ganze Sinn der Aufteilung ist,
dass die Logik ohne Fenster testbar bleibt.

**2. Kein tkinter-Zugriff aus fremden Threads.** pynput ruft seine Callbacks
in eigenen Threads auf, tkinter ist nicht threadsicher. Jeder Weg zurück in
die GUI läuft über `root.after(0, funktion)` — das ist die einzige
tkinter-Funktion, die von außen aufgerufen werden darf. Betrifft
`HotkeyVerwaltung._erzeuge_weiterleitung` und `HotkeyAufnahme._bei_loslassen`.

**3. Zeit wird nie hochgezählt.** `Timer` merkt sich `_start_zeitpunkt`
(`time.perf_counter()`) und `_angesammelt` und rechnet bei jeder Abfrage
`jetzt - start + angesammelt` frisch aus. Kein `zeit += 0.016` in der
Update-Schleife, kein `time.time()` und kein `datetime` — `perf_counter()` ist
monoton und springt nicht bei einer Zeitsynchronisation.

**4. Aktionen im falschen Zustand tun nichts und geben `False` zurück**,
statt zu werfen. Ein versehentlicher Hotkey darf einen laufenden Run nie
verfälschen. `start()` ist aus BEREIT (beginnt bei 0) *und* aus GESTOPPT
(setzt fort) erlaubt — der einzige Unterschied ist, ob `_angesammelt`
zurückgesetzt wird.

### Hotkey-Format und pynput-Eigenheiten

Kombinationen werden im Textformat von pynput gespeichert (`"<f12>+s"`,
`"<ctrl>+<shift>+s"`) und in `timer_config.json` neben dem Skript abgelegt.

- `HotKey.parse()` liefert rohe `KeyCode`-Objekte mit vk-Nummer, der Listener
  meldet beim Drücken aber `Key`-Enums. Verglichen wird erst nach
  `Listener.canonical()`. Wer Hotkey-Treffer testen will, muss `canonical()`
  selbst anwenden, sonst löst scheinbar nichts aus.
- Windows meldet Strg+Buchstabe als Steuerzeichen `\x01`–`\x1a`.
  `taste_zu_text()` rechnet das auf den Buchstaben zurück, sonst wäre Strg+S
  nicht belegbar.
- Linke und rechte Modifier werden über `MODIFIER_VEREINHEITLICHUNG`
  zusammengefasst, sonst reagiert ein mit links belegter Hotkey nicht rechts.
- F-Tasten funktionieren als Haltetaste (Standard ist F12+S/P/X/R), obwohl sie
  keine echten Modifier sind.
- pynput fängt Tasten ab, **blockiert sie aber nicht** — sie erreichen das
  Spiel zusätzlich.

Beim Neubelegen wird der globale Listener angehalten (`hotkeys.stoppe()`),
sonst löst die gedrückte Tastenkombination noch die alten Hotkeys aus. Er muss
auf jedem Rückweg wieder anlaufen, auch wenn das Fenster mitten in einer
Aufnahme geschlossen wird.

`lade_belegung()` stürzt nie ab: fehlende Datei, kaputtes JSON, unsinnige oder
doppelt vergebene Einträge führen still zur Standardbelegung.

### Skalierende Zeitanzeige

Die Schriftgröße der Zeit wird aus der verfügbaren Fläche berechnet
(`_passe_schrift_an`), nicht umgekehrt. Das ergibt eine Rückkopplung, die
sich ohne Gegenmaßnahme endlos hochschaukelt — größere Schrift, größerer
Bereich, noch größere Schrift; das Fenster hängt dann schon beim Aufbau.

Unterbrochen wird sie durch `self.zeit_bereich.pack_propagate(False)`: Der
Frame um die Zeitanzeige übernimmt nicht mehr die Größe seines Inhalts,
sondern bekommt sie vom Fenster. **Diese Zeile darf nicht entfernt werden.**
Die `width`/`height` des Frames dienen nur noch als natürliche Größe, aus der
tkinter beim Start und bei `geometry("")` die Fenstergröße ableitet.

Gerechnet wird mit der **Ziffernhöhe**, nicht mit `linespace`. Die Zeilenhöhe
einer Schrift reicht von den Oberlängen bis unter die Grundlinie; Ziffern
nutzen davon nur rund 60 % (`ZIFFERN_ANTEIL`, an gerenderten Pixeln
nachgemessen). Mit `linespace` blieben über und unter der Zeit etwa 25 % der
Fensterhöhe ungenutzt.

Im Kompaktmodus wird die Fensterhöhe zusätzlich aus der Breite berechnet
(`_kompakte_hoehe`) statt frei mitskaliert — sonst entsteht Leerraum, sobald
das Fenster höher ist, als die Schriftgröße braucht.

Schriften skalieren linear, deshalb wird der Text einmal in
`SCHRIFT_REFERENZ` vermessen und daraus hochgerechnet, statt Größen
durchzuprobieren. Die Neuberechnung läuft nur bei Größenänderung und bei
geänderter Textlänge (ab 10 Minuten, ab einer Stunde) — nicht 60-mal pro
Sekunde.

### Kompaktmodus

`overrideredirect(True)` entfernt die gesamte Fensterdekoration. Daraus
folgen drei Dinge, die alle in `main.py` behandelt sind:

- Das Fenster verschwindet aus der Taskleiste. Deshalb wird `-topmost` im
  Kompaktmodus erzwungen und beim Zurückschalten wieder auf den Wert der
  Checkbox gesetzt — sonst wäre das Fenster hinter einem Spiel unerreichbar.
- Es gibt kein X mehr und keinen Rahmen zum Ziehen. Ersatz sind Maus-Bindings
  (`<B1-Motion>`) und ein Rechtsklick-Menü mit „Beenden". Ohne diesen Ausweg
  könnte man sich aussperren, falls der Hotkey nicht greift.
- Nach `overrideredirect(False)` fehlt der Taskleisteneintrag, bis das Fenster
  einmal `withdraw()`/`deiconify()` durchlaufen hat.

Beim Zurückschalten müssen die Elemente in derselben Reihenfolge wie im
Aufbau gepackt werden — `pack()` hängt immer hinten an.

## Fallstricke beim Testen der GUI

- **`root.after()` aus einem fremden Thread wirft `RuntimeError: main thread
  is not in main loop`, wenn kein `mainloop` läuft.** Für Thread-Tests reicht
  `root.update()` nicht, es braucht einen echten `root.mainloop()` mit
  `root.after(...)`-Schritten. (Im Betrieb tritt der Fehler nur im
  Sekundenbruchteil beim Schließen auf und wird dort abgefangen.)
- Tests, die die Konfiguration schreiben, müssen vorher
  `hotkeys.KONFIG_DATEI` auf eine Testdatei umbiegen — sonst wird die echte
  `timer_config.json` überschrieben.
- `messagebox.showerror` blockiert; in Tests ersetzen.
- Die vier Hauptbuttons haben eine feste `width`, weil ihre Beschriftung
  zwischen "Start"/"Weiter" bzw. "Pause"/"Weiter" wechselt. Ohne feste Breite
  springt die Fensterbreite bei jedem Zustandswechsel.

## Repository

`timer_config.json` und `__pycache__/` sind über `.gitignore` ausgenommen.
Die Konfigurationsdatei entsteht erst beim ersten Ändern eines Hotkeys; in
einem frischen Klon fehlt sie, und das Programm startet mit der
Standardbelegung.
