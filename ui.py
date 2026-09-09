"""
Floatube — UI Layer
All widget classes: MainWindow, TitleBar, SearchPanel, NowPlaying, Controls,
QueuePanel, and TrayIcon. Dark glassmorphism aesthetic.
"""

import io
import requests
from collections import OrderedDict
from typing import Optional

from PyQt6.QtCore import (
    Qt, QTimer, QPoint, QPropertyAnimation, QEasingCurve, QSize,
    pyqtSignal, pyqtSlot, QRect, QByteArray, QThread,
)
from PyQt6.QtGui import (
    QPixmap, QPainter, QColor, QBrush, QPen, QIcon, QFont, QAction,
    QCursor, QMouseEvent, QPaintEvent, QLinearGradient, QRadialGradient, QImage,
)
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QLineEdit,
    QListWidget, QListWidgetItem, QSlider, QSystemTrayIcon, QMenu,
    QSizePolicy, QSpacerItem, QAbstractItemView, QApplication, QGraphicsOpacityEffect,
)

from models import Track
from styles import (
    WIDGET_WIDTH, MINI_HEIGHT, EXPANDED_HEIGHT, CORNER_RADIUS,
    TITLE_BAR_HEIGHT, ART_SIZE, BG_PRIMARY, BG_SECONDARY,
    ACCENT_PRIMARY, ACCENT_SECONDARY, TEXT_PRIMARY, TEXT_SECONDARY,
    TEXT_MUTED, BORDER_SUBTLE,
)
from services import AudioEngine, QueueManager, SearchService, StreamResolver, RepeatMode
from platform_utils import Positioning, Settings, get_asset_path


# ═══════════════════════════════════════════════════════════════════════════════
#  THUMBNAIL LOADER — Async thumbnail download
# ═══════════════════════════════════════════════════════════════════════════════

_thumb_cache: OrderedDict[str, QPixmap] = OrderedDict()
_thumb_workers: list = []  # Keep references to active thumbnail workers


class _ThumbnailWorker(QThread):
    """Background thread that downloads a thumbnail image."""
    finished = pyqtSignal(str, QImage)  # (url, image) — QImage is thread-safe

    def __init__(self, url: str, size: int = 60):
        super().__init__()
        self._url = url
        self._size = size

    def run(self):
        try:
            resp = requests.get(self._url, timeout=5)
            resp.raise_for_status()
            image = QImage()
            image.loadFromData(QByteArray(resp.content))
            self.finished.emit(self._url, image)
        except Exception:
            self.finished.emit(self._url, QImage())  # Empty image signals failure


def _get_cached_thumbnail(url: str, size: int = 60) -> Optional[QPixmap]:
    """Return cached thumbnail if available, or None."""
    if url in _thumb_cache:
        _thumb_cache.move_to_end(url)
        return _thumb_cache[url]
    return None


def _cache_thumbnail(url: str, image: QImage, size: int = 60) -> QPixmap:
    """Process a downloaded QImage into a cached QPixmap. Must be called on the main thread."""
    if image.isNull():
        return _placeholder_pixmap(size)
    pm = QPixmap.fromImage(image)
    pm = pm.scaled(size, size, Qt.AspectRatioMode.KeepAspectRatioByExpanding,
                   Qt.TransformationMode.SmoothTransformation)
    # Center-crop to square
    if pm.width() > size or pm.height() > size:
        x = (pm.width() - size) // 2
        y = (pm.height() - size) // 2
        pm = pm.copy(x, y, size, size)
    _thumb_cache[url] = pm
    if len(_thumb_cache) > 80:
        _thumb_cache.popitem(last=False)  # Evict oldest (true LRU)
    return pm


