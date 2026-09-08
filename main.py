"""
Floatube — Entry Point
Wires all services, creates the UI, and launches the application.
"""

import sys
import os

# Ensure mpv DLL can be found — must be done before importing mpv (via services)
# For PyInstaller bundles, add the extraction directory
if hasattr(sys, "_MEIPASS"):
    os.environ["PATH"] = sys._MEIPASS + os.pathsep + os.environ["PATH"]
    os.add_dll_directory(sys._MEIPASS)

# For normal execution, add the script's directory (where libmpv-2.dll lives)
_script_dir = os.path.dirname(os.path.abspath(__file__))
os.environ["PATH"] = _script_dir + os.pathsep + os.environ["PATH"]

from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QFont, QIcon

from models import Track
from styles import STYLESHEET
from services import SearchService, StreamResolver, AudioEngine, QueueManager
from platform_utils import Settings, MediaKeyListener, Positioning, get_asset_path
from ui import MainWindow, TrayIcon


def main():
    # High-DPI
    QApplication.setHighDpiScaleFactorRoundingPolicy(
        Qt.HighDpiScaleFactorRoundingPolicy.PassThrough
    )

    # if sys.platform == "win32":
    #     import ctypes
    #     ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("floatube.desktop.widget")

    # ── Application setup ──────────────────────────────────────────────────
    app = QApplication(sys.argv)
    app.setApplicationName("Floatube")
    app.setOrganizationName("Floatube")
    app.setWindowIcon(QIcon(get_asset_path("icon.png")))
    app.setQuitOnLastWindowClosed(False)
    app.setStyleSheet(STYLESHEET)

    # Default font
    font = QFont("Segoe UI", 10)
    app.setFont(font)

    # ── Instantiate services ───────────────────────────────────────────────
    settings = Settings()
    audio_engine = AudioEngine()
    search_service = SearchService()
    stream_resolver = StreamResolver()
    queue_manager = QueueManager(search_service, stream_resolver, audio_engine)

    # ── Instantiate UI ─────────────────────────────────────────────────────
    window = MainWindow(
        search_service=search_service,
        stream_resolver=stream_resolver,
        audio_engine=audio_engine,
        queue_manager=queue_manager,
        settings=settings,
    )

    tray = TrayIcon()
    tray.show_toggle.connect(lambda: window.setVisible(not window.isVisible()))
    tray.quit_app.connect(lambda: _shutdown(app, audio_engine, media_keys, settings, window))
    tray.play_pause.connect(audio_engine.toggle)
    tray.next_track.connect(queue_manager.next)
    tray.prev_track.connect(queue_manager.previous)

    # Update tray tooltip when track changes
    queue_manager.current_changed.connect(
        lambda t: tray.update_track_info(t) if t else None
    )

    tray.show()

    # ── Media keys ─────────────────────────────────────────────────────────
    media_keys = MediaKeyListener()
    media_keys.play_pause.connect(audio_engine.toggle)
    media_keys.next_track.connect(queue_manager.next)
    media_keys.prev_track.connect(queue_manager.previous)
    media_keys.start()

    # ── Resume last track (display only, don't auto-play) ──────────────────
    last_track_data = settings.get_last_track()
    if last_track_data:
        try:
            last_track = Track.from_dict(last_track_data)
            queue_manager.load_track(last_track)
        except Exception:
            pass

    # ── Show window ────────────────────────────────────────────────────────
    window.close_requested.connect(tray.quit_app.emit)
    window.show()

    # ── Run ────────────────────────────────────────────────────────────────
    sys.exit(app.exec())


def _shutdown(app, audio_engine, media_keys, settings, window):
    """Graceful cleanup before quitting."""
    # Save state
    settings.set_window_pos(window.pos())
    settings.set_volume(audio_engine.volume)

    # Stop services
    media_keys.stop()
    audio_engine.cleanup()

    app.quit()


def run_app():
    try:
        main()
    except Exception as e:
        import traceback
        with open("floatube_crash.log", "w") as f:
            f.write(traceback.format_exc())
        raise

if __name__ == "__main__":
    run_app()
