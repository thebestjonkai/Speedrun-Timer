"""
Globale Hotkeys mit pynput - Belegung, Aufnahme neuer Tasten, Speichern.

"Global" heißt: Die Tasten werden systemweit abgefangen, auch wenn ein Spiel
im Vordergrund läuft und unser Fenster gar keinen Fokus hat.

DER WICHTIGE PUNKT IN DIESER DATEI
pynput horcht in einem eigenen Hintergrund-Thread auf die Tastatur und ruft
seine Rückmeldungen auch dort auf. tkinter ist aber nicht threadsicher: Wenn
wir von diesem fremden Thread aus ein Label beschriften, kann das Programm
einfrieren oder abstürzen - oft erst nach Minuten, was die Fehlersuche
scheußlich macht.

Deshalb fasst diese Datei NIE ein GUI-Element an. Sie schiebt die Aktion mit
root.after(0, funktion) in die Warteschlange von tkinter. Der GUI-Thread
arbeitet sie beim nächsten Durchlauf ab - also im richtigen Thread.
root.after ist die einzige tkinter-Funktion, die man von außen aufrufen darf.
"""

import json
from pathlib import Path

from pynput import keyboard

# Die Konfigurationsdatei liegt neben diesem Skript, nicht im aktuellen
# Arbeitsverzeichnis. Sonst läge sie mal hier und mal dort, je nachdem aus
# welchem Ordner heraus du "python main.py" aufrufst.
KONFIG_DATEI = Path(__file__).with_name("timer_config.json")

# Die vier Aktionen. Die Reihenfolge bestimmt auch die Reihenfolge im
# Einstellungsfenster.
AKTIONEN = ("start", "pause", "stop", "reset", "kompakt")

# Anzeigenamen für die Oberfläche.
AKTION_BESCHRIFTUNG = {
    "start": "Start",
    "pause": "Pause",
    "stop": "Stop",
    "reset": "Reset",
    "kompakt": "Kompakt",
}

# Standardbelegung in der Schreibweise von pynput:
# Sondertasten stehen in spitzen Klammern, Kombinationen werden mit "+"
# verbunden. F12 dient hier als Haltetaste, weil Spiele die einzelnen
# F-Tasten oft selbst belegen.
STANDARD_BELEGUNG = {
    "start": "<f12>+s",
    "pause": "<f12>+p",
    "stop": "<f12>+x",
    "reset": "<f12>+r",
    "kompakt": "<f12>+k",
}

# Linke und rechte Varianten derselben Taste fassen wir zusammen. Sonst
# würde ein mit der linken Strg-Taste belegter Hotkey nicht auf die rechte
# reagieren.
MODIFIER_VEREINHEITLICHUNG = {
    "ctrl_l": "ctrl",
    "ctrl_r": "ctrl",
    "alt_l": "alt",
    "alt_r": "alt",
    "shift_l": "shift",
    "shift_r": "shift",
    "cmd_l": "cmd",
    "cmd_r": "cmd",
}

# Modifier stehen in der Anzeige immer vorn, in dieser Reihenfolge.
MODIFIER_REIHENFOLGE = ("ctrl", "alt", "alt_gr", "shift", "cmd")

# Übersetzung der pynput-Namen in lesbare deutsche Tastenbezeichnungen.
LESBARE_NAMEN = {
    "ctrl": "Strg",
    "alt": "Alt",
    "alt_gr": "AltGr",
    "shift": "Umschalt",
    "cmd": "Windows",
    "space": "Leertaste",
    "enter": "Eingabe",
    "esc": "Esc",
    "tab": "Tab",
    "backspace": "Rücktaste",
    "delete": "Entf",
    "insert": "Einfg",
    "home": "Pos1",
    "end": "Ende",
    "page_up": "Bild auf",
    "page_down": "Bild ab",
    "up": "Pfeil hoch",
    "down": "Pfeil runter",
    "left": "Pfeil links",
    "right": "Pfeil rechts",
    "print_screen": "Druck",
    "num_lock": "Num",
    "scroll_lock": "Rollen",
    "caps_lock": "Feststell",
    "menu": "Menü",
    "pause": "Pause-Taste",
}

