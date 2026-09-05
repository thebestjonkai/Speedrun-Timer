"""
Kleines Testskript für die Timer-Logik - ganz ohne GUI.

Ausführen mit:  python test_timer_logik.py

Es braucht keine Zusatzpakete. Jeder Test ist eine Funktion, die mit
"assert" eine Behauptung aufstellt. Stimmt sie nicht, bricht der Test mit
einer Fehlermeldung ab.
"""

import time

from timer_logik import Timer, Zustand, formatiere_zeit, lies_zeit


def test_formatierung():
    assert formatiere_zeit(0) == "0:00.000"
    assert formatiere_zeit(1.5) == "0:01.500"
    assert formatiere_zeit(65.123) == "1:05.123"
    # Ab einer Stunde kommt die Stundenstelle dazu.
    assert formatiere_zeit(3600) == "1:00:00.000"
    assert formatiere_zeit(3661.007) == "1:01:01.007"
    # Negative Werte dürfen nicht zu kaputtem Text führen.
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
    """Start während des Laufens darf die Zeit nicht zurücksetzen."""
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
    # Während der Pause darf sich der Wert nicht verändern.
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

    # Gelaufen sind rund 0,10 s. Die 0,20 s Pause dürfen nicht auftauchen.
    verstrichen = t.verstrichene_zeit()
    assert 0.08 < verstrichen < 0.18, f"unerwartet: {verstrichen}"


def test_start_waehrend_pause_wird_ignoriert():
    """Auch aus PAUSIERT heraus darf Start nichts anfassen - dafür ist Pause da."""
    t = Timer()
    t.start()
    time.sleep(0.05)
    t.pause()
    zeit_bei_pause = t.verstrichene_zeit()

    assert t.start() is False
    assert t.zustand is Zustand.PAUSIERT
    assert t.verstrichene_zeit() == zeit_bei_pause


def test_stop_friert_zeit_ein():
    t = Timer()
    t.start()
    time.sleep(0.05)
    t.stop()
    assert t.zustand is Zustand.GESTOPPT

    endzeit = t.verstrichene_zeit()
    time.sleep(0.05)
    assert t.verstrichene_zeit() == endzeit
    # Aus GESTOPPT heraus ergeben Pause und ein weiteres Stop keinen Sinn.
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


def test_weiterlaufen_nach_stop():
    """Start setzt einen gestoppten Lauf fort, statt bei 0 zu beginnen."""
    t = Timer()
    t.start()
    time.sleep(0.05)
    t.stop()
    zeit_bei_stop = t.verstrichene_zeit()

    time.sleep(0.20)  # Zeit im gestoppten Zustand darf nicht mitzählen
    assert t.start() is True
    assert t.zustand is Zustand.LAEUFT
    # Direkt nach dem Fortsetzen steht die Zeit noch fast auf dem Stop-Wert.
    assert t.verstrichene_zeit() >= zeit_bei_stop
    assert t.verstrichene_zeit() < zeit_bei_stop + 0.05

    time.sleep(0.05)
    verstrichen = t.verstrichene_zeit()
    assert 0.08 < verstrichen < 0.18, f"unerwartet: {verstrichen}"


def test_mehrfaches_stoppen_und_fortsetzen():
    """Drei kurze Abschnitte mit Stop dazwischen ergeben zusammen die Summe."""
    t = Timer()
    for durchgang in range(3):
        if durchgang == 0:
            t.start()
        else:
            t.start()  # setzt fort
        time.sleep(0.05)
        t.stop()
        time.sleep(0.05)  # Pause zwischen den Abschnitten, zählt nicht mit

    verstrichen = t.verstrichene_zeit()
    assert 0.13 < verstrichen < 0.25, f"unerwartet: {verstrichen}"


def test_startet_neuen_lauf_meldet_richtig():
    """Diese Abfrage steuert die Beschriftung 'Start' bzw. 'Weiter'."""
    t = Timer()
    assert t.startet_neuen_lauf() is True  # BEREIT -> "Start"
    t.start()
    t.stop()
    assert t.startet_neuen_lauf() is False  # GESTOPPT -> "Weiter"
    t.zuruecksetzen()
    assert t.startet_neuen_lauf() is True


def test_zeit_einlesen():
    assert lies_zeit("12") == 12.0
    assert lies_zeit("1:23") == 83.0
    assert lies_zeit("1:23.456") == 83.456
    # Deutsche Tastatur: Komma muss genauso gehen wie Punkt.
    assert lies_zeit("1:23,456") == 83.456
    assert lies_zeit("2:03:04") == 7384.0
    assert lies_zeit("0:00.001") == 0.001
    assert lies_zeit("  1:30  ") == 90.0
    assert lies_zeit("0") == 0.0


def test_zeit_einlesen_lehnt_unsinn_ab():
    for eingabe in ("", "   ", "abc", "1:2:3:4", "-5", "1:-2", "1:60",
                    "1:99", "2:70:00", "1.2.3", "12:ab", None, "1:"):
        assert lies_zeit(eingabe) is None, f"haette None sein muessen: {eingabe!r}"


def test_zeit_setzen_aus_bereit():
    t = Timer()
    assert t.setze_zeit(83.456) is True
    # BEREIT passt nicht mehr, wenn die Uhr nicht auf null steht.
    assert t.zustand is Zustand.GESTOPPT
    assert t.verstrichene_zeit() == 83.456
    assert t.formatierte_zeit() == "1:23.456"


def test_zeit_setzen_waehrend_pause():
    t = Timer()
    t.start()
    time.sleep(0.05)
    t.pause()
    t.setze_zeit(10.0)
    assert t.zustand is Zustand.PAUSIERT
    assert t.verstrichene_zeit() == 10.0
    # Die vorher gelaufene Zeit darf nicht wieder auftauchen.
    time.sleep(0.05)
    assert t.verstrichene_zeit() == 10.0


def test_zeit_setzen_waehrend_laufend():
    t = Timer()
    t.start()
    time.sleep(0.05)
    t.setze_zeit(100.0)
    assert t.zustand is Zustand.LAEUFT
    # Ab dem gesetzten Wert läuft es weiter, die alten 0,05 s zählen nicht mit.
    assert 100.0 <= t.verstrichene_zeit() < 100.02
    time.sleep(0.05)
    assert 100.04 < t.verstrichene_zeit() < 100.1


def test_zeit_setzen_lehnt_negatives_ab():
    t = Timer()
    t.setze_zeit(50.0)
    assert t.setze_zeit(-1) is False
    assert t.verstrichene_zeit() == 50.0


def test_reset_nach_zeit_setzen():
    t = Timer()
    t.setze_zeit(500.0)
    t.zuruecksetzen()
    assert t.zustand is Zustand.BEREIT
    assert t.verstrichene_zeit() == 0.0


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
        # Nach dem Reset muss ein neuer Lauf möglich sein.
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
