"""
Floatube — Styles & Theme
Color palette constants and QSS stylesheet for the entire application.
Dark glassmorphism aesthetic with indigo-purple accent gradient.
"""

# ── Color Palette ──────────────────────────────────────────────────────────────
BG_PRIMARY = "rgba(15, 15, 20, 0.92)"
BG_SECONDARY = "rgba(25, 25, 35, 0.95)"
BG_HOVER = "rgba(40, 40, 55, 0.9)"
BG_PRESSED = "rgba(55, 55, 70, 0.9)"

ACCENT_PRIMARY = "#6366f1"       # Indigo
ACCENT_SECONDARY = "#a855f7"     # Purple
ACCENT_GRADIENT = "qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #6366f1, stop:1 #a855f7)"
ACCENT_GLOW = "rgba(99, 102, 241, 0.3)"

TEXT_PRIMARY = "#f1f5f9"
TEXT_SECONDARY = "#9ca3af"
TEXT_MUTED = "#6b7280"

BORDER_SUBTLE = "rgba(255, 255, 255, 0.08)"
BORDER_ACCENT = "rgba(99, 102, 241, 0.4)"

DANGER = "#ef4444"
SUCCESS = "#22c55e"

# ── Dimensions ─────────────────────────────────────────────────────────────────
WIDGET_WIDTH = 380
MINI_HEIGHT = 160
EXPANDED_HEIGHT = 500
CORNER_RADIUS = 16
TITLE_BAR_HEIGHT = 32
ART_SIZE = 72

