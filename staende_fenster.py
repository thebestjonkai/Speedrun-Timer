"""
Die beiden Fenster für gespeicherte Timerstände.

SpeicherFenster  - fragt einen Namen ab und legt den aktuellen Stand ab
StandAuswahl     - zeigt die Liste und lädt oder löscht einen Eintrag

Beide reichen die eigentliche Arbeit an staende.py weiter. Hier steht nur,
wie es aussieht und was bei welchem Klick passiert.

Die Fenster laden und schreiben die Liste selbst. Dadurch muss main.py sich
nicht merken, was gerade gespeichert ist - es fragt immer frisch die Datei.
"""

import tkinter as tk
from tkinter import messagebox

import staende
import stil
from timer_logik import formatiere_zeit

# Breite der Liste in Zeichen. Zusammen mit der Monospace-Schrift ergibt das
# saubere Spalten für Name, Zeit und Datum.
LISTEN_BREITE = 48
LISTEN_HOEHE = 8

# So viele Zeichen des Namens passen in die erste Spalte. Längere Namen
# werden in der Anzeige gekürzt - gespeichert bleibt natürlich der ganze.
NAME_SPALTE = 18

# Markierung vor dem Stand, der gerade geöffnet ist.
MARKE_OFFEN = "▸ "
MARKE_LEER = "  "


def _zeilentext(stand: dict, offen: bool = False) -> str:
    """Baut die Anzeigezeile: Marke, Name, Zeit, Datum in festen Spalten."""
    name = stand["name"]
    if len(name) > NAME_SPALTE:
        name = name[: NAME_SPALTE - 1] + "…"

    marke = MARKE_OFFEN if offen else MARKE_LEER
    zeit = formatiere_zeit(stand["sekunden"])
    return f"{marke}{name:<{NAME_SPALTE}}  {zeit:>12}  {stand['gespeichert_am']}"


class _Grundfenster:
    """
    Gemeinsames Grundgerüst beider Fenster.

    Spart das doppelte Aufschreiben von Farbe, Titel, modalem Verhalten und
    dem Zentrieren über dem Hauptfenster - genauso wie es ZeitEingabe für
    sich allein macht.
    """

    def __init__(self, root: tk.Tk, titel: str) -> None:
        self.root = root

        self.fenster = tk.Toplevel(root)
        self.fenster.title(titel)
        self.fenster.configure(bg=stil.FARBE_HINTERGRUND)
        self.fenster.resizable(False, False)
        self.fenster.transient(root)
        self.fenster.grab_set()
        self.fenster.protocol("WM_DELETE_WINDOW", self.schliessen)
        self.fenster.bind("<Escape>", lambda ereignis: self.schliessen())

        # Steht das Hauptfenster immer vorn (im Kompaktmodus immer), müsste
        # dieses Fenster sonst dahinter verschwinden - und wäre nicht mehr
        # bedienbar, obwohl es die Eingabe blockiert.
        if bool(root.attributes("-topmost")):
            self.fenster.attributes("-topmost", True)

        self.rahmen = tk.Frame(self.fenster, bg=stil.FARBE_HINTERGRUND, padx=16, pady=14)
        self.rahmen.pack(fill="both", expand=True)

    def _ueberschrift(self, text: str, hinweis: str = "") -> None:
        tk.Label(
            self.rahmen,
            text=text,
            font=stil.SCHRIFT_UEBERSCHRIFT,
            bg=stil.FARBE_HINTERGRUND,
            fg=stil.FARBE_TEXT,
            anchor="w",
        ).pack(fill="x")

        if hinweis:
            tk.Label(
                self.rahmen,
                text=hinweis,
                font=stil.SCHRIFT_KLEIN,
                bg=stil.FARBE_HINTERGRUND,
                fg=stil.FARBE_TEXT_GEDIMMT,
                anchor="w",
                justify="left",  # mehrzeilige Hinweise sonst mittig
            ).pack(fill="x", pady=(2, 8))

    def _zentriere(self) -> None:
        self.fenster.update_idletasks()
        x = self.root.winfo_x() + (self.root.winfo_width() - self.fenster.winfo_width()) // 2
        y = self.root.winfo_y() + 40
        self.fenster.geometry(f"+{max(x, 0)}+{max(y, 0)}")

    def schliessen(self) -> None:
        self.fenster.grab_release()
        self.fenster.destroy()

    def existiert(self) -> bool:
        return bool(self.fenster.winfo_exists())

    def in_den_vordergrund(self) -> None:
        self.fenster.deiconify()
        self.fenster.lift()
        self.fenster.focus_force()