def _placeholder_pixmap(size: int = 60) -> QPixmap:
    """Generate a dark placeholder with a music note icon."""
    pm = QPixmap(size, size)
    pm.fill(QColor(30, 30, 42))
    painter = QPainter(pm)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    painter.setPen(QPen(QColor(100, 100, 120)))
    font = QFont("Segoe UI", size // 3)
    painter.setFont(font)
    painter.drawText(pm.rect(), Qt.AlignmentFlag.AlignCenter, "♪")
    painter.end()
    return pm


def _rounded_pixmap(pm: QPixmap, radius: int = 10) -> QPixmap:
    """Apply rounded corners to a pixmap."""
    rounded = QPixmap(pm.size())
    rounded.fill(QColor(0, 0, 0, 0))
    painter = QPainter(rounded)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    painter.setBrush(QBrush(pm))
    painter.setPen(Qt.PenStyle.NoPen)
    painter.drawRoundedRect(pm.rect(), radius, radius)
    painter.end()
    return rounded


# ═══════════════════════════════════════════════════════════════════════════════
#  TITLE BAR — Custom draggable title bar with close/minimize
# ═══════════════════════════════════════════════════════════════════════════════

class TitleBar(QWidget):
    """Custom frameless title bar with drag support."""
    minimize_clicked = pyqtSignal()
    close_clicked = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("titleBar")
        self.setFixedHeight(TITLE_BAR_HEIGHT)
        self._drag_pos = None

        layout = QHBoxLayout(self)
        layout.setContentsMargins(10, 0, 6, 0)
        layout.setSpacing(4)

        # App icon (small dot)
        icon_label = QLabel("◉")
        icon_label.setStyleSheet(f"color: {ACCENT_PRIMARY}; font-size: 10px;")
        layout.addWidget(icon_label)

        # Title
        title = QLabel("FLOATUBE")
        title.setObjectName("titleLabel")
        layout.addWidget(title)

        layout.addStretch()

        # Search toggle button
        self.btn_search = QPushButton("")
        self.btn_search.setIcon(QIcon(get_asset_path("icons/search.svg")))
        self.btn_search.setIconSize(QSize(20, 20))
        self.btn_search.setObjectName("btnMinimize")
        self.btn_search.setToolTip("Search")
        self.btn_search.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        layout.addWidget(self.btn_search)

        # Queue toggle button
        self.btn_queue = QPushButton("")
        self.btn_queue.setIcon(QIcon(get_asset_path("icons/queue.svg")))
        self.btn_queue.setIconSize(QSize(20, 20))
        self.btn_queue.setObjectName("btnMinimize")
        self.btn_queue.setToolTip("Queue")
        self.btn_queue.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        layout.addWidget(self.btn_queue)

        # Minimize
        btn_min = QPushButton("")
        btn_min.setIcon(QIcon(get_asset_path("icons/minimize.svg")))
        btn_min.setIconSize(QSize(20, 20))
        btn_min.setObjectName("btnMinimize")
        btn_min.setToolTip("Minimize to tray")
        btn_min.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        btn_min.clicked.connect(self.minimize_clicked.emit)
        layout.addWidget(btn_min)

        # Close
        btn_close = QPushButton("")
        btn_close.setIcon(QIcon(get_asset_path("icons/close.svg")))
        btn_close.setIconSize(QSize(20, 20))
        btn_close.setObjectName("btnClose")
        btn_close.setToolTip("Quit Floatube")
        btn_close.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        btn_close.clicked.connect(self.close_clicked.emit)
        layout.addWidget(btn_close)

    def mousePressEvent(self, event: QMouseEvent):
        if event.button() == Qt.MouseButton.LeftButton:
            self._drag_pos = event.globalPosition().toPoint() - self.window().pos()
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event: QMouseEvent):
        if self._drag_pos and event.buttons() & Qt.MouseButton.LeftButton:
            new_pos = event.globalPosition().toPoint() - self._drag_pos
            # Snap to edges
            window = self.window()
            new_pos = Positioning.snap_to_edge(
                new_pos, window.width(), window.height()
            )
            window.move(new_pos)
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event: QMouseEvent):
        self._drag_pos = None
        super().mouseReleaseEvent(event)


# ═══════════════════════════════════════════════════════════════════════════════
#  SEARCH PANEL — Search bar + results list
# ═══════════════════════════════════════════════════════════════════════════════

