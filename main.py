"""
Speedrun-Timer - grafische Oberfläche (tkinter).

Start über:  python main.py

Die Oberfläche enthält selbst keine Zeitrechnung. Sie fragt den Timer aus
timer_logik.py nur regelmäßig nach dem aktuellen Wert und zeigt ihn an.

Die Dateien im Überblick:
  timer_logik.py  - Zustände und Zeitmessung, ganz ohne GUI
  hotkeys.py      - globale Tasten, Aufnahme, timer_config.json
  einstellungen.py- das Fenster zum Neubelegen
  staende.py      - gespeicherte Zeiten, timer_staende.json
  staende_fenster.py - Fenster zum Speichern und Auswählen
  stil.py         - Farben und Schriften
  main.py         - dieses Hauptfenster
"""

import tkinter as tk
import tkinter.font as tkfont
from pathlib import Path
from tkinter import messagebox

import staende
import stil
from einstellungen import EinstellungsFenster
from hotkeys import AKTION_BESCHRIFTUNG, AKTIONEN, HotkeyVerwaltung, lesbare_kombination
from staende_fenster import SpeicherFenster, StandAuswahl
from timer_logik import Timer, Zustand
from zeit_eingabe import ZeitEingabe

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

# Fenstersymbol für Titelleiste und Taskleiste. Liegt neben diesem Skript.
ICON_DATEI = Path(__file__).with_name("timer_icon.ico")

# Innenabstand des Rahmens in normaler Ansicht und im Kompaktmodus.
RAND_NORMAL = {"padx": 16, "pady": 12}
RAND_KOMPAKT = {"padx": 10, "pady": 2}

# Grenzen für die Zeitanzeige. Darunter wird sie unleserlich, darüber
# unhandlich.
SCHRIFT_MIN = 10
SCHRIFT_MAX = 300
# Größe, mit der die Textmaße einmal gemessen werden. Schriften skalieren
# linear, deshalb lässt sich daraus jede andere Größe hochrechnen.
SCHRIFT_REFERENZ = 100

# Anteil der Zeilenhöhe, den Ziffern tatsächlich ausfüllen.
# Die Zeilenhöhe einer Schrift reicht von den Oberlängen bis unter die
# Grundlinie (für Buchstaben wie "g"). Ziffern nutzen davon nur den mittleren
# Teil - nachgemessen sind es bei Consolas rund 58 %. Ohne diese Korrektur
# bleibt über und unter der Zeit unnötig viel Rand stehen.
ZIFFERN_ANTEIL = 0.60

# Kleinste Fenstergröße im Kompaktmodus. In der normalen Ansicht ergibt sie
# sich aus den Bedienelementen und wird beim Aufbau ausgerechnet.
MINDESTGROESSE_KOMPAKT = (110, 26)


