"""
Gespeicherte Timerstände - Verwaltung und Datei, ganz ohne GUI.

Ein "Stand" ist ein benannter Zeitwert, den du später wieder aufnehmen
kannst: Name, Sekunden und der Zeitpunkt des Speicherns. Abgelegt wird alles
in timer_staende.json neben diesem Skript.

Diese Datei kennt kein tkinter - genau wie timer_logik.py. Dadurch lässt sich
das Speichern und Laden ohne Fenster testen (siehe test_staende.py), und das
Fenster in staende_fenster.py ruft hier nur noch fertige Funktionen auf.

Zur Sicherheit: Der Zeitstempel hier ist reine Beschriftung für die Liste.
Für die Zeitmessung selbst wird er nie benutzt - dafür bleibt allein
time.perf_counter() in timer_logik.py zuständig.
"""

import json
import re
from datetime import datetime
from pathlib import Path

# Die Datei liegt neben dem Skript, nicht im aktuellen Arbeitsverzeichnis.
# Sonst läge sie mal hier und mal dort, je nachdem aus welchem Ordner heraus
# du "python main.py" aufrufst.
STAENDE_DATEI = Path(__file__).with_name("timer_staende.json")

# Grenzen, damit die Liste übersichtlich und die Datei klein bleibt.
MAX_NAME_LAENGE = 40
MAX_STAENDE = 100

# Vorschlag für den Namen beim Speichern: "Lauf 1", "Lauf 2", ...
NAME_VORLAGE = "Lauf"


# ----------------------------------------------------------------------
# Namen und einzelne Einträge
# ----------------------------------------------------------------------


def pruefe_name(name) -> str | None:
    """
    Prüft einen eingegebenen Namen und gibt ihn aufgeräumt zurück.

    Leerzeichen am Rand fallen weg. Ein leerer Name, ein zu langer Name oder
    einer mit Zeilenumbrüchen ist nicht brauchbar - dann kommt None zurück.
    """
    if not isinstance(name, str):
        return None

    name = name.strip()
    if not name or len(name) > MAX_NAME_LAENGE:
        return None

    # Steuerzeichen (Zeilenumbruch, Tabulator) würden die Liste zerreißen.
    if not name.isprintable():
        return None

    return name


def gleicher_name(einer: str, anderer: str) -> bool:
    """
    Vergleicht zwei Namen ohne Rücksicht auf Groß- und Kleinschreibung.

    "Lauf 1" und "lauf 1" sollen derselbe Stand sein - sonst hättest du
    versehentlich zwei Einträge, die in der Liste gleich aussehen.
    """
    return einer.casefold() == anderer.casefold()


def finde_stand(staende: list, name: str):
    """Sucht einen Stand nach Namen. Gibt ihn zurück oder None."""
    geprueft = pruefe_name(name)
    if geprueft is None:
        return None

    for stand in staende:
        if gleicher_name(stand["name"], geprueft):
            return stand
    return None


def jetzt_als_text() -> str:
    """
    Aktuelles Datum mit Uhrzeit als Text, z. B. "20.09.2026 14:33".

    Nur als Beschriftung in der Liste gedacht, damit du ältere von neueren
    Ständen unterscheiden kannst.
    """
    return datetime.now().strftime("%d.%m.%Y %H:%M")


def setze_stand(staende: list, name: str, sekunden: float, zeitstempel: str | None = None):
    """
    Legt einen Stand an oder überschreibt den gleichnamigen.

    Gibt eine neue Liste zurück - die übergebene bleibt unverändert. Bei
    unbrauchbarem Namen oder negativer Zeit kommt None zurück, dann wurde
    nichts geändert.

    Ein vorhandener Eintrag behält seinen Platz in der Liste, statt ans Ende
    zu rutschen. So springt die Anzeige beim Überschreiben nicht herum.
    """
    geprueft = pruefe_name(name)
    if geprueft is None:
        return None

    try:
        sekunden = float(sekunden)
    except (TypeError, ValueError):
        return None
    if sekunden < 0:
        return None

    neuer = {
        "name": geprueft,
        "sekunden": sekunden,
        "gespeichert_am": zeitstempel if zeitstempel is not None else jetzt_als_text(),
    }

    ergebnis = []
    ersetzt = False
    for stand in staende:
        if gleicher_name(stand["name"], geprueft):
            ergebnis.append(neuer)
            ersetzt = True
        else:
            ergebnis.append(dict(stand))

    if not ersetzt:
        if len(ergebnis) >= MAX_STAENDE:
            # Voll: Der älteste Eintrag macht Platz für den neuen.
            ergebnis.pop(0)
        ergebnis.append(neuer)

    return ergebnis


def entferne_stand(staende: list, name: str) -> list:
    """
    Entfernt den Stand mit diesem Namen.

    Gibt eine neue Liste zurück. Gibt es den Namen gar nicht, ist die Liste
    einfach unverändert - das ist kein Fehler.
    """
    geprueft = pruefe_name(name)
    if geprueft is None:
        return [dict(stand) for stand in staende]

    return [dict(stand) for stand in staende if not gleicher_name(stand["name"], geprueft)]


