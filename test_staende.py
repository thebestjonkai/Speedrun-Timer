"""
Tests für die gespeicherten Timerstände - ganz ohne GUI.

Ausführen mit:  python test_staende.py

Aufgebaut wie test_timer_logik.py: Jeder Test ist eine Funktion mit
"assert"-Behauptungen, am Dateiende werden alle "test_*" eingesammelt.

Wichtig: Die Tests, die wirklich eine Datei schreiben, biegen vorher
staende.STAENDE_DATEI auf eine Testdatei um. Sonst würden sie deine echte
timer_staende.json überschreiben.
"""

import json
from pathlib import Path

import staende

# Testdatei neben diesem Skript. Sie wird nach jedem Dateitest wieder gelöscht.
TESTDATEI = Path(__file__).with_name("test_staende_tmp.json")


def mit_testdatei(funktion):
    """
    Führt funktion() aus, während staende.STAENDE_DATEI auf die Testdatei
    zeigt, und räumt danach auf - auch wenn der Test fehlschlägt.
    """
    echte_datei = staende.STAENDE_DATEI
    staende.STAENDE_DATEI = TESTDATEI
    try:
        funktion()
    finally:
        staende.STAENDE_DATEI = echte_datei
        if TESTDATEI.exists():
            TESTDATEI.unlink()


# ----------------------------------------------------------------------
# Namen
# ----------------------------------------------------------------------


def test_name_wird_getrimmt():
    assert staende.pruefe_name("  Any% Glitchless  ") == "Any% Glitchless"
    assert staende.pruefe_name("Lauf 1") == "Lauf 1"


def test_name_lehnt_unsinn_ab():
    for eingabe in ("", "   ", "\n", "a\nb", "a\tb", None, 5, "x" * 41):
        assert staende.pruefe_name(eingabe) is None, f"haette None sein muessen: {eingabe!r}"


def test_name_an_der_laengengrenze():
    gerade_noch = "x" * staende.MAX_NAME_LAENGE
    assert staende.pruefe_name(gerade_noch) == gerade_noch


def test_gross_und_kleinschreibung_ist_derselbe_stand():
    liste = staende.setze_stand([], "Lauf 1", 10.0, "heute")
    assert staende.finde_stand(liste, "lauf 1") is not None
    assert staende.finde_stand(liste, "LAUF 1") is not None
    assert staende.finde_stand(liste, "Lauf 2") is None


# ----------------------------------------------------------------------
# Anlegen, überschreiben, löschen
# ----------------------------------------------------------------------


def test_stand_anlegen():
    liste = staende.setze_stand([], "Any%", 83.456, "20.09.2026 14:33")
    assert len(liste) == 1
    assert liste[0]["name"] == "Any%"
    assert liste[0]["sekunden"] == 83.456
    assert liste[0]["gespeichert_am"] == "20.09.2026 14:33"


def test_setze_stand_laesst_original_in_ruhe():
    """Die Funktion gibt eine neue Liste zurück, statt die alte zu ändern."""
    original = staende.setze_stand([], "Lauf 1", 10.0, "heute")
    neue = staende.setze_stand(original, "Lauf 2", 20.0, "heute")
    assert len(original) == 1
    assert len(neue) == 2


def test_gleicher_name_ueberschreibt_am_selben_platz():
    liste = staende.setze_stand([], "Lauf 1", 10.0, "heute")
    liste = staende.setze_stand(liste, "Lauf 2", 20.0, "heute")
    liste = staende.setze_stand(liste, "lauf 1", 99.0, "morgen")

    # Kein dritter Eintrag, und "Lauf 1" steht weiterhin vorn.
    assert len(liste) == 2
    assert liste[0]["sekunden"] == 99.0
    assert liste[1]["name"] == "Lauf 2"
    # Die Schreibweise des neuen Namens gilt.
    assert liste[0]["name"] == "lauf 1"


def test_setze_stand_lehnt_unsinn_ab():
    assert staende.setze_stand([], "", 10.0) is None
    assert staende.setze_stand([], "Lauf", -1) is None
    assert staende.setze_stand([], "Lauf", "abc") is None
    assert staende.setze_stand([], "Lauf", None) is None


def test_stand_entfernen():
    liste = staende.setze_stand([], "Lauf 1", 10.0, "heute")
    liste = staende.setze_stand(liste, "Lauf 2", 20.0, "heute")

    liste = staende.entferne_stand(liste, "LAUF 1")
    assert len(liste) == 1
    assert liste[0]["name"] == "Lauf 2"

    # Ein nicht vorhandener Name ist kein Fehler.
    liste = staende.entferne_stand(liste, "gibt es nicht")
    assert len(liste) == 1


def test_liste_laeuft_nicht_ueber():
    liste = []
    for nummer in range(staende.MAX_STAENDE + 5):
        liste = staende.setze_stand(liste, f"Lauf {nummer}", float(nummer), "heute")

    assert len(liste) == staende.MAX_STAENDE
    # Die ältesten sind rausgeflogen, der neueste ist noch da.
    assert liste[-1]["name"] == f"Lauf {staende.MAX_STAENDE + 4}"


def test_namensvorschlag_weicht_belegten_aus():
    assert staende.naechster_freier_name([]) == "Lauf 1"

    liste = staende.setze_stand([], "Lauf 1", 10.0, "heute")
    assert staende.naechster_freier_name(liste) == "Lauf 2"

    liste = staende.setze_stand(liste, "Lauf 2", 20.0, "heute")
    assert staende.naechster_freier_name(liste) == "Lauf 3"