class SpeicherFenster(_Grundfenster):
    """Fragt einen Namen ab und speichert die übergebene Zeit darunter."""

    def __init__(self, root: tk.Tk, sekunden: float, bei_erfolg=None, vorschlag=None) -> None:
        """
        sekunden:   die Zeit, die gespeichert werden soll
        bei_erfolg: wird nach erfolgreichem Speichern mit dem Namen aufgerufen
        vorschlag:  Vorbelegung des Feldes. Ohne Angabe wird der nächste
                    freie Name genommen ("Lauf 1", "Lauf 2", ...).
        """
        super().__init__(root, "Stand speichern")
        self.sekunden = sekunden
        self.bei_erfolg = bei_erfolg
        self.staende = staende.lade_staende()

        self._ueberschrift(
            f"Zeit {formatiere_zeit(sekunden)} speichern",
            "Unter diesem Namen findest du den Stand beim nächsten Start wieder.",
        )

        self.feld = tk.Entry(
            self.rahmen,
            font=stil.SCHRIFT_TASTE,
            bg=stil.FARBE_FLAECHE,
            fg=stil.FARBE_TEXT,
            insertbackground=stil.FARBE_TEXT,  # Farbe des Textcursors
            relief="flat",
            justify="center",
            width=26,
        )
        self.feld.pack(ipady=6, fill="x")
        self.feld.insert(0, vorschlag or staende.naechster_freier_name(self.staende))
        self.feld.select_range(0, "end")
        self.feld.focus_set()

        self.feld.bind("<Return>", lambda ereignis: self._speichern())
        # Bei jedem Tastendruck prüfen, ob der Name schon vergeben ist.
        self.feld.bind("<KeyRelease>", lambda ereignis: self._pruefe_eingabe())

        self.label_status = tk.Label(
            self.rahmen,
            text="",
            font=stil.SCHRIFT_KLEIN,
            bg=stil.FARBE_HINTERGRUND,
            fg=stil.FARBE_TEXT_GEDIMMT,
            height=1,
            anchor="w",
        )
        self.label_status.pack(fill="x", pady=(6, 8))

        leiste = tk.Frame(self.rahmen, bg=stil.FARBE_HINTERGRUND)
        leiste.pack(fill="x")

        tk.Button(
            leiste,
            text="Abbrechen",
            command=self.schliessen,
            padx=10,
            pady=4,
            **stil.knopf_stil(),
        ).pack(side="right")

        self.button_speichern = tk.Button(
            leiste,
            text="Speichern",
            command=self._speichern,
            padx=10,
            pady=4,
            **stil.knopf_stil(),
        )
        self.button_speichern.pack(side="right", padx=(0, 6))

        self._pruefe_eingabe()
        self._zentriere()

    def _pruefe_eingabe(self) -> None:
        """Zeigt an, ob der eingetippte Name einen vorhandenen überschreibt."""
        name = staende.pruefe_name(self.feld.get())

        if name is None:
            self.label_status.config(text="", fg=stil.FARBE_TEXT_GEDIMMT)
            return

        vorhandener = staende.finde_stand(self.staende, name)
        if vorhandener is None:
            self.label_status.config(text="", fg=stil.FARBE_TEXT_GEDIMMT)
        else:
            self.label_status.config(
                text=f"Überschreibt {formatiere_zeit(vorhandener['sekunden'])}.",
                fg=stil.FARBE_HINWEIS,
            )

    def _speichern(self) -> None:
        name = staende.pruefe_name(self.feld.get())
        if name is None:
            self.label_status.config(
                text=f"Bitte einen Namen eingeben (höchstens {staende.MAX_NAME_LAENGE} Zeichen).",
                fg=stil.FARBE_WARNUNG,
            )
            self.feld.focus_set()
            return

        neue_liste = staende.setze_stand(self.staende, name, self.sekunden)
        if neue_liste is None or not staende.speichere_staende(neue_liste):
            # Schreibt der Ordner nicht, bleibt das Fenster offen - so geht
            # die eingetippte Eingabe nicht verloren.
            self.label_status.config(
                text="Speichern fehlgeschlagen - Datei nicht beschreibbar?",
                fg=stil.FARBE_WARNUNG,
            )
            return

        self.schliessen()
        if self.bei_erfolg is not None:
            self.bei_erfolg(name)


