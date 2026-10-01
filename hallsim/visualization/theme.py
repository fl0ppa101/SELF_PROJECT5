from dataclasses import dataclass


@dataclass(frozen=True)
class Theme:
    background: str
    panel: str
    foreground: str
    muted: str
    border: str
    accent: str
    selection: str
    field_line: str


THEMES = {
    "light": Theme("#f5efe6", "#fcf8f1", "#382d28", "#897c70", "#ded4c6",
                   "#a44c38", "#f5dcad", "#e4f5ef"),
    "dark": Theme("#171d26", "#202834", "#e6e9ee", "#97a3b2", "#364252",
                  "#ed987f", "#ffdfaa", "#e0f0f2"),
}


def get_theme(name: str) -> Theme:
    if name not in THEMES:
        raise ValueError("theme must be 'light' or 'dark'")
    return THEMES[name]


def stylesheet(name: str) -> str:
    t = get_theme(name)
    return f"""
    QWidget {{ background: {t.background}; color: {t.foreground}; font-size: 13px; }}
    QFrame#card {{ background: {t.panel}; border: 1px solid {t.border}; border-radius: 10px; }}
    QLabel {{ background: transparent; }}
    QLabel#heading {{ font-size: 17px; font-weight: 600; }}
    QLabel#muted {{ color: {t.muted}; }}
    QPushButton, QComboBox, QDoubleSpinBox {{ background: {t.panel}; border: 1px solid {t.border};
        border-radius: 5px; padding: 6px 10px; }}
    QPushButton:hover {{ border-color: {t.accent}; }}
    QPushButton:checked {{ background: {t.accent}; color: white; }}
    QToolTip {{ color: {t.foreground}; background: {t.panel}; border: 1px solid {t.border}; padding: 6px; }}
    QCheckBox {{ spacing: 8px; background: transparent; }}
    """
