"""
Speedrun-Timer - grafische Oberflaeche (tkinter).

Start ueber:  python main.py

Die Oberflaeche enthaelt selbst keine Zeitrechnung. Sie fragt den Timer aus
timer_logik.py nur regelmaessig nach dem aktuellen Wert und zeigt ihn an.
"""

import tkinter as tk

from timer_logik import Timer, Zustand

# ----------------------------------------------------------------------
# Dunkles Farbschema. An einer Stelle gesammelt, damit du Farben leicht
# aendern kannst, ohne den restlichen Code zu durchsuchen.
# ----------------------------------------------------------------------
FARBE_HINTERGRUND = "#1b1b1f"
FARBE_TEXT = "#e6e6e6"
FARBE_TEXT_GEDIMMT = "#8a8a92"
FARBE_BUTTON = "#2c2c33"
FARBE_BUTTON_AKTIV = "#3a3a43"
FARBE_BUTTON_DEAKTIVIERT = "#4a4a52"

# Die Zeitanzeige wechselt je nach Zustand die Farbe - so siehst du auf einen
# Blick, ob der Timer laeuft, auch ohne den Text zu lesen.
FARBE_JE_ZUSTAND = {
    Zustand.BEREIT: "#e6e6e6",     # neutral weiss
    Zustand.LAEUFT: "#5ddb8a",     # gruen
    Zustand.PAUSIERT: "#e8c14a",   # gelb
    Zustand.GESTOPPT: "#7aa7ff",   # blau
}

TEXT_JE_ZUSTAND = {
    Zustand.BEREIT: "Bereit",
    Zustand.LAEUFT: "Laeuft",
    Zustand.PAUSIERT: "Pausiert",
    Zustand.GESTOPPT: "Gestoppt",
}

# Abstand zwischen zwei Bildschirmaktualisierungen in Millisekunden.
# 16 ms entsprechen etwa 60 Aktualisierungen pro Sekunde.
AKTUALISIERUNGS_INTERVALL_MS = 16