class TimerFenster:
    """Das Hauptfenster mit Zeitanzeige und Bedienknöpfen."""

    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.timer = Timer()

        # Merker, damit wir die Buttons nur dann neu setzen, wenn sich der
        # Zustand wirklich geändert hat, und nicht 60-mal pro Sekunde.
        self._letzter_zustand: Zustand | None = None
        # Kennung der nächsten eingeplanten Bildschirmaktualisierung. Wird
        # beim Schließen abbestellt, sonst beschwert sich tkinter über einen
        # Auftrag für ein Fenster, das es nicht mehr gibt.
        self._anzeige_auftrag: str | None = None
        # Das Einstellungsfenster, solange es offen ist.
        self._einstellungen: EinstellungsFenster | None = None
        # Das Fenster zur Zeiteingabe, solange es offen ist.
        self._zeit_eingabe: ZeitEingabe | None = None
        # Die Fenster für gespeicherte Stände, solange sie offen sind.
        self._speicher_fenster: SpeicherFenster | None = None
        self._auswahl_fenster: StandAuswahl | None = None
        # Name des "geöffneten" Standes - wie ein geöffnetes Dokument in
        # einer Textverarbeitung. Solange einer geöffnet ist, schreibt
        # "Speichern" ohne Rückfrage hinein. None heißt: keiner geöffnet.
        self._offener_stand: str | None = None
        # Kompaktmodus: nur die Zeit, ohne Titelleiste.
        self._kompakt = False
        # Merkt sich beim Ziehen den Griffpunkt innerhalb des Fensters.
        self._zieh_versatz = (0, 0)
        # Fenstergröße je Ansicht, damit beim Umschalten die zuletzt
        # eingestellte Größe zurückkommt.
        self._groesse_normal: str | None = None
        self._breite_kompakt: int | None = None
        # Zwischenspeicher für die Textmaße, siehe _passe_schrift_an.
        self._mass_je_text: dict = {}
        self._mindestgroesse_normal = (0, 0)

        # Die Hotkey-Verwaltung bekommt genau die fünf Aktionsmethoden.
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
                "kompakt": self.aktion_kompakt,
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
        self.root.resizable(True, True)

        # Fenstersymbol setzen. Fehlt die Datei, läuft das Programm einfach
        # mit dem Standardsymbol weiter - das ist kein Grund abzubrechen.
        try:
            self.root.iconbitmap(str(ICON_DATEI))
        except tk.TclError:
            pass

        # Eigenes Schriftobjekt statt eines festen Tupels: Ändern wir seine
        # Größe, zeichnet tkinter alle Beschriftungen neu, die es benutzen.
        familie, groesse, dicke = stil.SCHRIFT_ZEIT
        self.schrift_zeit = tkfont.Font(family=familie, size=groesse, weight=dicke)
        self._mess_schrift = tkfont.Font(
            family=familie, size=SCHRIFT_REFERENZ, weight=dicke
        )

        self.rahmen = tk.Frame(self.root, bg=stil.FARBE_HINTERGRUND, **RAND_NORMAL)
        self.rahmen.pack(fill="both", expand=True)

        # --- Große Zeitanzeige in Monospace ----------------------------
        # Monospace ist hier wichtig: bei einer Proportionalschrift hätten
        # die Ziffern unterschiedliche Breiten und die Anzeige würde bei
        # jedem Millisekundenwechsel zappeln.
        #
        # Die Anzeige steckt in einem eigenen Bereich mit pack_propagate(False).
        # Das ist der entscheidende Kniff: Normalerweise wächst ein Frame mit
        # seinem Inhalt. Da wir aber umgekehrt die Schriftgröße aus der
        # verfügbaren Fläche berechnen, würde sich beides gegenseitig
        # hochschaukeln - größere Schrift, größerer Bereich, noch größere
        # Schrift. pack_propagate(False) schneidet diese Rückkopplung durch:
        # Die Größe des Bereichs kommt allein vom Fenster.
        self.zeit_bereich = tk.Frame(
            self.rahmen,
            bg=stil.FARBE_HINTERGRUND,
            width=self._textbreite(stil.SCHRIFT_ZEIT[1]) + 16,
            height=self._texthoehe(stil.SCHRIFT_ZEIT[1]) + 8,
        )
        self.zeit_bereich.pack(pady=(4, 0), fill="both", expand=True)
        self.zeit_bereich.pack_propagate(False)

        self.label_zeit = tk.Label(
            self.zeit_bereich,
            text="0:00.000",
            font=self.schrift_zeit,
            bg=stil.FARBE_HINTERGRUND,
            fg=stil.FARBE_TEXT,
        )
        self.label_zeit.pack(fill="both", expand=True)
        # Sobald der Bereich seine Größe ändert, wird die Schrift nachgezogen.
        self.zeit_bereich.bind("<Configure>", self._bei_bereich_groesse)

        # --- Kleine Zustandsanzeige darunter ---------------------------
        self.label_zustand = tk.Label(
            self.rahmen,
            text="Bereit",
            font=stil.SCHRIFT_NORMAL,
            bg=stil.FARBE_HINTERGRUND,
            fg=stil.FARBE_TEXT_GEDIMMT,
        )
        self.label_zustand.pack(pady=(0, 10))

        # --- Die vier Buttons in einer Reihe ---------------------------
        self.button_reihe = tk.Frame(self.rahmen, bg=stil.FARBE_HINTERGRUND)
        self.button_reihe.pack(fill="x")

        self.button_start = self._erzeuge_button(self.button_reihe, "Start", self.aktion_start)
        self.button_pause = self._erzeuge_button(self.button_reihe, "Pause", self.aktion_pause)
        self.button_stop = self._erzeuge_button(self.button_reihe, "Stop", self.aktion_stop)
        self.button_reset = self._erzeuge_button(self.button_reihe, "Reset", self.aktion_zuruecksetzen)

        for spalte, button in enumerate(
            (self.button_start, self.button_pause, self.button_stop, self.button_reset)
        ):
            button.grid(row=0, column=spalte, sticky="ew", padx=3)
            # Alle vier Spalten gleich breit machen.
            self.button_reihe.columnconfigure(spalte, weight=1, uniform="buttons")

        # --- Zeile mit der aktuellen Hotkey-Belegung -------------------
        # wraplength lässt den Text umbrechen, statt das Fenster in die
        # Breite zu ziehen. Der Wert wird bei Größenänderung angepasst.
        self.label_hotkeys = tk.Label(
            self.rahmen,
            text="",
            font=stil.SCHRIFT_KLEIN,
            bg=stil.FARBE_HINTERGRUND,
            fg=stil.FARBE_TEXT_GEDIMMT,
            wraplength=300,
            justify="center",
        )
        self.label_hotkeys.pack(pady=(10, 0), fill="x")

        # --- Fußleiste: Checkbox und Knöpfe ----------------------------
        self.fussleiste = tk.Frame(self.rahmen, bg=stil.FARBE_HINTERGRUND)
        self.fussleiste.pack(fill="x", pady=(8, 0))

        self.var_immer_vorne = tk.BooleanVar(value=False)
        self.checkbox_vorne = tk.Checkbutton(
            self.fussleiste,
            text="Immer vorn",
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
            self.fussleiste,
            text="Einstellungen",
            command=self.oeffne_einstellungen,
            font=stil.SCHRIFT_NORMAL,
            padx=8,
            pady=2,
            **{k: v for k, v in stil.knopf_stil().items() if k != "font"},
        )
        self.button_einstellungen.pack(side="right")

        self.button_kompakt = tk.Button(
            self.fussleiste,
            text="Kompakt",
            command=self.aktion_kompakt,
            font=stil.SCHRIFT_NORMAL,
            padx=8,
            pady=2,
            **{k: v for k, v in stil.knopf_stil().items() if k != "font"},
        )
        self.button_kompakt.pack(side="right", padx=(0, 6))

        self.button_zeit = tk.Button(
            self.fussleiste,
            text="Zeit",
            command=self.oeffne_zeit_eingabe,
            font=stil.SCHRIFT_NORMAL,
            padx=8,
            pady=2,
            **{k: v for k, v in stil.knopf_stil().items() if k != "font"},
        )
        self.button_zeit.pack(side="right", padx=(0, 6))

        # --- Zweite Fußzeile: gespeicherte Stände ----------------------
        # Eine eigene Zeile, weil fünf Knöpfe nebeneinander das Fenster um
        # rund 140 Pixel breiter machen würden - und damit auch die kleinste
        # mögliche Fenstergröße.
        self.fussleiste_stand = tk.Frame(self.rahmen, bg=stil.FARBE_HINTERGRUND)
        self.fussleiste_stand.pack(fill="x", pady=(6, 0))

        # Nur eine kurze Beschriftung der Zeile. Welcher Stand geöffnet ist,
        # steht in der Titelleiste - ein Name hier würde das Fenster je nach
        # Länge um bis zu 100 Pixel breiter machen.
        tk.Label(
            self.fussleiste_stand,
            text="Stand",
            font=stil.SCHRIFT_KLEIN,
            bg=stil.FARBE_HINTERGRUND,
            fg=stil.FARBE_TEXT_GEDIMMT,
        ).pack(side="left")

        self.button_laden = tk.Button(
            self.fussleiste_stand,
            text="Laden",
            command=self.oeffne_stand_auswahl,
            font=stil.SCHRIFT_NORMAL,
            padx=8,
            pady=2,
            **{k: v for k, v in stil.knopf_stil().items() if k != "font"},
        )
        self.button_laden.pack(side="right")

        self.button_speichern_unter = tk.Button(
            self.fussleiste_stand,
            text="Speichern unter …",
            command=self.oeffne_speichern_unter,
            font=stil.SCHRIFT_NORMAL,
            padx=8,
            pady=2,
            **{k: v for k, v in stil.knopf_stil().items() if k != "font"},
        )
        self.button_speichern_unter.pack(side="right", padx=(0, 6))

        self.button_speichern = tk.Button(
            self.fussleiste_stand,
            text="Speichern",
            command=self.aktion_speichern,
            font=stil.SCHRIFT_NORMAL,
            padx=8,
            pady=2,
            **{k: v for k, v in stil.knopf_stil().items() if k != "font"},
        )
        self.button_speichern.pack(side="right", padx=(0, 6))

        self._zeige_offenen_stand()

        self._baue_kontextmenue()

        # Mausrad vergrößert und verkleinert das Fenster. Im Kompaktmodus
        # ist das der einzige Weg, weil dort der Fensterrahmen fehlt.
        self.root.bind("<MouseWheel>", self._bei_mausrad)

        self._setze_mindestgroesse_normal()

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

    def _baue_kontextmenue(self) -> None:
        """
        Rechtsklick-Menü für den Kompaktmodus.

        Dort gibt es keine Titelleiste mehr, also auch kein X zum Schließen.
        Ohne diesen Ausweg käme man aus dem Programm nur noch über den
        Task-Manager heraus.
        """
        self.kontextmenue = tk.Menu(
            self.root,
            tearoff=0,
            bg=stil.FARBE_BUTTON,
            fg=stil.FARBE_TEXT,
            activebackground=stil.FARBE_BUTTON_AKTIV,
            activeforeground=stil.FARBE_TEXT,
            borderwidth=0,
        )
        self.kontextmenue.add_command(label="Normale Ansicht", command=self.aktion_kompakt)
        self.kontextmenue.add_command(label="Zeit eingeben …", command=self.oeffne_zeit_eingabe)
        self.kontextmenue.add_command(label="Stand speichern", command=self.aktion_speichern)
        self.kontextmenue.add_command(
            label="Speichern unter …", command=self.oeffne_speichern_unter
        )
        self.kontextmenue.add_command(label="Stand laden …", command=self.oeffne_stand_auswahl)
        self.kontextmenue.add_separator()
        self.kontextmenue.add_command(label="Beenden", command=self._beim_schliessen)

    def _setze_mindestgroesse_normal(self) -> None:
        """
        Ermittelt, wie klein die normale Ansicht werden darf.

        Dafür wird die Zeitanzeige kurz auf die kleinstmögliche Schrift
        gesetzt: Was das Fenster dann noch braucht, ist der Platzbedarf der
        Bedienelemente - und damit die Untergrenze.
        """
        normale_hoehe = self.zeit_bereich.cget("height")
        normale_breite = self.zeit_bereich.cget("width")

        self.zeit_bereich.config(
            width=self._textbreite(SCHRIFT_MIN) + 16,
            height=self._texthoehe(SCHRIFT_MIN) + 8,
        )
        self.root.update_idletasks()
        self._mindestgroesse_normal = (self.root.winfo_reqwidth(), self.root.winfo_reqheight())

        self.zeit_bereich.config(width=normale_breite, height=normale_hoehe)
        self.root.update_idletasks()
        self.root.minsize(*self._mindestgroesse_normal)

        # Startgröße: etwas breiter als unbedingt nötig, damit die Zeile mit
        # der Hotkey-Belegung auf zwei statt drei Zeilen passt.
        self.root.geometry(
            f"{max(self.root.winfo_reqwidth(), 330)}x{self.root.winfo_reqheight()}"
        )

    # ------------------------------------------------------------------
    # Größe der Zeitanzeige
    # ------------------------------------------------------------------

    def _textbreite(self, schriftgroesse: int, text: str = "0:00.000") -> int:
        """Wie breit wäre dieser Text in der angegebenen Schriftgröße?"""
        return int(self._mess_schrift.measure(text) * schriftgroesse / SCHRIFT_REFERENZ)

    def _texthoehe(self, schriftgroesse: int) -> int:
        """Wie hoch wäre eine Textzeile in der angegebenen Schriftgröße?"""
        return int(self._mess_schrift.metrics("linespace") * schriftgroesse / SCHRIFT_REFERENZ)

    def _ziffernhoehe(self, schriftgroesse: float) -> int:
        """Wie hoch sind die Ziffern selbst - ohne den Leerraum der Zeile?"""
        return int(self._texthoehe(int(schriftgroesse)) * ZIFFERN_ANTEIL)

    def _kompakte_mindestbreite(self) -> int:
        """
        Kleinste Fensterbreite im Kompaktmodus für den aktuellen Text.

        Ab einer Stunde wird die Zeit drei Zeichen länger ("1:07:03.412"
        statt "7:03.412"). Bliebe die Untergrenze dieselbe, ließe sich das
        Fenster schmaler ziehen, als die kleinste Schrift Platz braucht -
        die Ziffern wären dann abgeschnitten.
        """
        noetig = (
            self._textbreite(SCHRIFT_MIN, self.label_zeit.cget("text"))
            + 2 * RAND_KOMPAKT["padx"]
            + 8
        )
        return max(MINDESTGROESSE_KOMPAKT[0], noetig)

    def _kompakte_hoehe(self, breite: int) -> int:
        """
        Passende Fensterhöhe im Kompaktmodus zu einer gegebenen Breite.

        Im Kompaktmodus soll sich das Fenster eng um die Zeit legen. Wäre die
        Höhe frei wählbar, bliebe über und unter den Ziffern Leerraum, sobald
        das Fenster höher ist als für die Schriftgröße nötig.
        """
        text_breite = max(breite - 2 * RAND_KOMPAKT["padx"] - 8, 1)
        breite_referenz = self._masse(self.label_zeit.cget("text"))[0]
        groesse = SCHRIFT_REFERENZ * text_breite / breite_referenz
        groesse = max(SCHRIFT_MIN, min(SCHRIFT_MAX, groesse))
        return self._ziffernhoehe(groesse) + 2 * RAND_KOMPAKT["pady"] + 6

    def _masse(self, text: str) -> tuple:
        """Breite und Ziffernhöhe des Textes in der Referenzgröße."""
        if text not in self._mass_je_text:
            self._mass_je_text[text] = (
                max(self._mess_schrift.measure(text), 1),
                max(int(self._mess_schrift.metrics("linespace") * ZIFFERN_ANTEIL), 1),
            )
        return self._mass_je_text[text]

    def _setze_zeit_text(self, text: str) -> None:
        """
        Schreibt die Zeit in die Anzeige - der einzige Weg dorthin.

        Wird der Text länger oder kürzer (ab 10 Minuten, ab einer Stunde,
        oder weil eine Zeit geladen bzw. von Hand gesetzt wurde), passt
        hier die Schriftgröße nach. Genau das fehlte früher beim Laden:
        Der Text wurde direkt gesetzt, die Schrift blieb auf der Größe für
        "0:00.000" - und "1:07:03.412" ragte aus dem Fenster heraus.

        Die Länge zu prüfen genügt, weil die Zeit in einer Monospace-Schrift
        steht: Alle Ziffern sind gleich breit, nur ihre Anzahl zählt.
        """
        alter_text = self.label_zeit.cget("text")
        self.label_zeit.config(text=text)
        if len(text) != len(alter_text):
            self._bei_neuer_textlaenge()

    def _bei_neuer_textlaenge(self) -> None:
        """Zieht Schrift und - im Kompaktmodus - die Fenstergröße nach."""
        breite = self.zeit_bereich.winfo_width()
        hoehe = self.zeit_bereich.winfo_height()
        # Beim Aufbau steht das Fenster noch nicht; dann übernimmt gleich
        # das <Configure>-Ereignis.
        if breite <= 1 or hoehe <= 1:
            return

        self._passe_schrift_an(breite, hoehe)

        if self._kompakt:
            self._passe_kompakte_groesse_an()

    def _passe_kompakte_groesse_an(self) -> None:
        """
        Zieht die Fenstergröße im Kompaktmodus an den neuen Text nach.

        Ohne Titelleiste kann der Text nicht einfach überstehen: Das Fenster
        wird bei Bedarf breiter, und die Höhe folgt wie immer aus der Breite,
        damit über und unter den Ziffern kein Leerraum entsteht.
        """
        mindestbreite = self._kompakte_mindestbreite()
        self.root.minsize(mindestbreite, MINDESTGROESSE_KOMPAKT[1])

        breite = max(self.root.winfo_width(), mindestbreite)
        hoehe = max(self._kompakte_hoehe(breite), MINDESTGROESSE_KOMPAKT[1])
        self.root.geometry(f"{breite}x{hoehe}")

    def _bei_bereich_groesse(self, ereignis) -> None:
        """Wird aufgerufen, wenn die Zeitanzeige mehr oder weniger Platz hat."""
        self._passe_schrift_an(ereignis.width, ereignis.height)
        # Die Hotkey-Zeile soll innerhalb der Fensterbreite umbrechen.
        self.label_hotkeys.config(wraplength=max(self.root.winfo_width() - 32, 120))

    def _passe_schrift_an(self, breite: int, hoehe: int) -> None:
        """
        Wählt die größte Schrift, mit der die Zeit noch vollständig passt.

        Schriften skalieren linear: Wir messen den Text einmal in der
        Referenzgröße und rechnen daraus hoch, statt Größen durchzuprobieren.
        """
        breite_referenz, hoehe_referenz = self._masse(self.label_zeit.cget("text"))

        # Ein paar Pixel Luft, damit die Ränder der Ziffern nicht anstoßen.
        passend_zur_breite = SCHRIFT_REFERENZ * max(breite - 8, 1) / breite_referenz
        passend_zur_hoehe = SCHRIFT_REFERENZ * max(hoehe - 4, 1) / hoehe_referenz

        neue_groesse = int(min(passend_zur_breite, passend_zur_hoehe))
        neue_groesse = max(SCHRIFT_MIN, min(SCHRIFT_MAX, neue_groesse))

        # Nur bei echter Änderung neu zeichnen, sonst löst das Setzen der
        # Schrift wieder ein Configure-Ereignis aus und wir drehen uns im Kreis.
        if neue_groesse != self.schrift_zeit["size"]:
            self.schrift_zeit.config(size=neue_groesse)

    def _bei_mausrad(self, ereignis) -> None:
        """
        Mausrad ändert die Fenstergröße.

        Die Schrift folgt automatisch, weil sie an der Größe der Zeitanzeige
        hängt. Im Kompaktmodus ist das der einzige Weg zu skalieren, denn
        ohne Titelleiste gibt es keinen Rahmen zum Ziehen.
        """
        faktor = 1.1 if ereignis.delta > 0 else 1 / 1.1

        if self._kompakt:
            # Die Höhe wird nicht mitskaliert, sondern aus der Breite
            # berechnet - so bleibt der Rand oben und unten immer knapp.
            breite = max(int(self.root.winfo_width() * faktor), self._kompakte_mindestbreite())
            hoehe = max(self._kompakte_hoehe(breite), MINDESTGROESSE_KOMPAKT[1])
        else:
            breite = max(int(self.root.winfo_width() * faktor), self._mindestgroesse_normal[0])
            hoehe = max(int(self.root.winfo_height() * faktor), self._mindestgroesse_normal[1])

        self.root.geometry(f"{breite}x{hoehe}")

    # ------------------------------------------------------------------
    # Kompaktmodus
    # ------------------------------------------------------------------

    def aktion_kompakt(self) -> None:
        """Schaltet zwischen normaler Ansicht und reiner Zeitanzeige um."""
        if self._kompakt:
            self._kompakt_aus()
        else:
            self._kompakt_ein()

    def _kompakt_ein(self) -> None:
        """Blendet alles außer der Zeit aus und entfernt die Titelleiste."""
        self._kompakt = True
        self._groesse_normal = f"{self.root.winfo_width()}x{self.root.winfo_height()}"

        for widget in (
            self.label_zustand,
            self.button_reihe,
            self.label_hotkeys,
            self.fussleiste,
            self.fussleiste_stand,
        ):
            widget.pack_forget()
        self.zeit_bereich.pack_configure(pady=0)
        self.rahmen.config(**RAND_KOMPAKT)

        position = (self.root.winfo_x(), self.root.winfo_y())

        # overrideredirect entfernt die komplette Fensterdekoration:
        # Titelleiste, Rahmen und die Knöpfe zum Schließen.
        self.root.overrideredirect(True)
        # Ohne Titelleiste taucht das Fenster unter Windows nicht mehr in der
        # Taskleiste auf. Damit es nicht hinter dem Spiel verschwindet und
        # unerreichbar wird, halten wir es hier immer im Vordergrund -
        # unabhängig von der Checkbox.
        self.root.attributes("-topmost", True)
        self.root.minsize(self._kompakte_mindestbreite(), MINDESTGROESSE_KOMPAKT[1])

        # Zuletzt genutzte Breite wiederherstellen, beim ersten Mal die
        # natürliche nehmen. Die Höhe folgt immer aus der Breite.
        self.root.update_idletasks()
        breite = self._breite_kompakt or self.root.winfo_reqwidth()
        breite = max(breite, self._kompakte_mindestbreite())
        hoehe = max(self._kompakte_hoehe(breite), MINDESTGROESSE_KOMPAKT[1])
        self.root.geometry(f"{breite}x{hoehe}+{position[0]}+{position[1]}")

        # Ersatz für die fehlende Titelleiste: ziehen, Doppelklick zurück,
        # Rechtsklick für das Menü.
        self.root.bind("<Button-1>", self._zieh_start)
        self.root.bind("<B1-Motion>", self._zieh_bewegung)
        self.root.bind("<Double-Button-1>", lambda ereignis: self.aktion_kompakt())
        self.root.bind("<Button-3>", self._zeige_kontextmenue)
        self.label_zeit.config(cursor="fleur")

    def _kompakt_aus(self) -> None:
        """Stellt die normale Ansicht mit Titelleiste wieder her."""
        self._kompakt = False
        self._breite_kompakt = self.root.winfo_width()

        for ereignis in ("<Button-1>", "<B1-Motion>", "<Double-Button-1>", "<Button-3>"):
            self.root.unbind(ereignis)
        self.label_zeit.config(cursor="")

        position = (self.root.winfo_x(), self.root.winfo_y())

        self.root.overrideredirect(False)
        # Nach dem Zurückschalten fehlt der Eintrag in der Taskleiste, bis das
        # Fenster einmal aus- und wieder eingeblendet wurde.
        self.root.withdraw()
        self.root.deiconify()
        self.root.attributes("-topmost", self.var_immer_vorne.get())
        self.root.minsize(*self._mindestgroesse_normal)

        self.rahmen.config(**RAND_NORMAL)
        self.zeit_bereich.pack_configure(pady=(4, 0))
        # In derselben Reihenfolge wie beim Aufbau wieder einhängen, sonst
        # landet die Fußleiste über den Buttons.
        self.label_zustand.pack(pady=(0, 10))
        self.button_reihe.pack(fill="x")
        self.label_hotkeys.pack(pady=(10, 0), fill="x")
        self.fussleiste.pack(fill="x", pady=(8, 0))
        self.fussleiste_stand.pack(fill="x", pady=(6, 0))

        self.root.geometry(self._groesse_normal or "")
        self.root.update_idletasks()
        self.root.geometry(f"+{position[0]}+{position[1]}")

    def _zieh_start(self, ereignis) -> None:
        """Merkt sich, an welcher Stelle im Fenster gegriffen wurde."""
        self._zieh_versatz = (
            ereignis.x_root - self.root.winfo_x(),
            ereignis.y_root - self.root.winfo_y(),
        )

    def _zieh_bewegung(self, ereignis) -> None:
        """Verschiebt das Fenster mit der Maus."""
        x = ereignis.x_root - self._zieh_versatz[0]
        y = ereignis.y_root - self._zieh_versatz[1]
        self.root.geometry(f"+{x}+{y}")

    def _zeige_kontextmenue(self, ereignis) -> None:
        try:
            self.kontextmenue.tk_popup(ereignis.x_root, ereignis.y_root)
        finally:
            # grab_release verhindert, dass das Menü die Maus festhält, wenn
            # man daneben klickt.
            self.kontextmenue.grab_release()

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

    def oeffne_zeit_eingabe(self) -> None:
        """Fragt eine Zeit ab und übernimmt sie in den Timer."""
        if self._zeit_eingabe is not None and self._zeit_eingabe.existiert():
            self._zeit_eingabe.in_den_vordergrund()
            return

        self._zeit_eingabe = ZeitEingabe(
            self.root, self.timer.formatierte_zeit(), self._uebernimm_zeit
        )

    def _uebernimm_zeit(self, sekunden: float) -> None:
        self.timer.setze_zeit(sekunden)
        self._zeichne_neu()

    # ------------------------------------------------------------------
    # Gespeicherte Stände
    # ------------------------------------------------------------------

    def aktion_speichern(self) -> None:
        """
        Speichert die aktuelle Zeit - ohne Rückfrage, wenn ein Stand offen ist.

        Das ist das Strg+S-Verhalten: Ein geladener Stand bleibt geöffnet und
        wird beim Speichern überschrieben. Erst wenn keiner offen ist, fragt
        das Programm nach einem Namen.
        """
        if self._offener_stand is None:
            self.oeffne_speichern_unter()
            return

        # Frisch aus der Datei lesen: Womöglich wurde in der Zwischenzeit ein
        # anderer Stand angelegt oder gelöscht.
        liste = staende.setze_stand(
            staende.lade_staende(), self._offener_stand, self.timer.verstrichene_zeit()
        )
        if liste is None or not staende.speichere_staende(liste):
            self._melde("Speichern fehlgeschlagen")
            return

        self._melde(f"Gespeichert: {self._offener_stand}")

    def oeffne_speichern_unter(self) -> None:
        """Fragt einen Namen ab und legt die aktuelle Zeit darunter ab."""
        if self._speicher_fenster is not None and self._speicher_fenster.existiert():
            self._speicher_fenster.in_den_vordergrund()
            return

        self._speicher_fenster = SpeicherFenster(
            self.root,
            self.timer.verstrichene_zeit(),
            self._nach_dem_speichern,
            vorschlag=self._offener_stand,
        )

    def _nach_dem_speichern(self, name: str) -> None:
        # Unter einem neuen Namen gespeichert? Dann ist ab jetzt dieser der
        # geöffnete Stand - genau wie nach "Speichern unter" in Word.
        self._setze_offenen_stand(name)
        self._melde(f"Gespeichert: {name}")

    def _setze_offenen_stand(self, name: str | None) -> None:
        """Merkt sich den geöffneten Stand und zeigt ihn im Fenster an."""
        self._offener_stand = name
        self._zeige_offenen_stand()

    def _zeige_offenen_stand(self) -> None:
        """
        Schreibt den geöffneten Stand in die Titelleiste.

        Dieselbe Stelle wie bei einem Textprogramm - dort steht schließlich
        auch, welche Datei gerade offen ist.
        """
        if self._offener_stand is None:
            self.root.title("Speedrun-Timer")
        else:
            self.root.title(f"Speedrun-Timer – {self._offener_stand}")

    def _melde(self, text: str) -> None:
        """
        Schreibt eine kurze Rückmeldung in die Zustandszeile.

        Nach zwei Sekunden steht dort wieder der Zustand. Ohne dieses
        Zurücksetzen bliebe die Meldung bis zum nächsten Zustandswechsel
        stehen - und man wüsste nicht mehr, ob der Timer läuft.
        """
        self.label_zustand.config(text=text)
        self.root.after(
            2000,
            lambda: self.label_zustand.config(text=TEXT_JE_ZUSTAND[self.timer.zustand]),
        )

    def oeffne_stand_auswahl(self, beim_start: bool = False) -> None:
        """Zeigt die Liste der gespeicherten Stände zum Auswählen."""
        if self._auswahl_fenster is not None and self._auswahl_fenster.existiert():
            self._auswahl_fenster.in_den_vordergrund()
            return

        self._auswahl_fenster = StandAuswahl(
            self.root,
            self._uebernimm_stand,
            beim_start=beim_start,
            offener_stand=self._offener_stand,
            bei_loeschung=self._stand_wurde_geloescht,
        )

    def _stand_wurde_geloescht(self, name: str) -> None:
        """
        Der geöffnete Stand wurde in der Liste gelöscht.

        Dann darf er nicht geöffnet bleiben: "Speichern" würde ihn sonst
        beim nächsten Klick stillschweigend wieder anlegen.
        """
        self._setze_offenen_stand(None)
        self._melde(f"Gelöscht: {name}")

    def frage_start_stand(self) -> None:
        """
        Fragt direkt nach dem Programmstart, ob ein Stand fortgesetzt wird.

        Ist noch nichts gespeichert, passiert nichts - dann soll der Timer
        einfach wie gewohnt bei 0 stehen.
        """
        if staende.lade_staende():
            self.oeffne_stand_auswahl(beim_start=True)

    def _uebernimm_stand(self, stand: dict) -> None:
        """
        Setzt den Timer auf die Zeit eines gespeicherten Standes.

        Danach ist der Zustand GESTOPPT: Die Zeit steht auf dem gespeicherten
        Wert, und der Startknopf heißt "Weiter" - ein Druck darauf setzt den
        Lauf ab dort fort. Genau dafür ist das Speichern da.
        """
        # Läuft gerade ein Lauf, wäre dessen Zeit weg. Das darf nicht
        # unbemerkt passieren.
        if self.timer.zustand is Zustand.LAEUFT:
            if not messagebox.askyesno(
                "Stand laden",
                "Der Timer läuft gerade. Die laufende Zeit geht verloren.\n\n"
                f"„{stand['name']}“ trotzdem laden?",
                parent=self.root,
            ):
                return

        # Erst zurücksetzen, dann die Zeit setzen: So ist der Zustand danach
        # immer derselbe, egal ob vorher pausiert, gestoppt oder gelaufen.
        self.timer.zuruecksetzen()
        self.timer.setze_zeit(stand["sekunden"])
        self._zeichne_neu()

        # Ab jetzt ist dieser Stand geöffnet: "Speichern" schreibt ohne
        # weitere Rückfrage wieder hier hinein.
        self._setze_offenen_stand(stand["name"])
        self._melde(f"Geladen: {stand['name']}")

    def _beim_schliessen(self) -> None:
        """Wird beim Klick auf das X oder über das Kontextmenü aufgerufen."""
        self.hotkeys.stoppe()
        self.beende_anzeige()
        self.root.destroy()

    def beende_anzeige(self) -> None:
        """Bestellt die nächste eingeplante Aktualisierung ab."""
        if self._anzeige_auftrag is not None:
            self.root.after_cancel(self._anzeige_auftrag)
            self._anzeige_auftrag = None

    # ------------------------------------------------------------------
    # Aktionen
    #
    # Alle laufen im GUI-Thread: entweder direkt durch einen Klick,
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
        # Im Kompaktmodus ist "immer vorn" ohnehin erzwungen, dann darf die
        # Checkbox das nicht wieder abschalten.
        if not self._kompakt:
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
        self._setze_zeit_text(self.timer.formatierte_zeit())

        if self.timer.zustand is not self._letzter_zustand:
            self._aktualisiere_buttons()
            self._letzter_zustand = self.timer.zustand

        self._anzeige_auftrag = self.root.after(
            AKTUALISIERUNGS_INTERVALL_MS, self._aktualisiere_anzeige
        )

    def _zeichne_neu(self) -> None:
        """
        Zeichnet Zeit und Buttons sofort neu.

        Ohne diesen Aufruf müsste die Oberfläche bis zum nächsten
        16-ms-Takt warten, bevor sie auf einen Klick reagiert.
        """
        self._setze_zeit_text(self.timer.formatierte_zeit())
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
    fenster = TimerFenster(root)
    # Erst wenn die tkinter-Schleife läuft, ist das Hauptfenster sichtbar.
    # after(0, ...) reiht die Abfrage genau dahinter ein - so erscheint sie
    # über dem fertigen Fenster statt vor einem leeren Bildschirm.
    root.after(0, fenster.frage_start_stand)
    root.mainloop()


if __name__ == "__main__":
    main()
