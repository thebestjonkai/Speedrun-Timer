"""
Kleines Testskript fuer die Timer-Logik - ganz ohne GUI.

Ausfuehren mit:  python test_timer_logik.py

Es braucht keine Zusatzpakete. Jeder Test ist eine Funktion, die mit
"assert" eine Behauptung aufstellt. Stimmt sie nicht, bricht der Test mit
einer Fehlermeldung ab.
"""

import time

from timer_logik import Timer, Zustand, formatiere_zeit


def test_formatierung():
    assert formatiere_zeit(0) == "0:00.000"
    assert formatiere_zeit(1.5) == "0:01.500"
    assert formatiere_zeit(65.123) == "1:05.123"
    # Ab einer Stunde kommt die Stundenstelle dazu.
    assert formatiere_zeit(3600) == "1:00:00.000"
    assert formatiere_zeit(3661.007) == "1:01:01.007"
    # Negative Werte duerfen nicht zu kaputtem Text fuehren.
    assert formatiere_zeit(-5) == "0:00.000"


def test_startzustand():
    t = Timer()
    assert t.zustand is Zustand.BEREIT
    assert t.verstrichene_zeit() == 0.0


def test_start_laesst_zeit_laufen():
    t = Timer()
    assert t.start() is True
    assert t.zustand is Zustand.LAEUFT
    time.sleep(0.05)
    assert t.verstrichene_zeit() >= 0.04


def test_zweiter_start_wird_ignoriert():
    """Start ist nur aus BEREIT erlaubt - sonst wuerde die Zeit zurueckspringen."""
    t = Timer()
    t.start()
    time.sleep(0.05)
    assert t.start() is False
    assert t.verstrichene_zeit() >= 0.04


def test_pause_friert_zeit_ein():
    t = Timer()
    t.start()
    time.sleep(0.05)
    t.pause()
    assert t.zustand is Zustand.PAUSIERT

    zeit_bei_pause = t.verstrichene_zeit()
    time.sleep(0.05)
    # Waehrend der Pause darf sich der Wert nicht veraendern.
    assert t.verstrichene_zeit() == zeit_bei_pause


def test_pausendauer_zaehlt_nicht_mit():
    t = Timer()
    t.start()
    time.sleep(0.05)
    t.pause()
    time.sleep(0.20)  # lange Pause
    t.pause()  # weiter
    assert t.zustand is Zustand.LAEUFT
    time.sleep(0.05)

    # Gelaufen sind rund 0,10 s. Die 0,20 s Pause duerfen nicht auftauchen.
    verstrichen = t.verstrichene_zeit()
    assert 0.08 < verstrichen < 0.18, f"unerwartet: {verstrichen}"


def test_stop_friert_endgueltig_ein():
    t = Timer()
    t.start()
    time.sleep(0.05)
    t.stop()
    assert t.zustand is Zustand.GESTOPPT

    endzeit = t.verstrichene_zeit()
    time.sleep(0.05)
    assert t.verstrichene_zeit() == endzeit
    # Aus GESTOPPT heraus geht nur noch Reset.
    assert t.start() is False
    assert t.pause() is False
    assert t.stop() is False


def test_stop_aus_pause():
    t = Timer()
    t.start()
    time.sleep(0.05)
    t.pause()
    zeit_bei_pause = t.verstrichene_zeit()
    assert t.stop() is True
    assert t.zustand is Zustand.GESTOPPT
    assert t.verstrichene_zeit() == zeit_bei_pause


def test_reset_aus_jedem_zustand():
    for aufbau in (
        lambda t: None,                      # BEREIT
        lambda t: t.start(),                 # LAEUFT
        lambda t: (t.start(), t.pause()),    # PAUSIERT
        lambda t: (t.start(), t.stop()),     # GESTOPPT
    ):
        t = Timer()
        aufbau(t)
        t.zuruecksetzen()
        assert t.zustand is Zustand.BEREIT
        assert t.verstrichene_zeit() == 0.0
        # Nach dem Reset muss ein neuer Lauf moeglich sein.
        assert t.start() is True


def test_neustart_beginnt_wieder_bei_null():
    t = Timer()
    t.start()
    time.sleep(0.05)
    t.stop()
    t.zuruecksetzen()
    t.start()
    assert t.verstrichene_zeit() < 0.02


if __name__ == "__main__":
    # Alle Funktionen einsammeln, deren Name mit "test_" beginnt.
    tests = [
        (name, funktion)
        for name, funktion in sorted(globals().items())
        if name.startswith("test_") and callable(funktion)
    ]

    fehler = 0
    for name, funktion in tests:
        try:
            funktion()
            print(f"[ok]     {name}")
        except AssertionError as ausnahme:
            fehler += 1
            print(f"[FEHLER] {name}: {ausnahme}")

    print(f"\n{len(tests) - fehler} von {len(tests)} Tests bestanden.")
