"""
Reine Timer-Logik ohne jede GUI.

Diese Datei kennt kein tkinter. Dadurch kannst du sie unabhängig testen
(siehe test_timer_logik.py) und später jederzeit eine andere Oberfläche
darauf setzen.
"""

import time
from enum import Enum


class Zustand(Enum):
    """Die vier möglichen Zustände des Timers."""

    BEREIT = "BEREIT"
    LAEUFT = "LAEUFT"
    PAUSIERT = "PAUSIERT"
    GESTOPPT = "GESTOPPT"


def formatiere_zeit(sekunden: float) -> str:
    """
    Wandelt eine Dauer in Sekunden in den Anzeigetext um.

    Unter einer Stunde:  M:SS.mmm    (z. B. "7:03.412")
    Ab einer Stunde:     H:MM:SS.mmm (z. B. "1:07:03.412")
    """
    if sekunden < 0:
        sekunden = 0.0

    # Erst in ganze Millisekunden umrechnen, danach nur noch mit ganzen
    # Zahlen rechnen. So kann die Anzeige nicht durch Rundungsfehler
    # kurzzeitig auf z. B. "60" Sekunden springen.
    gesamt_ms = int(sekunden * 1000)

    millisekunden = gesamt_ms % 1000
    gesamt_sekunden = gesamt_ms // 1000
    sek = gesamt_sekunden % 60
    gesamt_minuten = gesamt_sekunden // 60
    minuten = gesamt_minuten % 60
    stunden = gesamt_minuten // 60

    if stunden > 0:
        return f"{stunden}:{minuten:02d}:{sek:02d}.{millisekunden:03d}"
    return f"{minuten}:{sek:02d}.{millisekunden:03d}"


def lies_zeit(text: str) -> float | None:
    """
    Wandelt eine von Hand eingegebene Zeit in Sekunden um.

    Erlaubt sind ein bis drei durch ":" getrennte Teile, der letzte davon
    mit Nachkommastellen. Komma und Punkt gelten beide als Dezimaltrenner,
    damit die deutsche Tastatur nicht stört.

        "12"          ->    12.0     (Sekunden)
        "1:23"        ->    83.0
        "1:23,5"      ->    83.5
        "2:03:04.567" -> 7384.567

    Gibt None zurück, wenn sich der Text nicht deuten lässt.
    """
    if not isinstance(text, str):
        return None

    text = text.strip().replace(",", ".")
    if not text:
        return None

    teile = text.split(":")
    if len(teile) > 3:
        return None

    # Nur der letzte Teil darf Nachkommastellen haben.
    for teil in teile[:-1]:
        if not teil.strip().isdigit():
            return None

    try:
        werte = [float(teil) for teil in teile]
    except ValueError:
        return None

    if any(wert < 0 for wert in werte):
        return None

    # Minuten und Sekunden dürfen 59 nicht überschreiten, sonst wäre die
    # Eingabe mehrdeutig ("1:70" wäre entweder falsch oder 2:10 gemeint).
    if len(werte) >= 2 and any(wert >= 60 for wert in werte[1:]):
        return None

    sekunden = 0.0
    for wert in werte:
        sekunden = sekunden * 60 + wert
    return sekunden