# Tasten des Nummernblocks meldet Windows nur als rohe Tastencodes. Für
# Hotkeys sind sie besonders praktisch, weil Spiele sie selten belegen -
# also geben wir ihnen wenigstens in der Anzeige einen lesbaren Namen.
VK_LESBAR = {
    "96": "Num 0", "97": "Num 1", "98": "Num 2", "99": "Num 3", "100": "Num 4",
    "101": "Num 5", "102": "Num 6", "103": "Num 7", "104": "Num 8", "105": "Num 9",
    "106": "Num *", "107": "Num +", "109": "Num -", "110": "Num ,", "111": "Num /",
}


# ----------------------------------------------------------------------
# Umwandlung zwischen Tasten, Speicherformat und Anzeigetext
# ----------------------------------------------------------------------


def lesbare_kombination(kombination: str) -> str:
    """
    Macht aus der pynput-Schreibweise einen anzeigbaren Text.

    "<f12>+s"           -> "F12+S"
    "<ctrl>+<shift>+s"  -> "Strg+Umschalt+S"
    """
    teile = []
    for roh in kombination.split("+"):
        taste = roh.strip().strip("<>")
        if taste in LESBARE_NAMEN:
            teile.append(LESBARE_NAMEN[taste])
        elif len(taste) == 1:
            teile.append(taste.upper())
        elif taste.isdigit():
            # Reiner Tastencode - Nummernblock kennen wir, alles andere nicht.
            teile.append(VK_LESBAR.get(taste, f"Taste {taste}"))
        else:
            # F-Tasten und alles Unbekannte: F-Tasten ganz groß, Rest
            # mit großem Anfangsbuchstaben.
            teile.append(taste.upper() if taste.startswith("f") else taste.capitalize())
    # Ohne Leerzeichen um das Plus: so bleibt die Anzeige kompakt genug,
    # dass das Timer-Fenster schmal bleibt.
    return "+".join(teile)


def taste_zu_text(taste) -> str:
    """
    Wandelt eine einzelne von pynput gemeldete Taste ins Speicherformat.

    Key.f12                  -> "<f12>"
    Key.ctrl_l               -> "<ctrl>"     (links und rechts gleich)
    KeyCode(char="S")        -> "s"          (immer klein)
    KeyCode(char="\\x13")     -> "s"          (siehe Kommentar unten)

    Gibt "" zurück, wenn die Taste sich nicht sinnvoll abbilden lässt.
    """
    if isinstance(taste, keyboard.Key):
        name = taste.name
        return f"<{MODIFIER_VEREINHEITLICHUNG.get(name, name)}>"

    zeichen = getattr(taste, "char", None)
    if zeichen:
        # Wird eine Buchstabentaste zusammen mit Strg gedrückt, meldet
        # Windows nicht "s", sondern das Steuerzeichen \x13. Die Steuer-
        # zeichen \x01 bis \x1a entsprechen den Buchstaben a bis z, also
        # rechnen wir zurück - sonst ließe sich Strg+S nicht belegen.
        if len(zeichen) == 1 and "\x01" <= zeichen <= "\x1a":
            zeichen = chr(ord(zeichen) + 96)

        zeichen = zeichen.lower()
        # "+", "<" und ">" sind in unserem Speicherformat Sonderzeichen und
        # würden es durcheinanderbringen.
        if zeichen.isprintable() and zeichen not in "+<> ":
            return zeichen

    # Letzter Ausweg: der rohe Tastencode. pynput versteht "<123>".
    if getattr(taste, "vk", None) is not None:
        return f"<{taste.vk}>"
    return ""


def kombination_zu_text(tasten: list) -> str:
    """
    Baut aus mehreren gedrückten Tasten den Speichertext, z. B. "<f12>+s".

    Modifier wandern nach vorn, damit "Strg + S" nicht mal so und mal
    andersherum angezeigt wird.
    """
    teile = [text for text in (taste_zu_text(t) for t in tasten) if text]
    if not teile:
        return ""

    # Doppelte entfernen, Reihenfolge beibehalten.
    ohne_doppelte = list(dict.fromkeys(teile))

    def sortierschluessel(text: str):
        name = text.strip("<>")
        if name in MODIFIER_REIHENFOLGE:
            return (0, MODIFIER_REIHENFOLGE.index(name))
        return (1, 0)

    # sorted ist stabil: Nicht-Modifier behalten ihre Druckreihenfolge.
    return "+".join(sorted(ohne_doppelte, key=sortierschluessel))


