"""
Floatube — Platform Utilities
Global media key listener, taskbar-aware positioning, and persistent settings.
All Windows-specific integrations in one module.
"""

import ctypes
import ctypes.wintypes
import json
import threading
from typing import Optional, Callable
import os
import sys

from PyQt6.QtCore import QObject, QThread, pyqtSignal, QSettings, QPoint, QSize

def get_asset_path(filename: str) -> str:
    """Get absolute path to an asset file."""
    base_dir = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(base_dir, "assets", filename)


# ═══════════════════════════════════════════════════════════════════════════════
#  SETTINGS — Persistent app settings via QSettings (Windows registry-backed)
# ═══════════════════════════════════════════════════════════════════════════════

class Settings:
    """Manages persistent application settings."""

    def __init__(self):
        self._settings = QSettings("Floatube", "Floatube")

    # ── Window ─────────────────────────────────────────────────────────────
    def get_window_pos(self) -> Optional[QPoint]:
        val = self._settings.value("window/position")
        if isinstance(val, QPoint):
            return val
        return None

    def set_window_pos(self, pos: QPoint):
        self._settings.setValue("window/position", pos)

    def get_window_expanded(self) -> bool:
        return self._settings.value("window/expanded", False, type=bool)

    def set_window_expanded(self, expanded: bool):
        self._settings.setValue("window/expanded", expanded)

    # ── Playback ───────────────────────────────────────────────────────────
    def get_volume(self) -> int:
        return self._settings.value("playback/volume", 70, type=int)

    def set_volume(self, volume: int):
        self._settings.setValue("playback/volume", volume)

    def get_shuffle(self) -> bool:
        return self._settings.value("playback/shuffle", False, type=bool)

    def set_shuffle(self, enabled: bool):
        self._settings.setValue("playback/shuffle", enabled)

    def get_repeat(self) -> int:
        return self._settings.value("playback/repeat", 0, type=int)

    def set_repeat(self, mode: int):
        self._settings.setValue("playback/repeat", mode)

    # ── Last Track ─────────────────────────────────────────────────────────
    def get_last_track(self) -> Optional[dict]:
        raw = self._settings.value("playback/last_track")
        if isinstance(raw, str):
            try:
                return json.loads(raw)
            except (json.JSONDecodeError, TypeError):
                return None
        return None

    def set_last_track(self, track_dict: dict):
        self._settings.setValue("playback/last_track", json.dumps(track_dict))

    def clear_last_track(self):
        self._settings.remove("playback/last_track")


# ═══════════════════════════════════════════════════════════════════════════════
#  POSITIONING — Taskbar detection + smart window placement
# ═══════════════════════════════════════════════════════════════════════════════

class _APPBARDATA(ctypes.Structure):
    _fields_ = [
        ("cbSize", ctypes.wintypes.DWORD),
        ("hWnd", ctypes.wintypes.HWND),
        ("uCallbackMessage", ctypes.wintypes.UINT),
        ("uEdge", ctypes.wintypes.UINT),
        ("rc", ctypes.wintypes.RECT),
        ("lParam", ctypes.wintypes.LPARAM),
    ]


