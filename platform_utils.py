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

from PyQt6.QtCore import QObject, QThread, pyqtSignal, QSettings, QPoint, QSize, QMetaObject, Qt as QtCoreQt

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

class Positioning:
    """Calculates widget placement using DPI-aware screen geometry."""

    @staticmethod
    def get_default_position(widget_width: int, widget_height: int, margin: int = 12) -> QPoint:
        """Calculate the default widget position (bottom-right of available screen space)."""
        from PyQt6.QtGui import QGuiApplication
        screen = QGuiApplication.primaryScreen()
        if screen:
            rect = screen.availableGeometry()
            x = rect.right() - widget_width - margin + 1
            y = rect.bottom() - widget_height - margin + 1
            return QPoint(max(rect.left(), x), max(rect.top(), y))
        return QPoint(0, 0)

    @staticmethod
    def clamp_to_screen(pos: QPoint, widget_width: int, widget_height: int) -> QPoint:
        """Ensure the widget stays strictly within the DPI-aware screen bounds."""
        from PyQt6.QtGui import QGuiApplication
        screen = QGuiApplication.primaryScreen()
        if screen:
            rect = screen.availableGeometry()
            x = max(rect.left(), min(pos.x(), rect.right() - widget_width + 1))
            y = max(rect.top(), min(pos.y(), rect.bottom() - widget_height + 1))
            return QPoint(x, y)
        return pos

    @staticmethod
    def snap_to_edge(pos: QPoint, widget_width: int, widget_height: int,
                     threshold: int = 20) -> QPoint:
        """Snap the widget to screen edges if within threshold, and strictly clamp."""
        from PyQt6.QtGui import QGuiApplication
        screen = QGuiApplication.primaryScreen()
        x, y = pos.x(), pos.y()

        if screen:
            rect = screen.availableGeometry()
            
            # Snap to left/right
            if x < rect.left() + threshold:
                x = rect.left()
            elif x + widget_width > rect.right() - threshold + 1:
                x = rect.right() - widget_width + 1
                
            # Snap to top/bottom
            if y < rect.top() + threshold:
                y = rect.top()
            elif y + widget_height > rect.bottom() - threshold + 1:
                y = rect.bottom() - widget_height + 1

            # Strict clamping so it can NEVER be thrown off-screen
            x = max(rect.left(), min(x, rect.right() - widget_width + 1))
            y = max(rect.top(), min(y, rect.bottom() - widget_height + 1))

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
        self._hooks = []

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
            for hook in self._hooks:
                keyboard.unhook(hook)
            self._hooks.clear()
        except Exception:
            pass

    def _listen(self):
        """Background thread: register global hotkeys."""
        try:
            import keyboard

            # Use QMetaObject.invokeMethod for thread-safe signal emission
            self._hooks.append(keyboard.on_press_key(
                "play/pause media",
                lambda _: QMetaObject.invokeMethod(self, "play_pause", QtCoreQt.ConnectionType.QueuedConnection),
                suppress=False))
            self._hooks.append(keyboard.on_press_key(
                "next track",
                lambda _: QMetaObject.invokeMethod(self, "next_track", QtCoreQt.ConnectionType.QueuedConnection),
                suppress=False))
            self._hooks.append(keyboard.on_press_key(
                "previous track",
                lambda _: QMetaObject.invokeMethod(self, "prev_track", QtCoreQt.ConnectionType.QueuedConnection),
                suppress=False))

            # Keep thread alive
            while self._running:
                import time
                time.sleep(0.5)
        except ImportError:
            pass  # keyboard library not installed, silently skip
        except Exception:
            pass