class TimerFenster:
    """Das Hauptfenster mit Zeitanzeige und Bedienknoepfen."""

    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.timer = Timer()

        # Merker, damit wir die Buttons nur dann neu setzen, wenn sich der
        # Zustand wirklich geaendert hat, und nicht 60-mal pro Sekunde.
        self._letzter_zustand: Zustand | None = None

        self._baue_oberflaeche()
        self._aktualisiere_buttons()
        self._aktualisiere_anzeige()

    # ------------------------------------------------------------------
    # Aufbau der Oberflaeche
    # ------------------------------------------------------------------

    def _baue_oberflaeche(self) -> None:
        self.root.title("Speedrun-Timer")
        self.root.configure(bg=FARBE_HINTERGRUND)
        self.root.resizable(False, False)

        rahmen = tk.Frame(self.root, bg=FARBE_HINTERGRUND, padx=16, pady=12)
        rahmen.pack(fill="both", expand=True)

        # --- Grosse Zeitanzeige in Monospace ---------------------------
        # Monospace ist hier wichtig: bei einer Proportionalschrift haetten
        # die Ziffern unterschiedliche Breiten und die Anzeige wuerde bei
        # jedem Millisekundenwechsel zappeln.
        self.label_zeit = tk.Label(
            rahmen,
            text="0:00.000",
            font=("Consolas", 40, "bold"),
            bg=FARBE_HINTERGRUND,
            fg=FARBE_TEXT,
        )
        self.label_zeit.pack(pady=(4, 0))

        # --- Kleine Zustandsanzeige darunter ---------------------------
        self.label_zustand = tk.Label(
            rahmen,
            text="Bereit",
            font=("Segoe UI", 9),
            bg=FARBE_HINTERGRUND,
            fg=FARBE_TEXT_GEDIMMT,
        )
        self.label_zustand.pack(pady=(0, 10))

        # --- Die vier Buttons in einer Reihe ---------------------------
        button_reihe = tk.Frame(rahmen, bg=FARBE_HINTERGRUND)
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

        # --- Fussleiste: "Immer im Vordergrund" ------------------------
        fussleiste = tk.Frame(rahmen, bg=FARBE_HINTERGRUND)
        fussleiste.pack(fill="x", pady=(12, 0))

        self.var_immer_vorne = tk.BooleanVar(value=False)
        self.checkbox_vorne = tk.Checkbutton(
            fussleiste,
            text="Immer im Vordergrund",
            variable=self.var_immer_vorne,
            command=self._setze_immer_vorne,
            font=("Segoe UI", 9),
            bg=FARBE_HINTERGRUND,
            fg=FARBE_TEXT,
            activebackground=FARBE_HINTERGRUND,
            activeforeground=FARBE_TEXT,
            selectcolor=FARBE_BUTTON,  # Farbe des Kaestchens selbst
            highlightthickness=0,
            borderwidth=0,
        )
        self.checkbox_vorne.pack(side="left")

    def _erzeuge_button(self, eltern: tk.Widget, beschriftung: str, befehl) -> tk.Button:
        """Erzeugt einen Button im dunklen Farbschema."""
        return tk.Button(
            eltern,
            text=beschriftung,
            command=befehl,
            font=("Segoe UI", 10),
            bg=FARBE_BUTTON,
            fg=FARBE_TEXT,
            activebackground=FARBE_BUTTON_AKTIV,
            activeforeground=FARBE_TEXT,
            disabledforeground=FARBE_BUTTON_DEAKTIVIERT,
            relief="flat",
            borderwidth=0,
            pady=6,
            cursor="hand2",
        )

    # ------------------------------------------------------------------
    # Aktionen
    #
    # Wichtig fuer spaeter: Alle Aktionen laufen ueber genau diese vier
    # Methoden. Wenn in Schritt 2 die globalen Hotkeys dazukommen, rufen
    # diese die Methoden nicht direkt auf, sondern reichen sie ueber
    # root.after(0, ...) an den GUI-Thread weiter.
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

    def _zeichne_neu(self) -> None:
        """
        Zeichnet Zeit und Buttons sofort neu.

        Ohne diesen Aufruf muesste die Oberflaeche bis zum naechsten
        16-ms-Takt warten, bevor sie auf einen Klick reagiert.
        """
        self.label_zeit.config(text=self.timer.formatierte_zeit())
        self._aktualisiere_buttons()
        self._letzter_zustand = self.timer.zustand

    def _setze_immer_vorne(self) -> None:
        """Haelt das Fenster ueber allen anderen Fenstern."""
        self.root.attributes("-topmost", self.var_immer_vorne.get())

    # ------------------------------------------------------------------
    # Anzeige aktualisieren
    # ------------------------------------------------------------------

    def _aktualisiere_anzeige(self) -> None:
        """
        Wird alle 16 ms erneut eingeplant und zeichnet die Zeit neu.

        Hier wird nichts hochgezaehlt: Der Timer rechnet den Wert bei jedem
        Aufruf frisch aus. Wenn dieser Aufruf mal 5 ms zu spaet kommt, zeigt
        er trotzdem die korrekte Zeit an.
        """
        self.label_zeit.config(text=self.timer.formatierte_zeit())

        if self.timer.zustand is not self._letzter_zustand:
            self._aktualisiere_buttons()
            self._letzter_zustand = self.timer.zustand

        self.root.after(AKTUALISIERUNGS_INTERVALL_MS, self._aktualisiere_anzeige)

    def _aktualisiere_buttons(self) -> None:
        """Graut Buttons aus, die im aktuellen Zustand nicht sinnvoll sind."""
        zustand = self.timer.zustand

        self.button_start.config(state="normal" if self.timer.kann_starten() else "disabled")
        self.button_pause.config(state="normal" if self.timer.kann_pausieren() else "disabled")
        self.button_stop.config(state="normal" if self.timer.kann_stoppen() else "disabled")
        self.button_reset.config(state="normal" if self.timer.kann_zuruecksetzen() else "disabled")

        # Der Pause-Button ist ein Umschalter, deshalb wechselt seine
        # Beschriftung, wenn der Timer bereits pausiert ist.
        self.button_pause.config(text="Weiter" if zustand is Zustand.PAUSIERT else "Pause")

        self.label_zustand.config(text=TEXT_JE_ZUSTAND[zustand])
        self.label_zeit.config(fg=FARBE_JE_ZUSTAND[zustand])


def main() -> None:
    root = tk.Tk()
    TimerFenster(root)
    root.mainloop()


if __name__ == "__main__":
    main()