# ----------------------------------------------------------------------
# Suche
# ----------------------------------------------------------------------


def _beispielliste() -> list:
    liste = staende.setze_stand([], "Any% Übung", 723.412, "20.09.2026 14:33")
    liste = staende.setze_stand(liste, "Bosskampf", 107.9, "19.09.2026 21:10")
    liste = staende.setze_stand(liste, "100% Testlauf", 4200.0, "01.10.2026 08:05")
    return liste


def test_leere_suche_zeigt_alles():
    liste = _beispielliste()
    for suche in ("", "   ", None):
        assert len(staende.filtere(liste, suche)) == 3, f"unerwartet bei {suche!r}"


def test_suche_nach_name():
    liste = _beispielliste()
    treffer = staende.filtere(liste, "boss")
    assert [stand["name"] for stand in treffer] == ["Bosskampf"]

    # Groß- und Kleinschreibung darf keine Rolle spielen.
    assert staende.filtere(liste, "ÜBUNG")[0]["name"] == "Any% Übung"


def test_suche_nach_datum():
    liste = _beispielliste()
    # Derselbe Tag in beiden Schreibweisen - mit und ohne führende Null.
    for suche in ("19.09", "19.9"):
        treffer = staende.filtere(liste, suche)
        assert [stand["name"] for stand in treffer] == ["Bosskampf"], f"bei {suche!r}"

    # Ein ganzer Monat.
    assert len(staende.filtere(liste, "09.2026")) == 2


def test_fuehrende_null_verwirrt_die_jahreszahl_nicht():
    """In "2026" steht die 0 mitten in der Zahl und darf nicht wegfallen."""
    liste = _beispielliste()
    assert len(staende.filtere(liste, "2026")) == 3
    assert staende.filtere(liste, "226") == []


def test_mehrere_woerter_grenzen_ein():
    liste = _beispielliste()
    # Beide Wörter müssen passen - eines aus dem Namen, eines aus dem Datum.
    treffer = staende.filtere(liste, "any 20.09")
    assert [stand["name"] for stand in treffer] == ["Any% Übung"]

    # Name passt, Datum nicht: kein Treffer.
    assert staende.filtere(liste, "any 19.09") == []


def test_suche_ohne_treffer():
    assert staende.filtere(_beispielliste(), "gibt es nicht") == []


def test_suche_verschont_die_zeit():
    """Gesucht wird in Name und Datum - nicht in der Laufzeit."""
    liste = _beispielliste()
    # 723,412 s wären "12:03.412". Danach darf nichts gefunden werden.
    assert staende.filtere(liste, "12:03") == []


# ----------------------------------------------------------------------
# Kaputte Daten abfangen
# ----------------------------------------------------------------------


def test_bereinige_wirft_unbrauchbares_raus():
    roh = [
        {"name": "gut", "sekunden": 12.5, "gespeichert_am": "heute"},
        {"name": "", "sekunden": 5},                    # leerer Name
        {"name": "negativ", "sekunden": -3},            # negative Zeit
        {"name": "keine Zahl", "sekunden": "viel"},     # falscher Typ
        {"name": "wahr", "sekunden": True},             # bool ist keine Zeit
        "gar kein Eintrag",
        {"sekunden": 5},                                # Name fehlt
        {"name": "ohne Datum", "sekunden": 7},          # Datum darf fehlen
    ]
    sauber = staende.bereinige(roh)
    assert [eintrag["name"] for eintrag in sauber] == ["gut", "ohne Datum"]
    assert sauber[1]["gespeichert_am"] == ""


def test_bereinige_entfernt_doppelte_namen():
    roh = [
        {"name": "Lauf 1", "sekunden": 10},
        {"name": "lauf 1", "sekunden": 20},
    ]
    sauber = staende.bereinige(roh)
    assert len(sauber) == 1
    assert sauber[0]["sekunden"] == 10.0


def test_bereinige_vertraegt_falsche_grundform():
    assert staende.bereinige(None) == []
    assert staende.bereinige("Text") == []
    assert staende.bereinige({"name": "x"}) == []


# ----------------------------------------------------------------------
# Datei
# ----------------------------------------------------------------------


def test_speichern_und_laden():
    def ablauf():
        liste = staende.setze_stand([], "Any% – Übung", 83.456, "20.09.2026 14:33")
        assert staende.speichere_staende(liste) is True

        geladen = staende.lade_staende()
        assert len(geladen) == 1
        # Umlaute und Sonderzeichen müssen die Datei unbeschadet überstehen.
        assert geladen[0]["name"] == "Any% – Übung"
        assert geladen[0]["sekunden"] == 83.456

    mit_testdatei(ablauf)


def test_laden_ohne_datei():
    def ablauf():
        assert staende.lade_staende() == []

    mit_testdatei(ablauf)


def test_laden_bei_kaputter_datei():
    def ablauf():
        TESTDATEI.write_text("{ das ist kein JSON", encoding="utf-8")
        assert staende.lade_staende() == []

    mit_testdatei(ablauf)


def test_laden_bei_unsinnigem_inhalt():
    def ablauf():
        TESTDATEI.write_text(
            json.dumps({"staende": [{"name": "ok", "sekunden": 5}, {"kaputt": True}]}),
            encoding="utf-8",
        )
        geladen = staende.lade_staende()
        assert len(geladen) == 1
        assert geladen[0]["name"] == "ok"

    mit_testdatei(ablauf)


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