def naechster_freier_name(staende: list, vorlage: str = NAME_VORLAGE) -> str:
    """
    Schlägt einen noch unbenutzten Namen vor: "Lauf 1", "Lauf 2", ...

    Damit steht im Speichern-Fenster schon etwas Sinnvolles im Feld und du
    kannst einfach Eingabe drücken.
    """
    nummer = 1
    while finde_stand(staende, f"{vorlage} {nummer}") is not None:
        nummer += 1
    return f"{vorlage} {nummer}"


# ----------------------------------------------------------------------
# Suche
#
# Bewusst ohne Filterauswahl: Man tippt einfach los, und gesucht wird in
# Name und Datum gleichzeitig. "any 20.09" findet den Lauf "Any% Übung" vom
# 20. September, ohne dass man vorher irgendwo "Name" oder "Datum" anklicken
# müsste.
# ----------------------------------------------------------------------


# Führende Nullen am Anfang einer Zahl. \b sorgt dafür, dass nur der Anfang
# gemeint ist: In "2026" steht die 0 mitten in der Zahl und bleibt stehen,
# in "09" steht sie vorn und fällt weg.
_FUEHRENDE_NULL = re.compile(r"\b0+(\d)")


def _such_text(text: str) -> str:
    """
    Bringt Text in die Form, in der verglichen wird.

    Klein geschrieben und ohne führende Nullen in Zahlen. Dadurch findet
    sowohl "20.9" als auch "20.09" den Eintrag vom 20.09. - beides schreibt
    man im Alltag, und niemand sollte raten müssen, welche Form gemeint ist.
    """
    return _FUEHRENDE_NULL.sub(r"\1", text.casefold())


def passt_zur_suche(stand: dict, suche: str) -> bool:
    """
    Prüft, ob ein Stand zum Suchtext passt.

    Der Suchtext wird an Leerzeichen zerlegt; jedes Wort muss irgendwo in
    Name oder Datum vorkommen. Mehrere Wörter grenzen also weiter ein, statt
    mehr Treffer zu liefern. Eine leere Suche passt auf alles.
    """
    if not isinstance(suche, str):
        return True

    begriffe = _such_text(suche).split()
    if not begriffe:
        return True

    durchsucht = _such_text(f"{stand.get('name', '')} {stand.get('gespeichert_am', '')}")
    return all(begriff in durchsucht for begriff in begriffe)


def filtere(staende: list, suche: str) -> list:
    """Gibt nur die Stände zurück, die zum Suchtext passen."""
    return [stand for stand in staende if passt_zur_suche(stand, suche)]


# ----------------------------------------------------------------------
# Datei lesen und schreiben
# ----------------------------------------------------------------------


def bereinige(rohdaten) -> list:
    """
    Macht aus dem, was in der Datei stand, eine verlässliche Liste.

    Alles Unbrauchbare fliegt still raus: falsche Datentypen, leere oder zu
    lange Namen, negative Zeiten, doppelte Namen. Lieber ein Eintrag weniger
    als ein Absturz beim Start.
    """
    if not isinstance(rohdaten, list):
        return []

    ergebnis = []
    for eintrag in rohdaten:
        if not isinstance(eintrag, dict):
            continue

        name = pruefe_name(eintrag.get("name"))
        if name is None:
            continue

        sekunden = eintrag.get("sekunden")
        # bool ist in Python ein Sonderfall von int - True wäre sonst 1.0.
        if isinstance(sekunden, bool) or not isinstance(sekunden, (int, float)):
            continue
        if sekunden < 0:
            continue

        zeitstempel = eintrag.get("gespeichert_am")
        if not isinstance(zeitstempel, str):
            zeitstempel = ""

        # Doppelte Namen: Der erste gewinnt, der zweite wäre in der Liste
        # nicht mehr von ihm zu unterscheiden.
        if any(gleicher_name(vorhandener["name"], name) for vorhandener in ergebnis):
            continue

        ergebnis.append(
            {"name": name, "sekunden": float(sekunden), "gespeichert_am": zeitstempel}
        )

        if len(ergebnis) >= MAX_STAENDE:
            break

    return ergebnis


def lade_staende() -> list:
    """
    Lädt die gespeicherten Stände aus timer_staende.json.

    Stürzt nie ab: Fehlt die Datei (völlig normal vor dem ersten Speichern),
    ist sie kein gültiges JSON oder steht Unsinn darin, kommt eine leere
    Liste zurück.
    """
    try:
        with open(STAENDE_DATEI, "r", encoding="utf-8") as datei:
            inhalt = json.load(datei)
    except FileNotFoundError:
        return []
    except (json.JSONDecodeError, OSError, UnicodeDecodeError):
        return []

    if not isinstance(inhalt, dict):
        return []

    return bereinige(inhalt.get("staende"))


def speichere_staende(staende: list) -> bool:
    """
    Schreibt die Stände nach timer_staende.json.

    Gibt False zurück, wenn das Schreiben fehlschlägt (z. B. weil der Ordner
    schreibgeschützt ist). Das Programm läuft dann weiter, merkt sich die
    Änderung aber nur bis zum Beenden.
    """
    inhalt = {"staende": bereinige(staende)}
    try:
        with open(STAENDE_DATEI, "w", encoding="utf-8") as datei:
            json.dump(inhalt, datei, indent=2, ensure_ascii=False)
            datei.write("\n")
        return True
    except OSError:
        return False