def ist_gueltige_kombination(kombination: str) -> bool:
    """Prüft, ob pynput diese Kombination später auch verarbeiten kann."""
    if not isinstance(kombination, str) or not kombination.strip():
        return False
    try:
        return len(keyboard.HotKey.parse(kombination)) > 0
    except (ValueError, KeyError):
        return False


def finde_doppelbelegung(belegung: dict, aktion: str, kombination: str):
    """
    Sucht eine andere Aktion, die bereits auf dieser Kombination liegt.

    Gibt deren Namen zurück oder None, wenn die Kombination frei ist.
    """
    for name, vorhandene in belegung.items():
        if name != aktion and vorhandene == kombination:
            return name
    return None


# ----------------------------------------------------------------------
# Konfigurationsdatei
# ----------------------------------------------------------------------


def lade_belegung() -> dict:
    """
    Lädt die Belegung aus timer_config.json.

    Diese Funktion stürzt nie ab. Fehlt die Datei, ist sie kein gültiges
    JSON, fehlen einzelne Aktionen oder steht Unsinn darin, wird für die
    betroffenen Aktionen die Standardbelegung genommen.
    """
    belegung = dict(STANDARD_BELEGUNG)

    try:
        with open(KONFIG_DATEI, "r", encoding="utf-8") as datei:
            inhalt = json.load(datei)
    except FileNotFoundError:
        # Beim allerersten Start völlig normal.
        return belegung
    except (json.JSONDecodeError, OSError, UnicodeDecodeError):
        # Datei kaputt oder nicht lesbar - lieber mit Standard weitermachen
        # als mit einer Fehlermeldung aussteigen.
        return belegung

    gespeicherte = inhalt.get("hotkeys") if isinstance(inhalt, dict) else None
    if not isinstance(gespeicherte, dict):
        return belegung

    for aktion in AKTIONEN:
        kombination = gespeicherte.get(aktion)
        if ist_gueltige_kombination(kombination):
            belegung[aktion] = kombination

    # Sind durch das Bearbeiten von Hand zwei Aktionen auf derselben Taste
    # gelandet, wäre eine davon wirkungslos. Dann lieber komplett zurück
    # auf Standard, das ist nachvollziehbarer als eine halb kaputte Belegung.
    if len(set(belegung.values())) != len(belegung):
        return dict(STANDARD_BELEGUNG)

    return belegung


def speichere_belegung(belegung: dict) -> bool:
    """
    Schreibt die Belegung nach timer_config.json.

    Gibt False zurück, wenn das Schreiben fehlschlägt (z. B. weil der Ordner
    schreibgeschützt ist). Das Programm läuft dann trotzdem weiter, merkt
    sich die Änderung aber nur bis zum Beenden.
    """
    inhalt = {"hotkeys": {aktion: belegung[aktion] for aktion in AKTIONEN if aktion in belegung}}
    try:
        with open(KONFIG_DATEI, "w", encoding="utf-8") as datei:
            json.dump(inhalt, datei, indent=2, ensure_ascii=False)
            datei.write("\n")
        return True
    except OSError:
        return False


# ----------------------------------------------------------------------
# Der laufende Listener
# ----------------------------------------------------------------------