# ── QSS Stylesheet ────────────────────────────────────────────────────────────
STYLESHEET = f"""
/* ── Global ─────────────────────────────────────────────────────────────── */
QWidget {{
    font-family: 'Segoe UI', 'Inter', sans-serif;
    font-size: 11px;
    color: {TEXT_PRIMARY};
}}

/* ── Title Bar ──────────────────────────────────────────────────────────── */
#titleBar {{
    background: transparent;
    padding: 4px 8px;
}}

#titleLabel {{
    font-size: 11px;
    font-weight: 600;
    color: {TEXT_SECONDARY};
    letter-spacing: 1px;
}}

#btnMinimize, #btnClose {{
    background: transparent;
    border: none;
    border-radius: 6px;
    padding: 4px;
    font-size: 12px;
    color: {TEXT_SECONDARY};
    min-width: 24px;
    max-width: 24px;
    min-height: 24px;
    max-height: 24px;
}}

#btnMinimize:hover {{
    background: {BG_HOVER};
    color: {TEXT_PRIMARY};
}}

#btnClose:hover {{
    background: rgba(239, 68, 68, 0.25);
    color: {DANGER};
}}

/* ── Search Panel ───────────────────────────────────────────────────────── */
#searchInput {{
    background: rgba(30, 30, 42, 0.9);
    border: 1px solid {BORDER_SUBTLE};
    border-radius: 10px;
    padding: 8px 12px 8px 32px;
    font-size: 12px;
    color: {TEXT_PRIMARY};
    selection-background-color: {ACCENT_PRIMARY};
}}

#searchInput:focus {{
    border: 1px solid {BORDER_ACCENT};
}}

#searchResults {{
    background: transparent;
    border: none;
    outline: none;
}}

#searchResults::item {{
    background: transparent;
    border-radius: 8px;
    padding: 6px 8px;
    margin: 1px 4px;
}}

#searchResults::item:hover {{
    background: {BG_HOVER};
}}

#searchResults::item:selected {{
    background: rgba(99, 102, 241, 0.15);
    border: 1px solid {BORDER_ACCENT};
}}

/* ── Now Playing ────────────────────────────────────────────────────────── */
#nowPlaying {{
    background: transparent;
    padding: 8px 12px;
}}

#trackTitle {{
    font-size: 13px;
    font-weight: 700;
    color: {TEXT_PRIMARY};
}}

#trackArtist {{
    font-size: 11px;
    color: {TEXT_SECONDARY};
}}

#timeLabel {{
    font-size: 9px;
    color: {TEXT_MUTED};
}}

/* ── Progress Slider ────────────────────────────────────────────────────── */
#progressSlider {{
    margin: 0px 4px;
}}

#progressSlider::groove:horizontal {{
    height: 4px;
    background: rgba(255, 255, 255, 0.08);
    border-radius: 2px;
}}

#progressSlider::sub-page:horizontal {{
    background: {ACCENT_GRADIENT};
    border-radius: 2px;
}}

#progressSlider::handle:horizontal {{
    background: {TEXT_PRIMARY};
    width: 10px;
    height: 10px;
    margin: -3px 0;
    border-radius: 5px;
}}

#progressSlider::handle:horizontal:hover {{
    background: {ACCENT_PRIMARY};
    width: 12px;
    height: 12px;
    margin: -4px 0;
    border-radius: 6px;
}}

/* ── Controls ───────────────────────────────────────────────────────────── */
#controls {{
    background: transparent;
    padding: 2px 12px 8px 12px;
}}

.controlBtn {{
    background: transparent;
    border: none;
    border-radius: 16px;
    color: {TEXT_SECONDARY};
    padding: 6px;
    min-width: 32px;
    max-width: 32px;
    min-height: 32px;
    max-height: 32px;
    font-size: 14px;
}}

.controlBtn:hover {{
    background: {BG_HOVER};
    color: {TEXT_PRIMARY};
}}

#btnPlayPause {{
    background: {ACCENT_GRADIENT};
    color: white;
    border-radius: 18px;
    min-width: 36px;
    max-width: 36px;
    min-height: 36px;
    max-height: 36px;
    font-size: 16px;
    font-weight: bold;
}}

#btnPlayPause:hover {{
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #818cf8, stop:1 #c084fc);
}}

.activeToggle {{
    color: {ACCENT_PRIMARY};
}}

/* ── Volume Slider ──────────────────────────────────────────────────────── */
#volumeSlider {{
    max-width: 80px;
}}

#volumeSlider::groove:horizontal {{
    height: 3px;
    background: rgba(255, 255, 255, 0.08);
    border-radius: 1px;
}}

#volumeSlider::sub-page:horizontal {{
    background: {TEXT_SECONDARY};
    border-radius: 1px;
}}

#volumeSlider::handle:horizontal {{
    background: {TEXT_PRIMARY};
    width: 8px;
    height: 8px;
    margin: -3px 0;
    border-radius: 4px;
}}

/* ── Queue Panel ────────────────────────────────────────────────────────── */
#queueHeader {{
    font-size: 11px;
    font-weight: 600;
    color: {TEXT_SECONDARY};
    padding: 8px 12px 4px 12px;
    letter-spacing: 0.5px;
}}

#queueList {{
    background: transparent;
    border: none;
    outline: none;
}}

#queueList::item {{
    background: transparent;
    border-radius: 6px;
    padding: 4px 8px;
    margin: 1px 4px;
}}

#queueList::item:hover {{
    background: {BG_HOVER};
}}

#queueList::item:selected {{
    background: rgba(99, 102, 241, 0.12);
}}

/* ── Scrollbar ──────────────────────────────────────────────────────────── */
QScrollBar:vertical {{
    background: transparent;
    width: 6px;
    margin: 4px 0;
}}

QScrollBar::handle:vertical {{
    background: rgba(255, 255, 255, 0.12);
    min-height: 20px;
    border-radius: 3px;
}}

QScrollBar::handle:vertical:hover {{
    background: rgba(255, 255, 255, 0.2);
}}

QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
    height: 0px;
}}

QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {{
    background: transparent;
}}

/* ── Tooltips ───────────────────────────────────────────────────────────── */
QToolTip {{
    background: rgba(30, 30, 42, 0.95);
    color: {TEXT_PRIMARY};
    border: 1px solid {BORDER_SUBTLE};
    border-radius: 6px;
    padding: 4px 8px;
    font-size: 10px;
}}

/* ── Context Menu ───────────────────────────────────────────────────────── */
QMenu {{
    background: rgba(20, 20, 30, 0.95);
    border: 1px solid {BORDER_SUBTLE};
    border-radius: 8px;
    padding: 4px;
}}

QMenu::item {{
    padding: 6px 24px 6px 12px;
    border-radius: 4px;
    color: {TEXT_PRIMARY};
}}

QMenu::item:selected {{
    background: {BG_HOVER};
}}

QMenu::separator {{
    height: 1px;
    background: {BORDER_SUBTLE};
    margin: 4px 8px;
}}
"""
