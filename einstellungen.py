"""
Einstellungsfenster: Hotkeys ansehen und neu belegen.

Der Ablauf beim Neubelegen ist etwas trickreich, deshalb hier die Kurzfassung:

1. Klick auf "Neu belegen"
2. Der globale Hotkey-Listener wird angehalten. Sonst würde der Timer beim
   Drücken der neuen Tasten sofort losrennen - schließlich sind es ja noch
   die alten Hotkeys, die gerade scharf sind.
3. Ein Aufnahme-Listener sammelt alle gedrückten Tasten. Sobald die erste
   losgelassen wird, ist die Kombination fertig.
4. Das Ergebnis kommt über root.after im GUI-Thread an (siehe hotkeys.py),
   wird auf Doppelbelegung geprüft, gespeichert - und der normale Listener
   läuft mit der neuen Belegung wieder los.
"""

import tkinter as tk
from tkinter import messagebox

import stil
from hotkeys import (
    AKTION_BESCHRIFTUNG,
    AKTIONEN,
    STANDARD_BELEGUNG,
    HotkeyAufnahme,
    finde_doppelbelegung,
    ist_gueltige_kombination,
    lesbare_kombination,
    speichere_belegung,
)


class EinstellungsFenster:
    """Ein eigenes kleines Fenster über dem Hauptfenster."""

    def __init__(self, root: tk.Tk, hotkey_verwaltung, bei_aenderung) -> None:
        """
        root:              das Hauptfenster
        hotkey_verwaltung: die HotkeyVerwaltung aus dem Hauptprogramm
        bei_aenderung:     wird aufgerufen, wenn sich die Belegung ändert,
                           damit das Hauptfenster seine Anzeige nachzieht
        """
        self.root = root
        self.hotkeys = hotkey_verwaltung
        self.bei_aenderung = bei_aenderung

        self.aufnahme = HotkeyAufnahme(root)
        # Name der Aktion, die gerade neu belegt wird - oder None.
        self.aktive_aufnahme: str | None = None
        # Merkt sich pro Aktion die Widgets der Zeile.
        self.zeilen: dict = {}

        self._baue_fenster()
        self._aktualisiere_zeilen()

    # ------------------------------------------------------------------
    # Aufbau
    # ------------------------------------------------------------------

    def _baue_fenster(self) -> None:
        self.fenster = tk.Toplevel(self.root)
        self.fenster.title("Einstellungen")
        self.fenster.configure(bg=stil.FARBE_HINTERGRUND)
        self.fenster.resizable(False, False)

        # transient: Das Fenster gehört sichtbar zum Hauptfenster und wird
        # mit ihm minimiert. grab_set: Solange es offen ist, nimmt das
        # Hauptfenster keine Klicks an - so kann man nicht mitten in einer
        # Aufnahme daran herumdrücken.
        self.fenster.transient(self.root)
        self.fenster.grab_set()
        self.fenster.protocol("WM_DELETE_WINDOW", self.schliessen)
        # Esc bricht eine laufende Aufnahme ab bzw. schließt das Fenster.
        self.fenster.bind("<Escape>", lambda ereignis: self._escape_gedrueckt())

        rahmen = tk.Frame(self.fenster, bg=stil.FARBE_HINTERGRUND, padx=16, pady=14)
        rahmen.pack(fill="both", expand=True)

        tk.Label(
            rahmen,
            text="Globale Hotkeys",
            font=stil.SCHRIFT_UEBERSCHRIFT,
            bg=stil.FARBE_HINTERGRUND,
            fg=stil.FARBE_TEXT,
        ).grid(row=0, column=0, columnspan=3, sticky="w", pady=(0, 10))

        # --- Eine Zeile je Aktion -------------------------------------
        for nummer, aktion in enumerate(AKTIONEN, start=1):
            beschriftung = tk.Label(
                rahmen,
                text=AKTION_BESCHRIFTUNG[aktion],
                font=stil.SCHRIFT_NORMAL,
                bg=stil.FARBE_HINTERGRUND,
                fg=stil.FARBE_TEXT,
                anchor="w",
                width=7,
            )
            beschriftung.grid(row=nummer, column=0, sticky="w", pady=3)

            # Feste Breite, sonst springt die Fensterbreite bei jeder
            # Änderung der Tastenkombination.
            taste = tk.Label(
                rahmen,
                text="",
                font=stil.SCHRIFT_TASTE,
                bg=stil.FARBE_FLAECHE,
                fg=stil.FARBE_TEXT,
                width=22,
                pady=4,
            )
            taste.grid(row=nummer, column=1, sticky="ew", padx=(0, 10), pady=3)

            knopf = tk.Button(
                rahmen,
                text="Neu belegen",
                font=stil.SCHRIFT_NORMAL,
                command=lambda a=aktion: self._neu_belegen(a),
                padx=8,
                pady=3,
                **{k: v for k, v in stil.knopf_stil().items() if k != "font"},
            )
            knopf.grid(row=nummer, column=2, pady=3)

            self.zeilen[aktion] = {"taste": taste, "knopf": knopf}

        # --- Statuszeile ----------------------------------------------
        self.label_status = tk.Label(
            rahmen,
            text="",
            font=stil.SCHRIFT_KLEIN,
            bg=stil.FARBE_HINTERGRUND,
            fg=stil.FARBE_TEXT_GEDIMMT,
            wraplength=340,
            justify="left",
            anchor="w",
            height=2,
        )
        self.label_status.grid(row=len(AKTIONEN) + 1, column=0, columnspan=3, sticky="ew", pady=(10, 6))

        # --- Untere Knopfleiste ---------------------------------------
        leiste = tk.Frame(rahmen, bg=stil.FARBE_HINTERGRUND)
        leiste.grid(row=len(AKTIONEN) + 2, column=0, columnspan=3, sticky="ew")

        self.knopf_standard = tk.Button(
            leiste,
            text="Standard",
            command=self._auf_standard_zuruecksetzen,
            padx=10,
            pady=4,
            **stil.knopf_stil(),
        )
        self.knopf_standard.pack(side="left")

        self.knopf_schliessen = tk.Button(
            leiste,
            text="Schließen",
            command=self.schliessen,
            padx=10,
            pady=4,
            **stil.knopf_stil(),
        )
        self.knopf_schliessen.pack(side="right")

        self._setze_status("Änderungen werden sofort gespeichert.")
        self._zentriere_ueber_hauptfenster()

    def _zentriere_ueber_hauptfenster(self) -> None:
        """Setzt das Fenster mittig über das Hauptfenster."""
        # update_idletasks sorgt dafür, dass die Größen schon feststehen -
        # vorher meldet tkinter für ein frisches Fenster nur 1x1 Pixel.
        self.fenster.update_idletasks()
        x = self.root.winfo_x() + (self.root.winfo_width() - self.fenster.winfo_width()) // 2
        y = self.root.winfo_y() + 40
        self.fenster.geometry(f"+{max(x, 0)}+{max(y, 0)}")

    # ------------------------------------------------------------------
    # Anzeige
    # ------------------------------------------------------------------

    def _aktualisiere_zeilen(self) -> None:
        """Schreibt die aktuelle Belegung in alle Zeilen."""
        for aktion in AKTIONEN:
            zeile = self.zeilen[aktion]
            if aktion == self.aktive_aufnahme:
                zeile["taste"].config(text="Tasten drücken …", fg=stil.FARBE_HINWEIS)
                zeile["knopf"].config(text="Abbrechen", state="normal")
            else:
                kombination = self.hotkeys.belegung.get(aktion, "")
                zeile["taste"].config(text=lesbare_kombination(kombination), fg=stil.FARBE_TEXT)
                zeile["knopf"].config(
                    text="Neu belegen",
                    # Während einer Aufnahme sind die anderen Zeilen gesperrt.
                    state="disabled" if self.aktive_aufnahme else "normal",
                )

        gesperrt = "disabled" if self.aktive_aufnahme else "normal"
        self.knopf_standard.config(state=gesperrt)
        self.knopf_schliessen.config(state=gesperrt)

    def _setze_status(self, text: str, farbe: str | None = None) -> None:
        self.label_status.config(text=text, fg=farbe or stil.FARBE_TEXT_GEDIMMT)

    # ------------------------------------------------------------------
    # Neubelegen
    # ------------------------------------------------------------------

    def _neu_belegen(self, aktion: str) -> None:
        """Startet die Aufnahme - oder bricht sie ab, wenn sie schon läuft."""
        if self.aktive_aufnahme is not None:
            self._brich_aufnahme_ab()
            return

        self.aktive_aufnahme = aktion
        # Die alten Hotkeys stilllegen, sonst löst das Drücken der neuen
        # Tasten womöglich gleich noch den Timer aus.
        self.hotkeys.stoppe()
        self.aufnahme.starte(self._aufnahme_fertig)

        self._aktualisiere_zeilen()
        self._setze_status(
            "Tastenkombination drücken und wieder loslassen. "
            "Esc bricht ab.",
            stil.FARBE_HINWEIS,
        )

    def _brich_aufnahme_ab(self, meldung: str = "Abgebrochen.") -> None:
        self.aufnahme.stoppe()
        self.aktive_aufnahme = None
        self._starte_hotkeys_wieder()
        self._aktualisiere_zeilen()
        self._setze_status(meldung)

    def _escape_gedrueckt(self) -> None:
        if self.aktive_aufnahme is not None:
            self._brich_aufnahme_ab()
        else:
            self.schliessen()

    def _aufnahme_fertig(self, kombination: str) -> None:
        """
        Ergebnis der Aufnahme. Läuft dank root.after im GUI-Thread, hier
        dürfen wir also wieder ganz normal Widgets anfassen.
        """
        aktion = self.aktive_aufnahme
        self.aktive_aufnahme = None
        # Der Aufnahme-Listener beendet sich normalerweise selbst. Falls
        # doch noch einer läuft, soll er hier auf keinen Fall übrig bleiben.
        self.aufnahme.stoppe()

        if aktion is None:
            # Kann passieren, wenn parallel abgebrochen wurde.
            return

        if kombination == "<esc>":
            self._brich_aufnahme_ab()
            return

        if not ist_gueltige_kombination(kombination):
            self._starte_hotkeys_wieder()
            self._aktualisiere_zeilen()
            self._setze_status("Diese Taste lässt sich nicht belegen.", stil.FARBE_WARNUNG)
            return

        belegt_durch = finde_doppelbelegung(self.hotkeys.belegung, aktion, kombination)
        if belegt_durch is not None:
            self._starte_hotkeys_wieder()
            self._aktualisiere_zeilen()
            self._setze_status("Doppelbelegung - nichts geändert.", stil.FARBE_WARNUNG)
            messagebox.showerror(
                "Doppelbelegung",
                f"{lesbare_kombination(kombination)} ist bereits mit "
                f"„{AKTION_BESCHRIFTUNG[belegt_durch]}“ belegt.\n\n"
                "Jede Kombination kann nur einer Aktion zugeordnet werden.",
                parent=self.fenster,
            )
            return

        # Alles in Ordnung: übernehmen.
        neue_belegung = dict(self.hotkeys.belegung)
        neue_belegung[aktion] = kombination
        self._uebernehmen(
            neue_belegung,
            f"{AKTION_BESCHRIFTUNG[aktion]} liegt jetzt auf "
            f"{lesbare_kombination(kombination)}.",
        )

    def _auf_standard_zuruecksetzen(self) -> None:
        self._uebernehmen(dict(STANDARD_BELEGUNG), "Standardbelegung wiederhergestellt.")

    def _uebernehmen(self, belegung: dict, meldung: str) -> None:
        """Neue Belegung scharf schalten, speichern und anzeigen."""
        try:
            self.hotkeys.setze_belegung(belegung)
        except Exception as ausnahme:
            self._aktualisiere_zeilen()
            self._setze_status(f"Hotkeys ließen sich nicht setzen: {ausnahme}", stil.FARBE_WARNUNG)
            return

        if speichere_belegung(belegung):
            self._setze_status(meldung, stil.FARBE_HINWEIS)
        else:
            self._setze_status(
                meldung + " Achtung: Speichern in timer_config.json fehlgeschlagen, "
                "die Änderung gilt nur bis zum Beenden.",
                stil.FARBE_WARNUNG,
            )

        self._aktualisiere_zeilen()
        self.bei_aenderung()

    def _starte_hotkeys_wieder(self) -> None:
        """Schaltet die globalen Hotkeys nach einer Aufnahme wieder scharf."""
        try:
            self.hotkeys.starte()
        except Exception as ausnahme:
            self._setze_status(f"Hotkeys ließen sich nicht starten: {ausnahme}", stil.FARBE_WARNUNG)

    # ------------------------------------------------------------------

    def schliessen(self) -> None:
        """Räumt auf und schließt das Fenster."""
        self.aufnahme.stoppe()
        self.aktive_aufnahme = None
        # Falls beim Schließen noch eine Aufnahme lief, sind die Hotkeys
        # gerade abgeschaltet - hier kommen sie sicher zurück.
        if not self.hotkeys.laeuft():
            self._starte_hotkeys_wieder()
        self.bei_aenderung()
        self.fenster.grab_release()
        self.fenster.destroy()

    def in_den_vordergrund(self) -> None:
        """Holt ein bereits offenes Fenster nach vorn, statt ein zweites zu öffnen."""
        self.fenster.deiconify()
        self.fenster.lift()
        self.fenster.focus_force()

    def existiert(self) -> bool:
        return bool(self.fenster.winfo_exists())