class Timer:
    """
    Der eigentliche Timer als Zustandsautomat.

    Zeitmessung: Wir zählen nichts hoch. Stattdessen merken wir uns
    - _start_zeitpunkt: wann der aktuell laufende Abschnitt begonnen hat
    - _angesammelt:     wie viel Zeit aus früheren Abschnitten (vor Pausen
                        oder vor einem Stop) schon zusammengekommen ist

    Die aktuelle Zeit ist immer eine frische Rechnung:
        jetzt - _start_zeitpunkt + _angesammelt
    Damit kann die Anzeige nicht driften, egal wie oft oder wie unregelmäßig
    sie aktualisiert wird.

    Als Uhr dient time.perf_counter(): monoton, hohe Auflösung, und sie
    springt nicht, wenn Windows die Systemuhr mit dem Zeitserver abgleicht.
    Ihr absoluter Wert ist bedeutungslos, nur Differenzen zählen.
    """

    def __init__(self) -> None:
        self.zustand = Zustand.BEREIT
        self._start_zeitpunkt: float | None = None
        self._angesammelt: float = 0.0

    # ------------------------------------------------------------------
    # Zeit auslesen
    # ------------------------------------------------------------------

    def verstrichene_zeit(self) -> float:
        """Aktuelle Laufzeit in Sekunden (als Kommazahl)."""
        if self.zustand is Zustand.LAEUFT and self._start_zeitpunkt is not None:
            return time.perf_counter() - self._start_zeitpunkt + self._angesammelt
        # In BEREIT, PAUSIERT und GESTOPPT steht die Zeit still, dann ist
        # der angesammelte Wert bereits die vollständige Antwort.
        return self._angesammelt

    def formatierte_zeit(self) -> str:
        """Aktuelle Laufzeit als fertiger Anzeigetext."""
        return formatiere_zeit(self.verstrichene_zeit())

    # ------------------------------------------------------------------
    # Abfragen: welche Aktion ist im aktuellen Zustand erlaubt?
    # Die GUI nutzt das, um Buttons auszugrauen.
    # ------------------------------------------------------------------

    def kann_starten(self) -> bool:
        # Aus BEREIT beginnt ein neuer Lauf bei 0, aus GESTOPPT wird der
        # eingefrorene Lauf fortgesetzt.
        return self.zustand in (Zustand.BEREIT, Zustand.GESTOPPT)

    def kann_pausieren(self) -> bool:
        return self.zustand in (Zustand.LAEUFT, Zustand.PAUSIERT)

    def kann_stoppen(self) -> bool:
        return self.zustand in (Zustand.LAEUFT, Zustand.PAUSIERT)

    def kann_zuruecksetzen(self) -> bool:
        # Reset ist immer erlaubt. In BEREIT passiert dabei schlicht nichts
        # Sichtbares, deshalb blenden wir den Button dort trotzdem nicht aus.
        return True

    def startet_neuen_lauf(self) -> bool:
        """
        True, wenn ein Start jetzt bei 0 beginnen würde, False, wenn er
        einen gestoppten Lauf fortsetzen würde. Die GUI beschriftet den
        Button danach mit "Start" bzw. "Weiter".
        """
        return self.zustand is Zustand.BEREIT

    # ------------------------------------------------------------------
    # Aktionen. Jede gibt True zurück, wenn sie im aktuellen Zustand
    # tatsächlich etwas bewirkt hat, sonst False. Ein unerlaubter Aufruf
    # ist also kein Fehler, er wird einfach ignoriert.
    # ------------------------------------------------------------------

    def start(self) -> bool:
        """
        BEREIT   -> LAEUFT: die Zeit beginnt bei 0.
        GESTOPPT -> LAEUFT: die Zeit läuft ab dem eingefrorenen Wert weiter.

        Der Unterschied liegt allein darin, ob _angesammelt auf 0 gesetzt
        wird. Die Zeit zwischen Stop und erneutem Start zählt genauso wenig
        mit wie eine Pause, weil dazwischen kein Abschnitt lief.
        """
        if self.zustand is Zustand.BEREIT:
            self._angesammelt = 0.0
        elif self.zustand is not Zustand.GESTOPPT:
            # Aus LAEUFT oder PAUSIERT heraus tut Start nichts. Sonst würde
            # ein versehentlicher Hotkey-Druck den laufenden Lauf verfälschen.
            return False

        self._start_zeitpunkt = time.perf_counter()
        self.zustand = Zustand.LAEUFT
        return True

    def pause(self) -> bool:
        """
        LAEUFT -> PAUSIERT (Zeit friert ein)
        PAUSIERT -> LAEUFT (Zeit läuft weiter, die Pause zählt nicht mit)
        """
        if self.zustand is Zustand.LAEUFT:
            # Den bisher gelaufenen Abschnitt einsammeln und die Uhr loslassen.
            self._angesammelt += time.perf_counter() - self._start_zeitpunkt
            self._start_zeitpunkt = None
            self.zustand = Zustand.PAUSIERT
            return True

        if self.zustand is Zustand.PAUSIERT:
            # Neuer Abschnitt ab jetzt. Die Dauer der Pause taucht nirgends
            # auf, weil sie zwischen zwei Abschnitten liegt.
            self._start_zeitpunkt = time.perf_counter()
            self.zustand = Zustand.LAEUFT
            return True

        return False

    def stop(self) -> bool:
        """
        LAEUFT oder PAUSIERT -> GESTOPPT. Die Zeit friert ein.

        "Endgültig" ist das nicht mehr: Mit Start kann der Lauf von hier aus
        fortgesetzt werden. Für einen frischen Lauf bei 0 erst Reset drücken.
        """
        if not self.kann_stoppen():
            return False
        if self.zustand is Zustand.LAEUFT:
            self._angesammelt += time.perf_counter() - self._start_zeitpunkt
        self._start_zeitpunkt = None
        self.zustand = Zustand.GESTOPPT
        return True

    def setze_zeit(self, sekunden: float) -> bool:
        """
        Setzt die Zeit von Hand auf einen bestimmten Wert.

        Der Zustand bleibt erhalten, nur der Zählerstand ändert sich:
        Ein laufender Timer läuft ab dem neuen Wert weiter, ein pausierter
        bleibt stehen. Aus BEREIT wird GESTOPPT - "bereit" heißt ja gerade,
        dass die Uhr auf null steht, und das stimmt dann nicht mehr.
        """
        if sekunden < 0:
            return False

        self._angesammelt = float(sekunden)
        if self.zustand is Zustand.LAEUFT:
            # Neuer Bezugspunkt, sonst käme die bisher gelaufene Zeit obendrauf.
            self._start_zeitpunkt = time.perf_counter()
        else:
            self._start_zeitpunkt = None
            if self.zustand is Zustand.BEREIT:
                self.zustand = Zustand.GESTOPPT
        return True

    def zuruecksetzen(self) -> bool:
        """Aus jedem Zustand -> BEREIT. Anzeige zurück auf 0."""
        self._start_zeitpunkt = None
        self._angesammelt = 0.0
        self.zustand = Zustand.BEREIT
        return True