class Positioning:
    """Detects taskbar position and calculates default widget placement."""

    ABM_GETTASKBARPOS = 0x00000005
    ABE_LEFT = 0
    ABE_TOP = 1
    ABE_RIGHT = 2
    ABE_BOTTOM = 3

    @staticmethod
    def get_taskbar_rect() -> tuple[int, int, int, int]:
        """Returns (left, top, right, bottom) of the Windows taskbar."""
        try:
            shell32 = ctypes.windll.shell32
            abd = _APPBARDATA()
            abd.cbSize = ctypes.sizeof(_APPBARDATA)
            shell32.SHAppBarMessage(Positioning.ABM_GETTASKBARPOS, ctypes.byref(abd))
            return (abd.rc.left, abd.rc.top, abd.rc.right, abd.rc.bottom)
        except Exception:
            # Fallback: assume bottom taskbar, 48px high
            user32 = ctypes.windll.user32
            sw = user32.GetSystemMetrics(0)  # SM_CXSCREEN
            sh = user32.GetSystemMetrics(1)  # SM_CYSCREEN
            return (0, sh - 48, sw, sh)

    @staticmethod
    def get_taskbar_edge() -> int:
        """Returns which edge the taskbar is on (ABE_LEFT/TOP/RIGHT/BOTTOM)."""
        try:
            shell32 = ctypes.windll.shell32
            abd = _APPBARDATA()
            abd.cbSize = ctypes.sizeof(_APPBARDATA)
            shell32.SHAppBarMessage(Positioning.ABM_GETTASKBARPOS, ctypes.byref(abd))
            return abd.uEdge
        except Exception:
            return Positioning.ABE_BOTTOM

    @staticmethod
    def get_screen_size() -> tuple[int, int]:
        """Returns (width, height) of the primary monitor."""
        user32 = ctypes.windll.user32
        return (user32.GetSystemMetrics(0), user32.GetSystemMetrics(1))

    @staticmethod
    def get_default_position(widget_width: int, widget_height: int, margin: int = 12) -> QPoint:
        """Calculate the default widget position (bottom-right, above taskbar)."""
        screen_w, screen_h = Positioning.get_screen_size()
        tb_rect = Positioning.get_taskbar_rect()
        edge = Positioning.get_taskbar_edge()

        if edge == Positioning.ABE_BOTTOM:
            x = screen_w - widget_width - margin
            y = tb_rect[1] - widget_height - margin
        elif edge == Positioning.ABE_TOP:
            x = screen_w - widget_width - margin
            y = tb_rect[3] + margin
        elif edge == Positioning.ABE_RIGHT:
            x = tb_rect[0] - widget_width - margin
            y = screen_h - widget_height - margin
        elif edge == Positioning.ABE_LEFT:
            x = tb_rect[2] + margin
            y = screen_h - widget_height - margin
        else:
            x = screen_w - widget_width - margin
            y = screen_h - widget_height - margin - 48

        return QPoint(max(0, x), max(0, y))

    @staticmethod
    def clamp_to_screen(pos: QPoint, widget_width: int, widget_height: int) -> QPoint:
        """Ensure the widget stays within screen bounds."""
        screen_w, screen_h = Positioning.get_screen_size()
        x = max(0, min(pos.x(), screen_w - widget_width))
        y = max(0, min(pos.y(), screen_h - widget_height))
        return QPoint(x, y)

    @staticmethod
    def snap_to_edge(pos: QPoint, widget_width: int, widget_height: int,
                     threshold: int = 20) -> QPoint:
        """Snap the widget to screen edges if within threshold."""
        screen_w, screen_h = Positioning.get_screen_size()
        x, y = pos.x(), pos.y()

        # Left edge
        if x < threshold:
            x = 0
        # Right edge
        if x + widget_width > screen_w - threshold:
            x = screen_w - widget_width
        # Top edge
        if y < threshold:
            y = 0
        # Bottom edge (above taskbar)
        tb_rect = Positioning.get_taskbar_rect()
        edge = Positioning.get_taskbar_edge()
        if edge == Positioning.ABE_BOTTOM:
            if y + widget_height > tb_rect[1] - threshold:
                y = tb_rect[1] - widget_height

        return QPoint(x, y)


# ═══════════════════════════════════════════════════════════════════════════════
#  MEDIA KEYS — Global keyboard media key listener
# ═══════════════════════════════════════════════════════════════════════════════

class MediaKeyListener(QObject):
    """Listens for global media key presses (Play/Pause, Next, Previous)."""
    play_pause = pyqtSignal()
    next_track = pyqtSignal()
    prev_track = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._running = False
        self._thread: Optional[threading.Thread] = None

    def start(self):
        """Start listening for global media keys in a daemon thread."""
        if self._running:
            return
        self._running = True
        self._thread = threading.Thread(target=self._listen, daemon=True)
        self._thread.start()

    def stop(self):
        """Stop listening for media keys."""
        self._running = False
        try:
            import keyboard
            keyboard.unhook_all()
        except Exception:
            pass

    def _listen(self):
        """Background thread: register global hotkeys."""
        try:
            import keyboard

            keyboard.on_press_key("play/pause media", lambda _: self.play_pause.emit(), suppress=False)
            keyboard.on_press_key("next track", lambda _: self.next_track.emit(), suppress=False)
            keyboard.on_press_key("previous track", lambda _: self.prev_track.emit(), suppress=False)

            # Keep thread alive
            while self._running:
                import time
                time.sleep(0.5)
        except ImportError:
            pass  # keyboard library not installed, silently skip
        except Exception:
            pass



