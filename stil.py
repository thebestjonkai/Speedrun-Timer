"""
Farben und Schriften des dunklen Farbschemas.

Alles an einer Stelle, damit Hauptfenster und Einstellungsfenster gleich
aussehen und du eine Farbe nur einmal ändern musst.
"""

FARBE_HINTERGRUND = "#1b1b1f"
FARBE_FLAECHE = "#232329"       # leicht abgesetzte Flächen, z. B. Zeilen
FARBE_TEXT = "#e6e6e6"
FARBE_TEXT_GEDIMMT = "#8a8a92"
FARBE_WARNUNG = "#e8804a"
FARBE_HINWEIS = "#5ddb8a"
FARBE_BUTTON = "#2c2c33"
FARBE_BUTTON_AKTIV = "#3a3a43"
FARBE_BUTTON_DEAKTIVIERT = "#4a4a52"

SCHRIFT_NORMAL = ("Segoe UI", 9)
SCHRIFT_BUTTON = ("Segoe UI", 10)
SCHRIFT_KLEIN = ("Segoe UI", 8)
SCHRIFT_UEBERSCHRIFT = ("Segoe UI", 10, "bold")
# Monospace für die Zeitanzeige und für Tastenkombinationen: gleich breite
# Zeichen sorgen dafür, dass nichts zappelt, wenn sich der Text ändert.
SCHRIFT_ZEIT = ("Consolas", 40, "bold")
SCHRIFT_TASTE = ("Consolas", 10)


def knopf_stil() -> dict:
    """Gemeinsame Einstellungen für alle Buttons im dunklen Schema."""
    return {
        "font": SCHRIFT_BUTTON,
        "bg": FARBE_BUTTON,
        "fg": FARBE_TEXT,
        "activebackground": FARBE_BUTTON_AKTIV,
        "activeforeground": FARBE_TEXT,
        "disabledforeground": FARBE_BUTTON_DEAKTIVIERT,
        "relief": "flat",
        "borderwidth": 0,
        "cursor": "hand2",
    }