class HotkeyVerwaltung:
    """
    Hält den pynput-Listener und die aktuelle Tastenbelegung.

    Bei jeder Änderung der Belegung wird der Listener gestoppt und neu
    gestartet - pynput kann eine laufende Zuordnung nicht nachträglich ändern.
    """

    def __init__(self, root, aktionen: dict) -> None:
        """
        root:     das tkinter-Hauptfenster (nur für root.after)
        aktionen: Zuordnung Aktionsname -> Funktion, z. B.
                  {"start": fenster.aktion_start, ...}
        """
        self.root = root
        self.aktionen = aktionen
        self.belegung = lade_belegung()
        self._listener = None

    def laeuft(self) -> bool:
        return self._listener is not None

    def starte(self) -> None:
        """
        Startet den Listener mit der aktuellen Belegung.

        Wirft ValueError, wenn pynput eine Kombination nicht versteht.
        """
        self.stoppe()

        zuordnung = {}
        for name, kombination in self.belegung.items():
            if name in self.aktionen:
                zuordnung[kombination] = self._erzeuge_weiterleitung(name)

        listener = keyboard.GlobalHotKeys(zuordnung)
        # Als Daemon markieren, damit dieser Thread Python beim Beenden des
        # Programms nicht am Leben hält.
        listener.daemon = True
        listener.start()
        self._listener = listener

    def stoppe(self) -> None:
        """Beendet den Listener, falls einer läuft."""
        if self._listener is not None:
            self._listener.stop()
            self._listener = None

    def setze_belegung(self, belegung: dict) -> None:
        """Übernimmt eine neue Belegung und startet den Listener neu."""
        self.belegung = dict(belegung)
        self.starte()

    def _erzeuge_weiterleitung(self, name: str):
        """
        Baut die Funktion, die pynput bei einem Tastendruck aufruft.

        Eine eigene Funktion pro Aktion ist nötig, damit jede ihren eigenen
        Namen festhält. Würden wir die Schleifenvariable direkt in einer
        verschachtelten Funktion verwenden, hätten am Ende alle vier
        Weiterleitungen denselben (letzten) Wert.
        """
        aktion = self.aktionen[name]

        def weiterleitung() -> None:
            # ACHTUNG: Diese Zeile läuft im pynput-Thread.
            # Hier darf nichts stehen außer der Übergabe an den GUI-Thread.
            try:
                self.root.after(0, aktion)
            except RuntimeError:
                # Tritt auf, wenn genau in diesem Moment das Fenster schon
                # geschlossen wird und die tkinter-Schleife nicht mehr läuft
                # ("main thread is not in main loop"). Dann gibt es nichts
                # mehr zu tun - der Tastendruck wird einfach verworfen,
                # statt den Listener-Thread mit einem Fehler zu beenden.
                pass

        return weiterleitung


# ----------------------------------------------------------------------
# Aufnahme einer neuen Tastenkombination
# ----------------------------------------------------------------------


class HotkeyAufnahme:
    """
    Horcht auf die nächste Tastenkombination, um sie neu zu belegen.

    Ablauf: Alle gedrückten Tasten werden gesammelt. Sobald die erste davon
    wieder losgelassen wird, gilt die Kombination als vollständig. So kann
    man "F12 gedrückt halten und S tippen" ganz natürlich eingeben.

    Wir horchen bewusst mit pynput und nicht mit den Tasten-Ereignissen von
    tkinter: Nur so sehen wir beim Aufnehmen exakt dieselben Tasten, die der
    Hotkey-Listener später auch sieht.
    """

    def __init__(self, root) -> None:
        self.root = root
        self._listener = None
        self._gedrueckt: list = []
        self._rueckmeldung = None

    def laeuft(self) -> bool:
        return self._listener is not None

    def starte(self, rueckmeldung) -> None:
        """
        Beginnt die Aufnahme.

        rueckmeldung wird später mit dem fertigen Text aufgerufen, z. B.
        "<f12>+s" - und zwar garantiert im GUI-Thread.
        """
        self.stoppe()
        self._rueckmeldung = rueckmeldung
        self._gedrueckt = []
        listener = keyboard.Listener(on_press=self._bei_druck, on_release=self._bei_loslassen)
        listener.daemon = True
        listener.start()
        self._listener = listener

    def stoppe(self) -> None:
        """Bricht die Aufnahme ab."""
        if self._listener is not None:
            self._listener.stop()
            self._listener = None
        self._rueckmeldung = None
        self._gedrueckt = []

    # -- die folgenden zwei Methoden laufen im pynput-Thread! --

    def _bei_druck(self, taste) -> None:
        if taste not in self._gedrueckt:
            self._gedrueckt.append(taste)

    def _bei_loslassen(self, taste) -> bool:
        """
        Erste losgelassene Taste beendet die Aufnahme.

        Der Rückgabewert False sagt pynput, dass dieser Listener sich
        beenden soll.
        """
        if not self._gedrueckt:
            return True

        kombination = kombination_zu_text(self._gedrueckt)
        rueckmeldung = self._rueckmeldung

        self._listener = None  # der Listener beendet sich gleich selbst
        self._rueckmeldung = None
        self._gedrueckt = []

        if rueckmeldung is not None and kombination:
            try:
                # Wieder der einzige erlaubte Weg zurück in den GUI-Thread.
                self.root.after(0, lambda: rueckmeldung(kombination))
            except RuntimeError:
                pass
        return False