class SearchPanel(QWidget):
    """Collapsible search panel with debounced input and results."""
    track_selected = pyqtSignal(object)        # Track
    track_play_next = pyqtSignal(object)       # Track
    track_enqueue = pyqtSignal(object)         # Track

    def __init__(self, search_service: SearchService, parent=None):
        super().__init__(parent)
        self._search = search_service
        self._results: list[Track] = []
        self._loading = False
        self.setVisible(False)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 4, 10, 4)
        layout.setSpacing(6)

        # Search input
        self.search_input = QLineEdit()
        self.search_input.setObjectName("searchInput")
        self.search_input.setPlaceholderText("🔍  Search YouTube Music...")
        self.search_input.setClearButtonEnabled(True)
        layout.addWidget(self.search_input)

        # Results list
        self.results_list = QListWidget()
        self.results_list.setObjectName("searchResults")
        self.results_list.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.results_list.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.results_list.setMinimumHeight(100)
        self.results_list.setMaximumHeight(250)
        self.results_list.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        layout.addWidget(self.results_list)

        # Status label
        self.status_label = QLabel("")
        self.status_label.setObjectName("timeLabel")
        self.status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.status_label)

        # Debounce timer
        self._debounce = QTimer()
        self._debounce.setSingleShot(True)
        self._debounce.setInterval(400)
        self._debounce.timeout.connect(self._do_search)

        # Connections
        self.search_input.textChanged.connect(self._on_text_changed)
        self.results_list.itemClicked.connect(self._on_item_clicked)
        self.results_list.customContextMenuRequested.connect(self._on_context_menu)
        self._search.results_ready.connect(self._on_results)
        self._search.error.connect(self._on_error)

    def _on_text_changed(self, text: str):
        self._debounce.start()

    def _do_search(self):
        query = self.search_input.text().strip()
        if len(query) < 2:
            self.results_list.clear()
            self._results.clear()
            self.status_label.setText("")
            return
        self._loading = True
        self.status_label.setText("Searching...")
        self._search.search(query)

    def _on_results(self, query: str, tracks: list[Track]):
        # Only update if this matches the current query
        current = self.search_input.text().strip()
        if query.strip().lower() != current.strip().lower():
            return
        self._results = tracks
        self._loading = False
        self.results_list.clear()
        if not tracks:
            self.status_label.setText("No results found")
            return
        self.status_label.setText(f"{len(tracks)} results")
        for track in tracks:
            item = QListWidgetItem()
            item.setSizeHint(QSize(0, 48))
            # Format: Title — Artist  [Duration]
            text = f"{track.title}\n{track.artist}  ·  {track.duration_display}"
            item.setText(text)
            item.setToolTip(f"{track.title} — {track.artist}")
            self.results_list.addItem(item)

    def _on_error(self, msg: str):
        self._loading = False
        self.status_label.setText(f"Error: {msg[:50]}")

    def _on_item_clicked(self, item: QListWidgetItem):
        idx = self.results_list.row(item)
        if 0 <= idx < len(self._results):
            self.track_selected.emit(self._results[idx])

    def _on_context_menu(self, pos):
        idx = self.results_list.currentRow()
        if idx < 0 or idx >= len(self._results):
            return
        track = self._results[idx]
        menu = QMenu(self)
        play_next_action = menu.addAction("▶  Play Next")
        enqueue_action = menu.addAction("＋  Add to Queue")
        action = menu.exec(self.results_list.mapToGlobal(pos))
        if action == play_next_action:
            self.track_play_next.emit(track)
        elif action == enqueue_action:
            self.track_enqueue.emit(track)


# ═══════════════════════════════════════════════════════════════════════════════
#  NOW PLAYING — Album art, title, artist, progress bar
# ═══════════════════════════════════════════════════════════════════════════════

