"""
Speedrun-Timer - grafische Oberfläche (tkinter).

Start über:  python main.py

Die Oberfläche enthält selbst keine Zeitrechnung. Sie fragt den Timer aus
timer_logik.py nur regelmäßig nach dem aktuellen Wert und zeigt ihn an.

Die Dateien im Überblick:
  timer_logik.py  - Zustände und Zeitmessung, ganz ohne GUI
  hotkeys.py      - globale Tasten, Aufnahme, timer_config.json
  einstellungen.py- das Fenster zum Neubelegen
  stil.py         - Farben und Schriften
  main.py         - dieses Hauptfenster
"""

import tkinter as tk

import stil
from einstellungen import EinstellungsFenster
from hotkeys import AKTION_BESCHRIFTUNG, AKTIONEN, HotkeyVerwaltung, lesbare_kombination
from timer_logik import Timer, Zustand

# Die Zeitanzeige wechselt je nach Zustand die Farbe - so siehst du auf einen
# Blick, ob der Timer läuft, auch ohne den Text zu lesen.
FARBE_JE_ZUSTAND = {
    Zustand.BEREIT: "#e6e6e6",     # neutral weiß
    Zustand.LAEUFT: "#5ddb8a",     # grün
    Zustand.PAUSIERT: "#e8c14a",   # gelb
    Zustand.GESTOPPT: "#7aa7ff",   # blau
}

TEXT_JE_ZUSTAND = {
    Zustand.BEREIT: "Bereit",
    Zustand.LAEUFT: "Läuft",
    Zustand.PAUSIERT: "Pausiert",
    Zustand.GESTOPPT: "Gestoppt",
}

# Abstand zwischen zwei Bildschirmaktualisierungen in Millisekunden.
# 16 ms entsprechen etwa 60 Aktualisierungen pro Sekunde.
AKTUALISIERUNGS_INTERVALL_MS = 16


