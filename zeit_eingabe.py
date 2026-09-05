"""
Kleines Fenster, um die Zeit von Hand einzutragen.

Nützlich, wenn der Start verpasst wurde oder ein Lauf ab einer bestimmten
Zwischenzeit geübt werden soll. Das Einlesen selbst steckt in
timer_logik.lies_zeit und ist damit ohne GUI testbar.
"""

import tkinter as tk

import stil
from timer_logik import lies_zeit


class ZeitEingabe:
    """Modales Fenster mit einem Eingabefeld für die Zeit."""

    def __init__(self, root: tk.Tk, startwert: str, bei_uebernahme) -> None:
        """
        root:           das Hauptfenster
        startwert:      Text, mit dem das Feld vorbelegt wird
        bei_uebernahme: wird mit der Zeit in Sekunden aufgerufen
        """
        self.root = root
        self.bei_uebernahme = bei_uebernahme

        self.fenster = tk.Toplevel(root)
        self.fenster.title("Zeit eingeben")
        self.fenster.configure(bg=stil.FARBE_HINTERGRUND)
        self.fenster.resizable(False, False)
        self.fenster.transient(root)
        self.fenster.grab_set()
        self.fenster.protocol("WM_DELETE_WINDOW", self.schliessen)

        rahmen = tk.Frame(self.fenster, bg=stil.FARBE_HINTERGRUND, padx=16, pady=14)
        rahmen.pack(fill="both", expand=True)

        tk.Label(
            rahmen,
            text="Neue Zeit",
            font=stil.SCHRIFT_UEBERSCHRIFT,
            bg=stil.FARBE_HINTERGRUND,
            fg=stil.FARBE_TEXT,
            anchor="w",
        ).pack(fill="x")

        tk.Label(
            rahmen,
            text="Formate: 12  ·  1:23  ·  1:23,456  ·  2:03:04.5",
            font=stil.SCHRIFT_KLEIN,
            bg=stil.FARBE_HINTERGRUND,
            fg=stil.FARBE_TEXT_GEDIMMT,
            anchor="w",
        ).pack(fill="x", pady=(2, 8))

        self.feld = tk.Entry(
            rahmen,
            font=stil.SCHRIFT_TASTE,
            bg=stil.FARBE_FLAECHE,
            fg=stil.FARBE_TEXT,
            insertbackground=stil.FARBE_TEXT,  # Farbe des Textcursors
            relief="flat",
            justify="center",
            width=20,
        )
        self.feld.pack(ipady=6, fill="x")
        self.feld.insert(0, startwert)
        self.feld.select_range(0, "end")
        self.feld.focus_set()

        # Eingabetaste übernimmt, Esc bricht ab - das erwartet man hier.
        self.feld.bind("<Return>", lambda ereignis: self._uebernehmen())
        self.fenster.bind("<Escape>", lambda ereignis: self.schliessen())

        self.label_status = tk.Label(
            rahmen,
            text="",
            font=stil.SCHRIFT_KLEIN,
            bg=stil.FARBE_HINTERGRUND,
            fg=stil.FARBE_WARNUNG,
            height=1,
            anchor="w",
        )
        self.label_status.pack(fill="x", pady=(6, 8))

        leiste = tk.Frame(rahmen, bg=stil.FARBE_HINTERGRUND)
        leiste.pack(fill="x")

        tk.Button(
            leiste,
            text="Abbrechen",
            command=self.schliessen,
            padx=10,
            pady=4,
            **stil.knopf_stil(),
        ).pack(side="right")

        tk.Button(
            leiste,
            text="Übernehmen",
            command=self._uebernehmen,
            padx=10,
            pady=4,
            **stil.knopf_stil(),
        ).pack(side="right", padx=(0, 6))

        self._zentriere()

    def _zentriere(self) -> None:
        self.fenster.update_idletasks()
        x = self.root.winfo_x() + (self.root.winfo_width() - self.fenster.winfo_width()) // 2
        y = self.root.winfo_y() + 40
        self.fenster.geometry(f"+{max(x, 0)}+{max(y, 0)}")

    def _uebernehmen(self) -> None:
        sekunden = lies_zeit(self.feld.get())
        if sekunden is None:
            self.label_status.config(text="Das lässt sich nicht als Zeit lesen.")
            self.feld.select_range(0, "end")
            self.feld.focus_set()
            return

        self.bei_uebernahme(sekunden)
        self.schliessen()

    def schliessen(self) -> None:
        self.fenster.grab_release()
        self.fenster.destroy()

    def existiert(self) -> bool:
        return bool(self.fenster.winfo_exists())

    def in_den_vordergrund(self) -> None:
        self.fenster.deiconify()
        self.fenster.lift()
        self.fenster.focus_force()