class NowPlaying(QWidget):
    """Displays current track info and a seekable progress bar."""
    seek_requested = pyqtSignal(float)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("nowPlaying")
        self._current_track: Optional[Track] = None
        self._duration = 0.0
        self._seeking = False

        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(12, 4, 12, 2)
        main_layout.setSpacing(6)

        # ── Top row: Art + Info ────────────────────────────────────────────
        top = QHBoxLayout()
        top.setSpacing(12)

        # Album art
        self.art_label = QLabel()
        self.art_label.setFixedSize(ART_SIZE, ART_SIZE)
        self.art_label.setStyleSheet(f"border-radius: 10px; background: rgba(30,30,42,0.9);")
        self.art_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.art_label.setPixmap(_rounded_pixmap(_placeholder_pixmap(ART_SIZE), 10))
        top.addWidget(self.art_label)

        # Track info
        info_layout = QVBoxLayout()
        info_layout.setSpacing(2)
        info_layout.addStretch()

        self.title_label = QLabel("No track playing")
        self.title_label.setObjectName("trackTitle")
        self.title_label.setWordWrap(False)
        self.title_label.setMaximumWidth(WIDGET_WIDTH - ART_SIZE - 50)
        info_layout.addWidget(self.title_label)

        self.artist_label = QLabel("Search for music to start")
        self.artist_label.setObjectName("trackArtist")
        self.artist_label.setWordWrap(False)
        info_layout.addWidget(self.artist_label)

        info_layout.addStretch()
        top.addLayout(info_layout)
        top.addStretch()
        main_layout.addLayout(top)

        # ── Progress bar ───────────────────────────────────────────────────
        progress_layout = QHBoxLayout()
        progress_layout.setSpacing(6)

        self.time_current = QLabel("0:00")
        self.time_current.setObjectName("timeLabel")
        self.time_current.setFixedWidth(36)
        progress_layout.addWidget(self.time_current)

        self.progress_slider = QSlider(Qt.Orientation.Horizontal)
        self.progress_slider.setObjectName("progressSlider")
        self.progress_slider.setRange(0, 1000)
        self.progress_slider.setValue(0)
        self.progress_slider.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        progress_layout.addWidget(self.progress_slider)

        self.time_total = QLabel("0:00")
        self.time_total.setObjectName("timeLabel")
        self.time_total.setFixedWidth(36)
        self.time_total.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        progress_layout.addWidget(self.time_total)

        main_layout.addLayout(progress_layout)

        # Slider signals
        self.progress_slider.sliderPressed.connect(lambda: setattr(self, '_seeking', True))
        self.progress_slider.sliderReleased.connect(self._on_seek)

    def set_track(self, track: Track):
        """Update display for a new track."""
        self._current_track = track
        self.title_label.setText(track.title)
        # Elide the title if too long
        metrics = self.title_label.fontMetrics()
        elided = metrics.elidedText(track.title, Qt.TextElideMode.ElideRight,
                                     self.title_label.maximumWidth())
        self.title_label.setText(elided)
        self.artist_label.setText(track.artist)
        self.time_total.setText(track.duration_display)
        self.progress_slider.setValue(0)
        self.time_current.setText("0:00")
        # Load thumbnail (check cache first, then async download)
        cached = _get_cached_thumbnail(track.thumbnail_url, ART_SIZE)
        if cached:
            self.art_label.setPixmap(_rounded_pixmap(cached, 10))
        elif track.thumbnail_url:
            self._load_art_async(track.thumbnail_url)
        else:
            self.art_label.setPixmap(_rounded_pixmap(_placeholder_pixmap(ART_SIZE), 10))

    def _load_art_async(self, url: str):
        """Download thumbnail in a background thread."""
        worker = _ThumbnailWorker(url, ART_SIZE)
        worker.finished.connect(self._on_thumb_loaded)
        worker.finished.connect(lambda: self._cleanup_thumb_worker(worker))
        _thumb_workers.append(worker)
        worker.start()

    def _on_thumb_loaded(self, url: str, image: QImage):
        """Called on main thread when thumbnail download completes."""
        pm = _cache_thumbnail(url, image, ART_SIZE)
        self.art_label.setPixmap(_rounded_pixmap(pm, 10))

    def _cleanup_thumb_worker(self, worker):
        if worker in _thumb_workers:
            _thumb_workers.remove(worker)
        worker.deleteLater()

    def update_position(self, position: float):
        """Update the progress slider and time label."""
        if self._seeking:
            return
        if self._duration > 0:
            ratio = position / self._duration
            self.progress_slider.setValue(int(ratio * 1000))
        mins, secs = divmod(int(position), 60)
        hours, mins = divmod(mins, 60)
        if hours > 0:
            self.time_current.setText(f"{hours}:{mins:02d}:{secs:02d}")
        else:
            self.time_current.setText(f"{mins}:{secs:02d}")

    def update_duration(self, duration: float):
        """Set the total duration."""
        self._duration = duration
        mins, secs = divmod(int(duration), 60)
        hours, mins = divmod(mins, 60)
        if hours > 0:
            self.time_total.setText(f"{hours}:{mins:02d}:{secs:02d}")
        else:
            self.time_total.setText(f"{mins}:{secs:02d}")

    def _on_seek(self):
        self._seeking = False
        if self._duration > 0:
            ratio = self.progress_slider.value() / 1000.0
            self.seek_requested.emit(ratio * self._duration)


# ═══════════════════════════════════════════════════════════════════════════════
#  CONTROLS — Play/Pause, Next, Prev, Volume, Shuffle, Repeat
# ═══════════════════════════════════════════════════════════════════════════════

