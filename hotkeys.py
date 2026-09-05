"""
Globale Hotkeys mit pynput.

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

from pynput import keyboard

# Die vier Aktionen. Die Reihenfolge bestimmt später auch die Reihenfolge im
# Einstellungsfenster.
AKTIONEN = ("start", "pause", "stop", "reset")

# Anzeigenamen für die Oberfläche.
AKTION_BESCHRIFTUNG = {
    "start": "Start",
    "pause": "Pause",
    "stop": "Stop",
    "reset": "Reset",
}

# Standardbelegung im Schreibweise-Format von pynput:
# Sondertasten stehen in spitzen Klammern, Kombinationen werden mit "+"
# verbunden, z. B. "<ctrl>+<shift>+s".
STANDARD_BELEGUNG = {
    "start": "<f1>",
    "pause": "<f2>",
    "stop": "<f3>",
    "reset": "<f4>",
}

# Übersetzung der pynput-Namen in lesbare deutsche Tastenbezeichnungen.
LESBARE_NAMEN = {
    "ctrl": "Strg",
    "ctrl_l": "Strg",
    "ctrl_r": "Strg",
    "alt": "Alt",
    "alt_l": "Alt",
    "alt_gr": "AltGr",
    "shift": "Umschalt",
    "shift_l": "Umschalt",
    "shift_r": "Umschalt",
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
    "pause": "Pause-Taste",
}


def lesbare_kombination(kombination: str) -> str:
    """
    Macht aus der pynput-Schreibweise einen anzeigbaren Text.

    "<f1>"              -> "F1"
    "<ctrl>+<shift>+s"  -> "Strg + Umschalt + S"
    """
    teile = []
    for roh in kombination.split("+"):
        taste = roh.strip().strip("<>")
        if taste in LESBARE_NAMEN:
            teile.append(LESBARE_NAMEN[taste])
        elif len(taste) == 1:
            teile.append(taste.upper())
        else:
            # F-Tasten und alles Unbekannte: erster Buchstabe groß.
            teile.append(taste.upper() if taste.startswith("f") else taste.capitalize())
    return " + ".join(teile)


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
        self.belegung = dict(STANDARD_BELEGUNG)
        self._listener = None

    # ------------------------------------------------------------------

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

    # ------------------------------------------------------------------

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
            self.root.after(0, aktion)

        return weiterleitung