class TimerFenster:
    """Das Hauptfenster mit Zeitanzeige und Bedienknöpfen."""

    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.timer = Timer()

        # Merker, damit wir die Buttons nur dann neu setzen, wenn sich der
        # Zustand wirklich geändert hat, und nicht 60-mal pro Sekunde.
        self._letzter_zustand: Zustand | None = None
        # Das Einstellungsfenster, solange es offen ist.
        self._einstellungen: EinstellungsFenster | None = None

        # Die Hotkey-Verwaltung bekommt genau die vier Aktionsmethoden.
        # Sie ruft sie nicht direkt auf, sondern über root.after - siehe
        # die Erklärung oben in hotkeys.py. Die Belegung wird dabei schon
        # aus timer_config.json geladen.
        self.hotkeys = HotkeyVerwaltung(
            root,
            {
                "start": self.aktion_start,
                "pause": self.aktion_pause,
                "stop": self.aktion_stop,
                "reset": self.aktion_zuruecksetzen,
            },
        )

        self._baue_oberflaeche()
        self._starte_hotkeys()
        self._zeichne_neu()
        self._aktualisiere_anzeige()

        # Beim Schließen des Fensters den Tastatur-Listener sauber beenden.
        self.root.protocol("WM_DELETE_WINDOW", self._beim_schliessen)

    # ------------------------------------------------------------------
    # Aufbau der Oberfläche
    # ------------------------------------------------------------------

    def _baue_oberflaeche(self) -> None:
        self.root.title("Speedrun-Timer")
        self.root.configure(bg=stil.FARBE_HINTERGRUND)
        self.root.resizable(False, False)

        rahmen = tk.Frame(self.root, bg=stil.FARBE_HINTERGRUND, padx=16, pady=12)
        rahmen.pack(fill="both", expand=True)

        # --- Große Zeitanzeige in Monospace ----------------------------
        # Monospace ist hier wichtig: bei einer Proportionalschrift hätten
        # die Ziffern unterschiedliche Breiten und die Anzeige würde bei
        # jedem Millisekundenwechsel zappeln.
        self.label_zeit = tk.Label(
            rahmen,
            text="0:00.000",
            font=stil.SCHRIFT_ZEIT,
            bg=stil.FARBE_HINTERGRUND,
            fg=stil.FARBE_TEXT,
        )
        self.label_zeit.pack(pady=(4, 0))

        # --- Kleine Zustandsanzeige darunter ---------------------------
        self.label_zustand = tk.Label(
            rahmen,
            text="Bereit",
            font=stil.SCHRIFT_NORMAL,
            bg=stil.FARBE_HINTERGRUND,
            fg=stil.FARBE_TEXT_GEDIMMT,
        )
        self.label_zustand.pack(pady=(0, 10))

        # --- Die vier Buttons in einer Reihe ---------------------------
        button_reihe = tk.Frame(rahmen, bg=stil.FARBE_HINTERGRUND)
        button_reihe.pack(fill="x")

        self.button_start = self._erzeuge_button(button_reihe, "Start", self.aktion_start)
        self.button_pause = self._erzeuge_button(button_reihe, "Pause", self.aktion_pause)
        self.button_stop = self._erzeuge_button(button_reihe, "Stop", self.aktion_stop)
        self.button_reset = self._erzeuge_button(button_reihe, "Reset", self.aktion_zuruecksetzen)

        for spalte, button in enumerate(
            (self.button_start, self.button_pause, self.button_stop, self.button_reset)
        ):
            button.grid(row=0, column=spalte, sticky="ew", padx=3)
            # Alle vier Spalten gleich breit machen.
            button_reihe.columnconfigure(spalte, weight=1, uniform="buttons")

        # --- Zeile mit der aktuellen Hotkey-Belegung -------------------
        self.label_hotkeys = tk.Label(
            rahmen,
            text="",
            font=stil.SCHRIFT_KLEIN,
            bg=stil.FARBE_HINTERGRUND,
            fg=stil.FARBE_TEXT_GEDIMMT,
        )
        self.label_hotkeys.pack(pady=(10, 0))

        # --- Fußleiste: Checkbox und Einstellungen ---------------------
        fussleiste = tk.Frame(rahmen, bg=stil.FARBE_HINTERGRUND)
        fussleiste.pack(fill="x", pady=(8, 0))

        self.var_immer_vorne = tk.BooleanVar(value=False)
        self.checkbox_vorne = tk.Checkbutton(
            fussleiste,
            text="Immer im Vordergrund",
            variable=self.var_immer_vorne,
            command=self._setze_immer_vorne,
            font=stil.SCHRIFT_NORMAL,
            bg=stil.FARBE_HINTERGRUND,
            fg=stil.FARBE_TEXT,
            activebackground=stil.FARBE_HINTERGRUND,
            activeforeground=stil.FARBE_TEXT,
            selectcolor=stil.FARBE_BUTTON,  # Farbe des Kästchens selbst
            highlightthickness=0,
            borderwidth=0,
        )
        self.checkbox_vorne.pack(side="left")

        self.button_einstellungen = tk.Button(
            fussleiste,
            text="Einstellungen",
            command=self.oeffne_einstellungen,
            font=stil.SCHRIFT_NORMAL,
            padx=8,
            pady=2,
            **{k: v for k, v in stil.knopf_stil().items() if k != "font"},
        )
        self.button_einstellungen.pack(side="right")

    def _erzeuge_button(self, eltern: tk.Widget, beschriftung: str, befehl) -> tk.Button:
        """Erzeugt einen Button im dunklen Farbschema."""
        return tk.Button(
            eltern,
            text=beschriftung,
            command=befehl,
            # Feste Breite in Zeichen: sonst würde das ganze Fenster zucken,
            # sobald aus "Start" der längere Text "Weiter" wird.
            width=7,
            pady=6,
            **stil.knopf_stil(),
        )

    # ------------------------------------------------------------------
    # Hotkeys und Einstellungen
    # ------------------------------------------------------------------

    def _starte_hotkeys(self) -> None:
        """
        Startet den globalen Tastatur-Listener.

        Schlägt das fehl (z. B. weil eine Sicherheitssoftware dazwischenfunkt),
        soll das Programm trotzdem laufen - dann eben nur mit den Buttons.
        """
        try:
            self.hotkeys.starte()
        except Exception as ausnahme:
            self.label_hotkeys.config(
                text=f"Hotkeys nicht verfügbar: {ausnahme}", fg=stil.FARBE_WARNUNG
            )
        else:
            self._aktualisiere_hotkey_zeile()

    def _aktualisiere_hotkey_zeile(self) -> None:
        """Schreibt die aktuelle Belegung in die kleine Zeile unter den Buttons."""
        teile = [
            f"{lesbare_kombination(self.hotkeys.belegung[name])} {AKTION_BESCHRIFTUNG[name]}"
            for name in AKTIONEN
            if name in self.hotkeys.belegung
        ]
        self.label_hotkeys.config(text="  ·  ".join(teile), fg=stil.FARBE_TEXT_GEDIMMT)

    def oeffne_einstellungen(self) -> None:
        """Öffnet das Einstellungsfenster - oder holt ein offenes nach vorn."""
        if self._einstellungen is not None and self._einstellungen.existiert():
            self._einstellungen.in_den_vordergrund()
            return

        self._einstellungen = EinstellungsFenster(
            self.root, self.hotkeys, self._aktualisiere_hotkey_zeile
        )

    def _beim_schliessen(self) -> None:
        """Wird beim Klick auf das X aufgerufen."""
        self.hotkeys.stoppe()
        self.root.destroy()

    # ------------------------------------------------------------------
    # Aktionen
    #
    # Alle vier laufen im GUI-Thread: entweder direkt durch einen Klick,
    # oder von einem Hotkey über root.after(0, ...) hierher weitergereicht.
    # ------------------------------------------------------------------

    def aktion_start(self) -> None:
        self.timer.start()
        self._zeichne_neu()

    def aktion_pause(self) -> None:
        self.timer.pause()
        self._zeichne_neu()

    def aktion_stop(self) -> None:
        self.timer.stop()
        self._zeichne_neu()

    def aktion_zuruecksetzen(self) -> None:
        self.timer.zuruecksetzen()
        self._zeichne_neu()

    def _setze_immer_vorne(self) -> None:
        """Hält das Fenster über allen anderen Fenstern."""
        self.root.attributes("-topmost", self.var_immer_vorne.get())

    # ------------------------------------------------------------------
    # Anzeige aktualisieren
    # ------------------------------------------------------------------

    def _aktualisiere_anzeige(self) -> None:
        """
        Wird alle 16 ms erneut eingeplant und zeichnet die Zeit neu.

        Hier wird nichts hochgezählt: Der Timer rechnet den Wert bei jedem
        Aufruf frisch aus. Wenn dieser Aufruf mal 5 ms zu spät kommt, zeigt
        er trotzdem die korrekte Zeit an.
        """
        self.label_zeit.config(text=self.timer.formatierte_zeit())

        if self.timer.zustand is not self._letzter_zustand:
            self._aktualisiere_buttons()
            self._letzter_zustand = self.timer.zustand

        self.root.after(AKTUALISIERUNGS_INTERVALL_MS, self._aktualisiere_anzeige)

    def _zeichne_neu(self) -> None:
        """
        Zeichnet Zeit und Buttons sofort neu.

        Ohne diesen Aufruf müsste die Oberfläche bis zum nächsten
        16-ms-Takt warten, bevor sie auf einen Klick reagiert.
        """
        self.label_zeit.config(text=self.timer.formatierte_zeit())
        self._aktualisiere_buttons()
        self._letzter_zustand = self.timer.zustand

    def _aktualisiere_buttons(self) -> None:
        """Graut Buttons aus, die im aktuellen Zustand nicht sinnvoll sind."""
        zustand = self.timer.zustand

        self.button_start.config(state="normal" if self.timer.kann_starten() else "disabled")
        self.button_pause.config(state="normal" if self.timer.kann_pausieren() else "disabled")
        self.button_stop.config(state="normal" if self.timer.kann_stoppen() else "disabled")
        self.button_reset.config(state="normal" if self.timer.kann_zuruecksetzen() else "disabled")

        # "Weiter" statt "Start" bzw. "Pause", wenn der Timer von einem
        # eingefrorenen Stand aus weiterlaufen würde.
        self.button_start.config(text="Start" if self.timer.startet_neuen_lauf() else "Weiter")
        self.button_pause.config(text="Weiter" if zustand is Zustand.PAUSIERT else "Pause")

        self.label_zustand.config(text=TEXT_JE_ZUSTAND[zustand])
        self.label_zeit.config(fg=FARBE_JE_ZUSTAND[zustand])


def main() -> None:
    root = tk.Tk()
    TimerFenster(root)
    root.mainloop()


if __name__ == "__main__":
    main()