class Controls(QWidget):
    """Playback control buttons and volume slider."""
    play_pause = pyqtSignal()
    next_track = pyqtSignal()
    prev_track = pyqtSignal()
    volume_changed = pyqtSignal(int)
    shuffle_toggled = pyqtSignal()
    repeat_cycled = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("controls")
        self._is_playing = False

        layout = QHBoxLayout(self)
        layout.setContentsMargins(8, 0, 8, 4)
        layout.setSpacing(4)

        # Shuffle button
        self.btn_shuffle = QPushButton("")
        self.btn_shuffle.setIcon(QIcon(get_asset_path("icons/shuffle.svg")))
        self.btn_shuffle.setIconSize(QSize(20, 20))
        self.btn_shuffle.setProperty("class", "controlBtn")
        self.btn_shuffle.setToolTip("Shuffle")
        self.btn_shuffle.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.btn_shuffle.clicked.connect(self.shuffle_toggled.emit)
        layout.addWidget(self.btn_shuffle)

        layout.addStretch()

        # Previous
        btn_prev = QPushButton("")
        btn_prev.setIcon(QIcon(get_asset_path("icons/prev.svg")))
        btn_prev.setIconSize(QSize(20, 20))
        btn_prev.setProperty("class", "controlBtn")
        btn_prev.setToolTip("Previous")
        btn_prev.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        btn_prev.clicked.connect(self.prev_track.emit)
        layout.addWidget(btn_prev)

        # Play/Pause (larger, accented)
        self.btn_play = QPushButton("")
        self.btn_play.setIcon(QIcon(get_asset_path("icons/play.svg")))
        self.btn_play.setIconSize(QSize(28, 28))
        self.btn_play.setObjectName("btnPlayPause")
        self.btn_play.setToolTip("Play")
        self.btn_play.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.btn_play.clicked.connect(self.play_pause.emit)
        layout.addWidget(self.btn_play)

        # Next
        btn_next = QPushButton("")
        btn_next.setIcon(QIcon(get_asset_path("icons/next.svg")))
        btn_next.setIconSize(QSize(20, 20))
        btn_next.setProperty("class", "controlBtn")
        btn_next.setToolTip("Next")
        btn_next.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        btn_next.clicked.connect(self.next_track.emit)
        layout.addWidget(btn_next)

        layout.addStretch()

        # Repeat button
        self.btn_repeat = QPushButton("")
        self.btn_repeat.setIcon(QIcon(get_asset_path("icons/repeat.svg")))
        self.btn_repeat.setIconSize(QSize(20, 20))
        self.btn_repeat.setProperty("class", "controlBtn")
        self.btn_repeat.setToolTip("Repeat: Off")
        self.btn_repeat.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.btn_repeat.clicked.connect(self.repeat_cycled.emit)
        layout.addWidget(self.btn_repeat)

        # Volume icon
        self.btn_mute = QPushButton("")
        self.btn_mute.setIcon(QIcon(get_asset_path("icons/vol_high.svg")))
        self.btn_mute.setIconSize(QSize(20, 20))
        self.btn_mute.setProperty("class", "controlBtn")
        self.btn_mute.setToolTip("Mute")
        self.btn_mute.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.btn_mute.clicked.connect(self._toggle_mute)
        layout.addWidget(self.btn_mute)

        # Volume slider
        self.volume_slider = QSlider(Qt.Orientation.Horizontal)
        self.volume_slider.setObjectName("volumeSlider")
        self.volume_slider.setRange(0, 100)
        self.volume_slider.setValue(70)
        self.volume_slider.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.volume_slider.valueChanged.connect(self._on_volume)
        layout.addWidget(self.volume_slider)

        self._last_volume = 70

    def set_playing(self, playing: bool):
        self._is_playing = playing
        icon_name = "pause.svg" if playing else "play.svg"
        self.btn_play.setIcon(QIcon(get_asset_path(f"icons/{icon_name}")))
        self.btn_play.setToolTip("Pause" if playing else "Play")

    def set_shuffle_active(self, active: bool):
        icon_name = "shuffle_active.svg" if active else "shuffle.svg"
        self.btn_shuffle.setIcon(QIcon(get_asset_path(f"icons/{icon_name}")))

    def set_repeat_mode(self, mode: int):
        icons = {RepeatMode.OFF: "repeat.svg", RepeatMode.ALL: "repeat_active.svg", RepeatMode.ONE: "repeat_one_active.svg"}
        tips = {RepeatMode.OFF: "Repeat: Off", RepeatMode.ALL: "Repeat: All", RepeatMode.ONE: "Repeat: One"}
        self.btn_repeat.setIcon(QIcon(get_asset_path(f"icons/{icons.get(mode, 'repeat.svg')}")))
        self.btn_repeat.setToolTip(tips.get(mode, "Repeat"))

    def _on_volume(self, value: int):
        self.volume_changed.emit(value)
        if value == 0:
            self.btn_mute.setIcon(QIcon(get_asset_path("icons/vol_mute.svg")))
        elif value < 50:
            self.btn_mute.setIcon(QIcon(get_asset_path("icons/vol_low.svg")))
        else:
            self.btn_mute.setIcon(QIcon(get_asset_path("icons/vol_high.svg")))

    def _toggle_mute(self):
        if self.volume_slider.value() > 0:
            self._last_volume = self.volume_slider.value()
            self.volume_slider.setValue(0)
        else:
            self.volume_slider.setValue(self._last_volume)


