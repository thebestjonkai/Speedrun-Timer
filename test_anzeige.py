"""
Tests der Zeitanzeige - mit echtem Fenster.

Ausführen mit:  python test_anzeige.py

Anders als test_timer_logik.py und test_staende.py braucht diese Datei einen
Bildschirm: Sie baut das Hauptfenster wirklich auf und misst nach, ob die
Zeit hineinpasst. Ein kurzes Aufblitzen der Fenster beim Testen ist normal.

Hintergrund: Die Schriftgröße wird aus der verfügbaren Fläche berechnet.
Wird der Text länger, ohne dass jemand die Neuberechnung anstößt, ragt die
Zeit aus dem Fenster heraus - genau das passierte beim Laden eines Standes
mit Stunden.
"""

import tkinter as tk

from main import TimerFenster

# Eine Zeit jenseits der Stunde: "1:07:03.412", also elf Zeichen statt acht.
STUNDEN_ZEIT = 4023.412


def mit_fenster(pruefung):
    """
    Baut ein Hauptfenster, reicht es an pruefung weiter und räumt danach auf.

    Das Aufräumen steht in finally, damit ein fehlgeschlagener Test kein
    Fenster und keinen Tastatur-Listener zurücklässt.
    """
    root = tk.Tk()
    fenster = TimerFenster(root)
    root.update()
    try:
        pruefung(fenster, root)
    finally:
        fenster.hotkeys.stoppe()
        # Ohne das Abbestellen liefe die 16-ms-Schleife ins Leere und tkinter
        # beschwerte sich über einen Auftrag für ein zerstörtes Fenster.
        fenster.beende_anzeige()
        root.destroy()


def passt_in_die_anzeige(fenster) -> bool:
    """
    Misst, ob der angezeigte Text in den Bereich der Zeitanzeige passt.

    schrift_zeit ist dasselbe Schriftobjekt, mit dem das Label zeichnet -
    seine measure() liefert also genau die Breite auf dem Bildschirm.
    """
    text = fenster.label_zeit.cget("text")
    return fenster.schrift_zeit.measure(text) <= fenster.zeit_bereich.winfo_width()


def test_zeit_von_hand_mit_stunden_passt():
    """Der Fehlerfall: Zeit von Hand setzen, Text wird drei Zeichen länger."""

    def pruefung(fenster, root):
        vorher = fenster.schrift_zeit["size"]
        fenster._uebernimm_zeit(STUNDEN_ZEIT)
        root.update()

        assert fenster.label_zeit.cget("text") == "1:07:03.412"
        # Die Schrift muss kleiner geworden sein, sonst passt es nicht.
        assert fenster.schrift_zeit["size"] < vorher, "Schrift wurde nicht angepasst"
        assert passt_in_die_anzeige(fenster), "Zeit ragt aus dem Fenster"

    mit_fenster(pruefung)


def test_geladener_stand_mit_stunden_passt():
    """Derselbe Weg über einen geladenen Stand."""

    def pruefung(fenster, root):
        fenster._uebernimm_stand({"name": "Langer Lauf", "sekunden": STUNDEN_ZEIT})
        root.update()

        assert fenster.label_zeit.cget("text") == "1:07:03.412"
        assert passt_in_die_anzeige(fenster), "Zeit ragt aus dem Fenster"

    mit_fenster(pruefung)


def test_schrift_waechst_nach_reset_wieder():
    """Wird der Text wieder kürzer, darf die Schrift nicht klein bleiben."""

    def pruefung(fenster, root):
        anfangs = fenster.schrift_zeit["size"]

        fenster._uebernimm_zeit(STUNDEN_ZEIT)
        root.update()
        klein = fenster.schrift_zeit["size"]

        fenster.aktion_zuruecksetzen()
        root.update()

        assert fenster.label_zeit.cget("text") == "0:00.000"
        assert fenster.schrift_zeit["size"] > klein, "Schrift blieb klein"
        assert fenster.schrift_zeit["size"] == anfangs
        assert passt_in_die_anzeige(fenster)

    mit_fenster(pruefung)


def test_kompaktmodus_mit_stunden_passt():
    """Im Kompaktmodus folgt zusätzlich die Fensterhöhe dem neuen Text."""

    def pruefung(fenster, root):
        fenster.aktion_kompakt()
        root.update()
        hoehe_vorher = root.winfo_height()

        fenster._uebernimm_zeit(STUNDEN_ZEIT)
        root.update()

        assert passt_in_die_anzeige(fenster), "Zeit ragt aus dem Fenster"
        # Kleinere Schrift heißt: Das Fenster darf nicht mehr so hoch sein,
        # sonst stünde über und unter der Zeit Leerraum.
        assert root.winfo_height() < hoehe_vorher, "Höhe wurde nicht nachgezogen"

        # Auf die Untergrenze geschrumpft muss es immer noch passen.
        breite = fenster._kompakte_mindestbreite()
        root.geometry(f"{breite}x{fenster._kompakte_hoehe(breite)}")
        root.update()
        assert passt_in_die_anzeige(fenster), "Zeit ragt bei kleinster Größe heraus"

    mit_fenster(pruefung)


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
