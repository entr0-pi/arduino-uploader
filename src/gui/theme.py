"""Centralized color and style constants."""

# Semantic colors
OK = "#4ec969"
WARN = "#e0a820"
ERROR = "#e05555"
MUTED = "#888888"
LINK = "#5a9fd4"

# Button styles
BTN_DANGER_BG = "#d64b4b"
BTN_DANGER_HOVER = "#be3f3f"
BTN_PRIMARY_BG = "#2e79d1"
BTN_PRIMARY_HOVER = "#2667b3"
BTN_FG = "#ffffff"

# Terminal
TERMINAL_BG = "#1e1e1e"
TERMINAL_FG = "#ffffff"

# Fonts
FONT_HEADING = ("Segoe UI", 16, "bold")
FONT_SUBHEADING = ("Segoe UI", 15, "bold")
FONT_BODY = ("Segoe UI", 10)
FONT_SMALL = ("Segoe UI", 9)
FONT_STATUS = ("Segoe UI", 11, "bold")
FONT_MONO = ("Consolas", 10)
FONT_MONO_SMALL = ("Consolas", 9)


def danger_button_style() -> dict:
    """Return kwargs for a red danger button (flash/write)."""
    return dict(
        bg=BTN_DANGER_BG, fg=BTN_FG,
        activebackground=BTN_DANGER_HOVER, activeforeground=BTN_FG,
        relief="flat", bd=0, padx=12, pady=6, cursor="hand2",
    )


def primary_button_style() -> dict:
    """Return kwargs for a blue primary button (import/export)."""
    return dict(
        bg=BTN_PRIMARY_BG, fg=BTN_FG,
        activebackground=BTN_PRIMARY_HOVER, activeforeground=BTN_FG,
        relief="flat", bd=0, padx=10, pady=4, cursor="hand2",
    )