# ═══════════════════════════════════════════════════════════════════════════════
#  QUEUE PANEL — Upcoming tracks list
# ═══════════════════════════════════════════════════════════════════════════════

class QueuePanel(QWidget):
    """Collapsible panel showing the upcoming queue."""
    track_clicked = pyqtSignal(int)            # index to play
    track_removed = pyqtSignal(int)            # index to remove

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setVisible(False)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 0, 4, 8)
        layout.setSpacing(2)

        # Header
        header = QLabel("UP NEXT")
        header.setObjectName("queueHeader")
        layout.addWidget(header)

        # Queue list
        self.queue_list = QListWidget()
        self.queue_list.setObjectName("queueList")
        self.queue_list.setMinimumHeight(80)
        self.queue_list.setMaximumHeight(200)
        self.queue_list.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.queue_list.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.queue_list.setDragDropMode(QAbstractItemView.DragDropMode.InternalMove)
        self.queue_list.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.queue_list.customContextMenuRequested.connect(self._on_context_menu)
        self.queue_list.itemDoubleClicked.connect(self._on_double_click)
        layout.addWidget(self.queue_list)

    def update_queue(self, tracks: list[Track]):
        """Refresh the queue display."""
        self.queue_list.clear()
        for i, track in enumerate(tracks):
            item = QListWidgetItem(f"{track.title}  ·  {track.artist}  ·  {track.duration_display}")
            item.setSizeHint(QSize(0, 32))
            item.setToolTip(f"{track.title} — {track.artist}")
            self.queue_list.addItem(item)

    def _on_context_menu(self, pos):
        idx = self.queue_list.currentRow()
        if idx < 0:
            return
        menu = QMenu(self)
        remove_action = menu.addAction("✕  Remove")
        action = menu.exec(self.queue_list.mapToGlobal(pos))
        if action == remove_action:
            self.track_removed.emit(idx)

    def _on_double_click(self, item):
        idx = self.queue_list.row(item)
        self.track_clicked.emit(idx)


# ═══════════════════════════════════════════════════════════════════════════════
#  TRAY ICON — System tray with context menu
# ═══════════════════════════════════════════════════════════════════════════════

class TrayIcon(QSystemTrayIcon):
    """System tray icon with playback controls."""
    show_toggle = pyqtSignal()
    quit_app = pyqtSignal()
    play_pause = pyqtSignal()
    next_track = pyqtSignal()
    prev_track = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._build_icon()
        self._build_menu()
        self.activated.connect(self._on_activated)
        self.setToolTip("Floatube — Not playing")

    def _build_icon(self):
        """Create a simple tray icon programmatically."""
        pm = QPixmap(32, 32)
        pm.fill(QColor(0, 0, 0, 0))
        painter = QPainter(pm)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        # Gradient circle
        gradient = QRadialGradient(16, 16, 16)
        gradient.setColorAt(0, QColor(ACCENT_PRIMARY))
        gradient.setColorAt(1, QColor(ACCENT_SECONDARY))
        painter.setBrush(QBrush(gradient))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawEllipse(2, 2, 28, 28)
        # Play triangle
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QBrush(QColor(255, 255, 255)))
        from PyQt6.QtGui import QPolygon
        painter.drawPolygon(QPolygon([QPoint(12, 8), QPoint(12, 24), QPoint(24, 16)]))
        painter.end()
        self.setIcon(QIcon(pm))

    def _build_menu(self):
        menu = QMenu()
        show_action = QAction("Show / Hide", menu)
        show_action.triggered.connect(self.show_toggle.emit)
        menu.addAction(show_action)

        menu.addSeparator()

        pp_action = QAction("Play / Pause", menu)
        pp_action.triggered.connect(self.play_pause.emit)
        menu.addAction(pp_action)

        next_action = QAction("Next", menu)
        next_action.triggered.connect(self.next_track.emit)
        menu.addAction(next_action)

        prev_action = QAction("Previous", menu)
        prev_action.triggered.connect(self.prev_track.emit)
        menu.addAction(prev_action)

        menu.addSeparator()

        quit_action = QAction("Quit Floatube", menu)
        quit_action.triggered.connect(self.quit_app.emit)
        menu.addAction(quit_action)

        self.setContextMenu(menu)

    def _on_activated(self, reason):
        if reason == QSystemTrayIcon.ActivationReason.DoubleClick:
            self.show_toggle.emit()

    def update_track_info(self, track: Track):
        self.setToolTip(f"Floatube — {track.title} · {track.artist}")