class StandAuswahl(_Grundfenster):
    """
    Liste der gespeicherten Stände zum Laden oder Löschen.

    Dasselbe Fenster dient zwei Zwecken: Beim Programmstart fragt es, ob ein
    Stand fortgesetzt werden soll; später öffnet es der Knopf "Laden". Der
    Unterschied ist nur die Beschriftung, deshalb steckt beides hier.
    """

    def __init__(
        self,
        root: tk.Tk,
        bei_auswahl,
        beim_start: bool = False,
        offener_stand: str | None = None,
        bei_loeschung=None,
    ) -> None:
        """
        bei_auswahl:   wird mit dem gewählten Stand (dict) aufgerufen
        beim_start:    True für die Abfrage direkt nach dem Programmstart
        offener_stand: Name des gerade geöffneten Standes, wird markiert
        bei_loeschung: wird mit dem Namen eines gelöschten Standes aufgerufen
        """
        titel = "Stand fortsetzen" if beim_start else "Stand laden"
        super().__init__(root, titel)

        self.bei_auswahl = bei_auswahl
        self.bei_loeschung = bei_loeschung
        self.offener_stand = offener_stand
        # alle: was in der Datei steht. gefiltert: was die Suche davon übrig
        # lässt und was deshalb in der Liste steht.
        self.alle = staende.lade_staende()
        self.gefiltert: list = []

        self._ueberschrift(
            "Gespeicherten Stand fortsetzen?" if beim_start else "Gespeicherter Stand",
            "Doppelklick lädt den Eintrag; der Timer läuft dann mit „Weiter“ "
            f"ab dieser Zeit weiter.\n{MARKE_OFFEN}zeigt den gerade "
            "geöffneten Stand.",
        )

        # --- Suchleiste ------------------------------------------------
        # Kein Feld zum Umschalten zwischen "Name" und "Datum": Gesucht wird
        # in beidem gleichzeitig, siehe staende.passt_zur_suche.
        such_reihe = tk.Frame(self.rahmen, bg=stil.FARBE_HINTERGRUND)
        such_reihe.pack(fill="x", pady=(0, 6))

        tk.Label(
            such_reihe,
            text="Suche",
            font=stil.SCHRIFT_NORMAL,
            bg=stil.FARBE_HINTERGRUND,
            fg=stil.FARBE_TEXT_GEDIMMT,
        ).pack(side="left", padx=(0, 6))

        self.feld_suche = tk.Entry(
            such_reihe,
            font=stil.SCHRIFT_TASTE,
            bg=stil.FARBE_FLAECHE,
            fg=stil.FARBE_TEXT,
            insertbackground=stil.FARBE_TEXT,
            relief="flat",
        )
        self.feld_suche.pack(side="left", fill="x", expand=True, ipady=4)
        # Bei jedem Tastendruck neu filtern - kein Knopf zum Bestätigen.
        self.feld_suche.bind("<KeyRelease>", lambda ereignis: self._fuelle_liste())
        # Eingabe lädt den obersten Treffer, Pfeil runter springt in die Liste.
        self.feld_suche.bind("<Return>", lambda ereignis: self._laden())
        self.feld_suche.bind("<Down>", lambda ereignis: self.liste.focus_set())

        self.liste = tk.Listbox(
            self.rahmen,
            font=stil.SCHRIFT_TASTE,
            bg=stil.FARBE_FLAECHE,
            fg=stil.FARBE_TEXT,
            selectbackground=stil.FARBE_BUTTON_AKTIV,
            selectforeground=stil.FARBE_TEXT,
            highlightthickness=0,
            borderwidth=0,
            activestyle="none",     # kein Unterstrich unter der aktiven Zeile
            width=LISTEN_BREITE,
            height=LISTEN_HOEHE,
        )
        self.liste.pack(fill="both", expand=True)
        self.liste.bind("<Double-Button-1>", lambda ereignis: self._laden())
        self.liste.bind("<Return>", lambda ereignis: self._laden())

        self.label_status = tk.Label(
            self.rahmen,
            text="",
            font=stil.SCHRIFT_KLEIN,
            bg=stil.FARBE_HINTERGRUND,
            fg=stil.FARBE_WARNUNG,
            height=1,
            anchor="w",
        )
        self.label_status.pack(fill="x", pady=(6, 8))

        leiste = tk.Frame(self.rahmen, bg=stil.FARBE_HINTERGRUND)
        leiste.pack(fill="x")

        self.button_laden = tk.Button(
            leiste,
            text="Fortsetzen" if beim_start else "Laden",
            command=self._laden,
            padx=10,
            pady=4,
            **stil.knopf_stil(),
        )
        self.button_laden.pack(side="right")

        tk.Button(
            leiste,
            # Beim Start ist "Neu beginnen" gemeint, sonst schlichtes Abbrechen.
            text="Neu beginnen" if beim_start else "Abbrechen",
            command=self.schliessen,
            padx=10,
            pady=4,
            **stil.knopf_stil(),
        ).pack(side="right", padx=(0, 6))

        tk.Button(
            leiste,
            text="Löschen",
            command=self._loeschen,
            padx=10,
            pady=4,
            **stil.knopf_stil(),
        ).pack(side="left")

        self._fuelle_liste()
        # Der Tastaturfokus liegt auf der Suche: So kann man sofort lostippen,
        # und Eingabe lädt trotzdem den markierten Eintrag.
        self.feld_suche.focus_set()
        self._zentriere()

    def _fuelle_liste(self) -> None:
        """
        Zeigt die Stände, die zur Suche passen, und markiert den ersten.

        Wird bei jedem Tastendruck in der Suche neu aufgerufen. Die Liste
        bleibt dadurch immer das, was die Suche gerade übrig lässt - und
        _gewaehlter_stand kann sich einfach auf self.gefiltert beziehen.
        """
        self.gefiltert = staende.filtere(self.alle, self.feld_suche.get())

        self.liste.delete(0, "end")
        for stand in self.gefiltert:
            offen = self.offener_stand is not None and staende.gleicher_name(
                stand["name"], self.offener_stand
            )
            self.liste.insert("end", _zeilentext(stand, offen))

        if self.gefiltert:
            self.liste.selection_set(0)
            self.button_laden.config(state="normal")
            self.label_status.config(text="")
        else:
            leer_text = "  (nichts gefunden)" if self.alle else "  (noch nichts gespeichert)"
            self.liste.insert("end", leer_text)
            self.button_laden.config(state="disabled")

    def _gewaehlter_stand(self):
        """Der gerade markierte Stand - oder None, wenn nichts markiert ist."""
        auswahl = self.liste.curselection()
        if not auswahl or not self.gefiltert:
            return None

        platz = auswahl[0]
        if platz >= len(self.gefiltert):
            return None
        return self.gefiltert[platz]

    def _laden(self) -> None:
        stand = self._gewaehlter_stand()
        if stand is None:
            self.label_status.config(text="Bitte zuerst einen Eintrag auswählen.")
            return

        # Erst das Fenster schließen, dann melden. Sonst läge der modale
        # Griff (grab_set) noch auf diesem Fenster, während main.py
        # womöglich eine Rückfrage anzeigen will.
        self.schliessen()
        self.bei_auswahl(stand)

    def _loeschen(self) -> None:
        stand = self._gewaehlter_stand()
        if stand is None:
            self.label_status.config(text="Bitte zuerst einen Eintrag auswählen.")
            return

        # Gelöscht ist gelöscht - hier lohnt eine Rückfrage.
        if not messagebox.askyesno(
            "Stand löschen",
            f"„{stand['name']}“ wirklich löschen?",
            parent=self.fenster,
        ):
            return

        self.alle = staende.entferne_stand(self.alle, stand["name"])
        if not staende.speichere_staende(self.alle):
            self.label_status.config(text="Datei nicht beschreibbar - Löschen nicht gesichert.")

        # War es der geöffnete Stand, gilt danach keiner mehr als geöffnet -
        # sonst würde "Speichern" ihn stillschweigend wieder anlegen.
        if self.offener_stand is not None and staende.gleicher_name(
            stand["name"], self.offener_stand
        ):
            self.offener_stand = None
            if self.bei_loeschung is not None:
                self.bei_loeschung(stand["name"])

        self._fuelle_liste()