# ═══════════════════════════════════════════════════════════════════════════════
#  MAIN WINDOW — Frameless, translucent, always-on-top widget
# ═══════════════════════════════════════════════════════════════════════════════

class MainWindow(QWidget):
    """Main Frameless Floating Window."""
    close_requested = pyqtSignal()

    def __init__(self, search_service: SearchService, stream_resolver: StreamResolver,
                 audio_engine: AudioEngine, queue_manager: QueueManager,
                 settings: Settings, parent=None):
        super().__init__(parent)

        self._search = search_service
        self._resolver = stream_resolver
        self._engine = audio_engine
        self._queue_mgr = queue_manager
        self._settings = settings
        self._expanded_panel: Optional[str] = None  # "search" or "queue" or None

        # ── Window setup ───────────────────────────────────────────────────
        self.setWindowFlags(
            Qt.WindowType.Window |
            Qt.WindowType.FramelessWindowHint |
            Qt.WindowType.WindowStaysOnTopHint |
            Qt.WindowType.WindowSystemMenuHint |
            Qt.WindowType.WindowMinimizeButtonHint
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setWindowOpacity(0.99)  # Fix invisible window bug on Windows 11
        self.setFixedWidth(WIDGET_WIDTH)
        self.setMinimumHeight(MINI_HEIGHT)
        self.setWindowIcon(QIcon(get_asset_path("icon.png")))

        # ── Build UI ───────────────────────────────────────────────────────
        self._layout = QVBoxLayout(self)
        self._layout.setContentsMargins(0, 0, 0, 0)
        self._layout.setSpacing(0)

        # Title bar
        self.title_bar = TitleBar(self)
        self.title_bar.close_clicked.connect(self.close_requested.emit)
        self.title_bar.minimize_clicked.connect(self.hide)
        self.title_bar.btn_search.clicked.connect(lambda: self._toggle_panel("search"))
        self.title_bar.btn_queue.clicked.connect(lambda: self._toggle_panel("queue"))
        self._layout.addWidget(self.title_bar)

        # Search panel (collapsible)
        self.search_panel = SearchPanel(search_service, self)
        self.search_panel.track_selected.connect(self._on_track_selected)
        self.search_panel.track_play_next.connect(queue_manager.play_next)
        self.search_panel.track_enqueue.connect(queue_manager.enqueue)
        self._layout.addWidget(self.search_panel)

        # Now playing
        self.now_playing = NowPlaying(self)
        self.now_playing.seek_requested.connect(audio_engine.seek)
        self._layout.addWidget(self.now_playing)

        # Controls
        self.controls = Controls(self)
        self.controls.play_pause.connect(self._on_play_pause_clicked)
        self.controls.next_track.connect(queue_manager.next)
        self.controls.prev_track.connect(queue_manager.previous)
        self.controls.volume_changed.connect(audio_engine.set_volume)
        self.controls.shuffle_toggled.connect(self._on_shuffle)
        self.controls.repeat_cycled.connect(self._on_repeat)
        self._layout.addWidget(self.controls)

        # Queue panel (collapsible)
        self.queue_panel = QueuePanel(self)
        self.queue_panel.track_removed.connect(queue_manager.remove_from_queue)
        self.queue_panel.track_clicked.connect(self._on_queue_track_clicked)
        self._layout.addWidget(self.queue_panel)

        # ── Wire engine signals ────────────────────────────────────────────
        audio_engine.state_changed.connect(self._on_state_changed)
        audio_engine.position_changed.connect(self.now_playing.update_position)
        audio_engine.duration_changed.connect(self.now_playing.update_duration)
        queue_manager.current_changed.connect(self._on_current_changed)
        queue_manager.queue_changed.connect(self._on_queue_changed)

        # ── Restore state ──────────────────────────────────────────────────
        vol = settings.get_volume()
        self.controls.volume_slider.setValue(vol)
        audio_engine.set_volume(vol)

        # Position
        saved_pos = settings.get_window_pos()
        if saved_pos:
            self.move(Positioning.clamp_to_screen(saved_pos, WIDGET_WIDTH, MINI_HEIGHT))
        else:
            self.move(Positioning.get_default_position(WIDGET_WIDTH, MINI_HEIGHT))

        # Shuffle/Repeat state
        if settings.get_shuffle():
            queue_manager.toggle_shuffle()
            self.controls.set_shuffle_active(True)
        repeat_mode = settings.get_repeat()
        for _ in range(repeat_mode):
            queue_manager.cycle_repeat()
        self.controls.set_repeat_mode(repeat_mode)

    # ── Painting (rounded dark background) ─────────────────────────────────
    def paintEvent(self, event: QPaintEvent):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        # Dark translucent background
        painter.setBrush(QColor(15, 15, 20, 235))
        painter.setPen(QPen(QColor(255, 255, 255, 20), 1))
        painter.drawRoundedRect(self.rect(), CORNER_RADIUS, CORNER_RADIUS)
        painter.end()

    def showEvent(self, event):
        super().showEvent(event)

    def closeEvent(self, event):
        # Save state before hiding
        self._save_state()
        event.ignore()
        self.hide()

    def moveEvent(self, event):
        super().moveEvent(event)
        # Save position on move
        self._settings.set_window_pos(self.pos())

    # ── Panel toggling ─────────────────────────────────────────────────────
    def _toggle_panel(self, panel_name: str):
        if self._expanded_panel == panel_name:
            # Collapse
            self.search_panel.setVisible(False)
            self.queue_panel.setVisible(False)
            self._expanded_panel = None
            self.setFixedHeight(MINI_HEIGHT)
        else:
            # Expand the requested panel
            self.search_panel.setVisible(panel_name == "search")
            self.queue_panel.setVisible(panel_name == "queue")
            self._expanded_panel = panel_name
            self.setFixedHeight(EXPANDED_HEIGHT)
            if panel_name == "search":
                self.search_panel.search_input.setFocus()

        # Re-position to ensure we don't go off screen
        new_pos = Positioning.clamp_to_screen(self.pos(), self.width(), self.height())
        self.move(new_pos)

    # ── Signal Handlers ────────────────────────────────────────────────────
    def _on_play_pause_clicked(self):
        self._queue_mgr.toggle_playback()

    def _on_track_selected(self, track: Track):
        self._queue_mgr.play_track_and_queue(track)
        # Collapse search after selection
        if self._expanded_panel == "search":
            self._toggle_panel("search")

    def _on_state_changed(self, state: str):
        self.controls.set_playing(state in ("playing", "loading"))

    def _on_current_changed(self, track):
        if track:
            self.now_playing.set_track(track)
            self._settings.set_last_track(track.to_dict())

    def _on_queue_changed(self):
        self.queue_panel.update_queue(self._queue_mgr.queue)

    def _on_shuffle(self):
        self._queue_mgr.toggle_shuffle()
        self.controls.set_shuffle_active(self._queue_mgr.shuffle)
        self._settings.set_shuffle(self._queue_mgr.shuffle)

    def _on_repeat(self):
        mode = self._queue_mgr.cycle_repeat()
        self.controls.set_repeat_mode(mode)
        self._settings.set_repeat(mode)

    def _on_queue_track_clicked(self, index: int):
        """Double-click a track in the queue to skip to it."""
        self._queue_mgr.skip_to(index)

    def _save_state(self):
        self._settings.set_window_pos(self.pos())
        self._settings.set_volume(self._engine.volume)
        self._settings.set_shuffle(self._queue_mgr.shuffle)
        self._settings.set_repeat(self._queue_mgr.repeat)
        if self._queue_mgr.current_track:
            self._settings.set_last_track(self._queue_mgr.current_track.to_dict())
