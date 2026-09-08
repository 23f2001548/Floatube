"""
Floatube — Services Layer
SearchService, StreamResolver, AudioEngine, QueueManager, and caching.
All backend logic in one module.
"""

import random
import time
from collections import deque
from datetime import datetime, timedelta
from typing import Optional

from PyQt6.QtCore import QObject, QThread, pyqtSignal, pyqtSlot, QTimer, QMutex, QMutexLocker

from models import Track


# ═══════════════════════════════════════════════════════════════════════════════
#  CACHE MANAGER — LRU caches with TTL for search results, streams, thumbnails
# ═══════════════════════════════════════════════════════════════════════════════

class CacheManager:
    """Simple TTL-based cache for search results and stream URLs."""

    def __init__(self, max_search=50, max_streams=100):
        self._search_cache: dict[str, tuple[list[Track], datetime]] = {}
        self._stream_cache: dict[str, tuple[str, datetime]] = {}
        self._max_search = max_search
        self._max_streams = max_streams

    # ── Search Cache ───────────────────────────────────────────────────────
    def get_search(self, query: str) -> Optional[list[Track]]:
        key = query.strip().lower()
        if key in self._search_cache:
            results, expiry = self._search_cache[key]
            if datetime.now() < expiry:
                return results
            del self._search_cache[key]
        return None

    def put_search(self, query: str, results: list[Track], ttl_minutes: int = 10):
        key = query.strip().lower()
        if len(self._search_cache) >= self._max_search:
            oldest = next(iter(self._search_cache))
            del self._search_cache[oldest]
        self._search_cache[key] = (results, datetime.now() + timedelta(minutes=ttl_minutes))

    # ── Stream Cache ───────────────────────────────────────────────────────
    def get_stream(self, video_id: str) -> Optional[str]:
        if video_id in self._stream_cache:
            url, expiry = self._stream_cache[video_id]
            if datetime.now() < expiry:
                return url
            del self._stream_cache[video_id]
        return None

    def put_stream(self, video_id: str, url: str, ttl_hours: int = 5):
        if len(self._stream_cache) >= self._max_streams:
            oldest = next(iter(self._stream_cache))
            del self._stream_cache[oldest]
        self._stream_cache[video_id] = (url, datetime.now() + timedelta(hours=ttl_hours))


# Global cache instance
cache = CacheManager()


# ═══════════════════════════════════════════════════════════════════════════════
#  SEARCH SERVICE — ytmusicapi wrapper running searches in background threads
# ═══════════════════════════════════════════════════════════════════════════════

class _SearchWorker(QThread):
    """Background thread that performs a YouTube Music search."""
    results_ready = pyqtSignal(str, list)   # (query, list[Track])
    error = pyqtSignal(str, str)             # (query, error_message)

    def __init__(self, query: str, limit: int = 12):
        super().__init__()
        self._query = query
        self._limit = limit

    def run(self):
        try:
            from ytmusicapi import YTMusic
            yt = YTMusic()
            raw = yt.search(self._query, filter="songs", limit=self._limit)
            tracks = []
            for item in raw:
                if not item.get("videoId"):
                    continue
                # Parse duration string "M:SS" or "H:MM:SS"
                dur_str = item.get("duration", "0:00")
                parts = dur_str.split(":")
                duration = 0
                try:
                    if len(parts) == 3:
                        duration = int(parts[0]) * 3600 + int(parts[1]) * 60 + int(parts[2])
                    elif len(parts) == 2:
                        duration = int(parts[0]) * 60 + int(parts[1])
                except ValueError:
                    pass

                # Get best thumbnail
                thumb = ""
                thumbnails = item.get("thumbnails", [])
                if thumbnails:
                    thumb = thumbnails[-1].get("url", "")

                # Get artist name(s)
                artists = item.get("artists", [])
                artist_name = ", ".join(a.get("name", "") for a in artists) if artists else "Unknown"

                # Get album
                album_info = item.get("album")
                album_name = album_info.get("name", "") if album_info else ""

                tracks.append(Track(
                    video_id=item["videoId"],
                    title=item.get("title", "Unknown"),
                    artist=artist_name,
                    album=album_name,
                    duration_seconds=duration,
                    thumbnail_url=thumb,
                ))

            cache.put_search(self._query, tracks)
            self.results_ready.emit(self._query, tracks)
        except Exception as e:
            self.error.emit(self._query, str(e))


class _WatchPlaylistWorker(QThread):
    """Fetches the 'radio' / related tracks for a given video."""
    results_ready = pyqtSignal(list)  # list[Track]
    error = pyqtSignal(str)

    def __init__(self, video_id: str):
        super().__init__()
        self._video_id = video_id

    def run(self):
        try:
            from ytmusicapi import YTMusic
            yt = YTMusic()
            watch = yt.get_watch_playlist(self._video_id, limit=25)
            tracks = []
            for item in watch.get("tracks", [])[1:]:  # Skip the first (current) track
                if not item.get("videoId"):
                    continue
                dur_str = item.get("length", "0:00") or "0:00"
                parts = dur_str.split(":")
                duration = 0
                try:
                    if len(parts) == 2:
                        duration = int(parts[0]) * 60 + int(parts[1])
                    elif len(parts) == 3:
                        duration = int(parts[0]) * 3600 + int(parts[1]) * 60 + int(parts[2])
                except ValueError:
                    pass
                thumb = ""
                thumbnails = item.get("thumbnail", [])
                if isinstance(thumbnails, list) and thumbnails:
                    thumb = thumbnails[-1].get("url", "")
                artists = item.get("artists", [])
                artist_name = ", ".join(a.get("name", "") for a in artists) if artists else "Unknown"
                album_info = item.get("album")
                album_name = album_info.get("name", "") if album_info else ""

                tracks.append(Track(
                    video_id=item["videoId"],
                    title=item.get("title", "Unknown"),
                    artist=artist_name,
                    album=album_name,
                    duration_seconds=duration,
                    thumbnail_url=thumb,
                ))
            self.results_ready.emit(tracks)
        except Exception as e:
            self.error.emit(str(e))


class SearchService(QObject):
    """High-level search API with caching and background threading."""
    results_ready = pyqtSignal(str, list)       # (query, list[Track])
    watch_playlist_ready = pyqtSignal(list)     # list[Track]
    error = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._workers: list[QThread] = []

    def search(self, query: str, limit: int = 12):
        """Trigger a search. Results arrive via results_ready signal."""
        query = query.strip()
        if not query:
            return
        # Check cache first
        cached = cache.get_search(query)
        if cached:
            self.results_ready.emit(query, cached)
            return
        worker = _SearchWorker(query, limit)
        worker.results_ready.connect(self.results_ready.emit)
        worker.error.connect(lambda q, e: self.error.emit(e))
        worker.finished.connect(lambda: self._cleanup_worker(worker))
        self._workers.append(worker)
        worker.start()

    def get_watch_playlist(self, video_id: str):
        """Fetch related tracks for auto-queue. Results via watch_playlist_ready."""
        worker = _WatchPlaylistWorker(video_id)
        worker.results_ready.connect(self.watch_playlist_ready.emit)
        worker.error.connect(self.error.emit)
        worker.finished.connect(lambda: self._cleanup_worker(worker))
        self._workers.append(worker)
        worker.start()

    def _cleanup_worker(self, worker):
        if worker in self._workers:
            self._workers.remove(worker)
        worker.deleteLater()


# ═══════════════════════════════════════════════════════════════════════════════
#  STREAM RESOLVER — yt-dlp wrapper to extract direct audio URLs
# ═══════════════════════════════════════════════════════════════════════════════

class _ResolveWorker(QThread):
    """Background thread that resolves a stream URL via yt-dlp."""
    resolved = pyqtSignal(str, str)    # (video_id, stream_url)
    error = pyqtSignal(str, str)        # (video_id, error_message)

    def __init__(self, video_id: str):
        super().__init__()
        self._video_id = video_id

    def run(self):
        try:
            import yt_dlp
            url = f"https://music.youtube.com/watch?v={self._video_id}"
            ydl_opts = {
                "format": "bestaudio/best",
                "noplaylist": True,
                "quiet": True,
                "no_warnings": True,
                "extract_flat": False,
            }
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=False)
                stream_url = info.get("url", "")
                if not stream_url:
                    # Fallback: try formats list
                    for fmt in info.get("formats", []):
                        if fmt.get("acodec") != "none" and fmt.get("vcodec") in ("none", None):
                            stream_url = fmt.get("url", "")
                            if stream_url:
                                break
                if stream_url:
                    cache.put_stream(self._video_id, stream_url)
                    self.resolved.emit(self._video_id, stream_url)
                else:
                    self.error.emit(self._video_id, "No audio stream found")
        except Exception as e:
            self.error.emit(self._video_id, str(e))


class StreamResolver(QObject):
    """Resolves video IDs to direct audio stream URLs."""
    resolved = pyqtSignal(str, str)     # (video_id, stream_url)
    error = pyqtSignal(str, str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._workers: list[QThread] = []

    def resolve(self, video_id: str):
        """Resolve a stream URL. Result arrives via resolved signal."""
        cached = cache.get_stream(video_id)
        if cached:
            self.resolved.emit(video_id, cached)
            return
        # Avoid duplicate workers for the same video
        for w in self._workers:
            if isinstance(w, _ResolveWorker) and w._video_id == video_id:
                return
        worker = _ResolveWorker(video_id)
        worker.resolved.connect(self.resolved.emit)
        worker.error.connect(self.error.emit)
        worker.finished.connect(lambda: self._cleanup_worker(worker))
        self._workers.append(worker)
        worker.start()

    def _cleanup_worker(self, worker):
        if worker in self._workers:
            self._workers.remove(worker)
        worker.deleteLater()


# ═══════════════════════════════════════════════════════════════════════════════
#  AUDIO ENGINE — mpv-based playback controller with Qt signals
# ═══════════════════════════════════════════════════════════════════════════════

class AudioEngine(QObject):
    """Controls audio playback via python-mpv."""
    state_changed = pyqtSignal(str)             # "playing" | "paused" | "stopped" | "loading"
    position_changed = pyqtSignal(float)        # Current position in seconds
    duration_changed = pyqtSignal(float)        # Total duration in seconds
    track_finished = pyqtSignal()               # Current track ended naturally
    error = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._player = None
        self._state = "stopped"
        self._position = 0.0
        self._duration = 0.0
        self._volume = 70
        self._poll_timer = QTimer(self)
        self._poll_timer.setInterval(500)       # Poll position every 500ms
        self._poll_timer.timeout.connect(self._poll_position)
        self._init_player()

    def _init_player(self):
        """Initialize the mpv player instance."""
        try:
            import mpv
            self._player = mpv.MPV(
                ytdl=False,
                video=False,
                terminal=False,
                input_default_bindings=False,
                input_vo_keyboard=False,
            )
            self._player.volume = self._volume

            @self._player.event_callback("end-file")
            def _on_end(event):
                data = event.get("event", {})
                # Check if file ended naturally (not stopped by user)
                reason = ""
                if hasattr(event, "reason"):
                    reason = str(event.reason)
                elif isinstance(data, dict):
                    reason = data.get("reason", "")
                # mpv uses "eof" for natural end
                if "eof" in str(event).lower() or self._state == "playing":
                    QTimer.singleShot(0, self.track_finished.emit)

        except Exception as e:
            self._player = None
            self.error.emit(f"Failed to initialize mpv: {e}")

    def play(self, url: str):
        """Play an audio stream from a URL."""
        if not self._player:
            self._init_player()
            if not self._player:
                return
        try:
            self._state = "loading"
            self.state_changed.emit("loading")
            self._player.play(url)
            self._player.pause = False
            self._state = "playing"
            self.state_changed.emit("playing")
            self._poll_timer.start()
        except Exception as e:
            self._state = "stopped"
            self.state_changed.emit("stopped")
            self.error.emit(f"Playback error: {e}")

    def toggle(self):
        """Toggle play/pause."""
        if not self._player:
            return
        if self._state == "playing":
            self.pause()
        elif self._state == "paused":
            self.resume()

    def pause(self):
        """Pause playback."""
        if self._player and self._state == "playing":
            try:
                self._player.pause = True
                self._state = "paused"
                self.state_changed.emit("paused")
            except Exception:
                pass

    def resume(self):
        """Resume playback."""
        if self._player and self._state == "paused":
            try:
                self._player.pause = False
                self._state = "playing"
                self.state_changed.emit("playing")
            except Exception:
                pass

    def stop(self):
        """Stop playback completely."""
        if self._player:
            try:
                self._player.stop()
            except Exception:
                pass
        self._state = "stopped"
        self._poll_timer.stop()
        self.state_changed.emit("stopped")
        self.position_changed.emit(0.0)

    def seek(self, position: float):
        """Seek to a position in seconds."""
        if self._player and self._state in ("playing", "paused"):
            try:
                self._player.seek(position, "absolute")
            except Exception:
                pass

    def set_volume(self, volume: int):
        """Set volume (0-100)."""
        self._volume = max(0, min(100, volume))
        if self._player:
            try:
                self._player.volume = self._volume
            except Exception:
                pass

    @property
    def volume(self) -> int:
        return self._volume

    @property
    def state(self) -> str:
        return self._state

    @property
    def position(self) -> float:
        return self._position

    @property
    def duration(self) -> float:
        return self._duration

    def _poll_position(self):
        """Periodically read position/duration from mpv."""
        if not self._player:
            return
        try:
            pos = self._player.time_pos
            dur = self._player.duration
            if pos is not None:
                self._position = float(pos)
                self.position_changed.emit(self._position)
            if dur is not None and dur != self._duration:
                self._duration = float(dur)
                self.duration_changed.emit(self._duration)
        except Exception:
            pass

    def cleanup(self):
        """Release mpv resources."""
        self._poll_timer.stop()
        if self._player:
            try:
                self._player.terminate()
            except Exception:
                pass
            self._player = None


# ═══════════════════════════════════════════════════════════════════════════════
#  QUEUE MANAGER — Track queue with shuffle, repeat, auto-populate
# ═══════════════════════════════════════════════════════════════════════════════

class RepeatMode:
    OFF = 0
    ALL = 1
    ONE = 2


class QueueManager(QObject):
    """Manages playback queue, shuffle, repeat, and auto-queue."""
    current_changed = pyqtSignal(object)        # Track or None
    queue_changed = pyqtSignal()                # Queue contents updated
    request_play = pyqtSignal(str)              # video_id to resolve and play

    def __init__(self, search_service: SearchService, stream_resolver: StreamResolver,
                 audio_engine: AudioEngine, parent=None):
        super().__init__(parent)
        self._search = search_service
        self._resolver = stream_resolver
        self._engine = audio_engine

        self._queue: deque[Track] = deque()
        self._history: list[Track] = []
        self._current: Optional[Track] = None
        self._shuffle = False
        self._repeat = RepeatMode.OFF
        self._original_queue: list[Track] = []  # Pre-shuffle order

        # Wire signals
        self._engine.track_finished.connect(self._on_track_finished)
        self._resolver.resolved.connect(self._on_stream_resolved)
        self._resolver.error.connect(self._on_resolve_error)
        self._search.watch_playlist_ready.connect(self._on_watch_playlist)

    # ── Public API ─────────────────────────────────────────────────────────
    @property
    def current_track(self) -> Optional[Track]:
        return self._current

    @property
    def queue(self) -> list[Track]:
        return list(self._queue)

    @property
    def shuffle(self) -> bool:
        return self._shuffle

    @property
    def repeat(self) -> int:
        return self._repeat

    def play_track(self, track: Track):
        """Play a track immediately and set it as current."""
        if self._current:
            self._history.append(self._current)
        self._current = track
        self.current_changed.emit(track)
        self._resolver.resolve(track.video_id)

    def load_track(self, track: Track):
        """Load a track as current without playing it immediately."""
        self._current = track
        self.current_changed.emit(track)

    def play_current(self):
        """Play the currently loaded track (used for resuming state)."""
        if self._current:
            self._resolver.resolve(self._current.video_id)

    def play_track_and_queue(self, track: Track, related: list[Track] = None):
        """Play a track and replace queue with related tracks."""
        self._queue.clear()
        self.play_track(track)
        if related:
            self._queue.extend(related)
        else:
            # Fetch radio/related tracks
            self._search.get_watch_playlist(track.video_id)
        self.queue_changed.emit()

    def enqueue(self, track: Track):
        """Add a track to the end of the queue."""
        self._queue.append(track)
        self.queue_changed.emit()

    def play_next(self, track: Track):
        """Insert a track at the front of the queue."""
        self._queue.appendleft(track)
        self.queue_changed.emit()

    def next(self):
        """Skip to the next track."""
        if self._repeat == RepeatMode.ONE and self._current:
            self._resolver.resolve(self._current.video_id)
            return

        if self._queue:
            if self._current:
                self._history.append(self._current)
            track = self._queue.popleft()
            self._current = track
            self.current_changed.emit(track)
            self._resolver.resolve(track.video_id)
            self.queue_changed.emit()
            # Pre-resolve the next one
            if self._queue:
                self._resolver.resolve(self._queue[0].video_id)
        elif self._repeat == RepeatMode.ALL and self._history:
            # Restart from history
            self._queue.extend(self._history)
            self._history.clear()
            if self._shuffle:
                self._shuffle_queue()
            self.next()
        elif self._current:
            # Queue empty, fetch more related tracks
            self._search.get_watch_playlist(self._current.video_id)

    def previous(self):
        """Go back to the previous track."""
        if self._history:
            if self._current:
                self._queue.appendleft(self._current)
            self._current = self._history.pop()
            self.current_changed.emit(self._current)
            self._resolver.resolve(self._current.video_id)
            self.queue_changed.emit()

    def clear(self):
        """Clear the queue."""
        self._queue.clear()
        self._original_queue.clear()
        self.queue_changed.emit()

    def remove_from_queue(self, index: int):
        """Remove a track from the queue by index."""
        if 0 <= index < len(self._queue):
            q_list = list(self._queue)
            q_list.pop(index)
            self._queue = deque(q_list)
            self.queue_changed.emit()

    def move_in_queue(self, from_idx: int, to_idx: int):
        """Move a track within the queue (drag-to-reorder)."""
        q_list = list(self._queue)
        if 0 <= from_idx < len(q_list) and 0 <= to_idx < len(q_list):
            item = q_list.pop(from_idx)
            q_list.insert(to_idx, item)
            self._queue = deque(q_list)
            self.queue_changed.emit()

    def toggle_shuffle(self):
        """Toggle shuffle mode."""
        self._shuffle = not self._shuffle
        if self._shuffle:
            self._original_queue = list(self._queue)
            self._shuffle_queue()
        else:
            # Restore original order
            if self._original_queue:
                self._queue = deque(self._original_queue)
                self._original_queue.clear()
        self.queue_changed.emit()

    def cycle_repeat(self) -> int:
        """Cycle: Off -> All -> One -> Off. Returns new mode."""
        self._repeat = (self._repeat + 1) % 3
        return self._repeat

    # ── Private ────────────────────────────────────────────────────────────
    def _shuffle_queue(self):
        q_list = list(self._queue)
        random.shuffle(q_list)
        self._queue = deque(q_list)

    def _on_track_finished(self):
        """Called when the audio engine finishes a track."""
        self.next()

    def _on_stream_resolved(self, video_id: str, stream_url: str):
        """Called when a stream URL is resolved. Play if it's the current track."""
        if self._current and self._current.video_id == video_id:
            self._current.stream_url = stream_url
            self._current.stream_expiry = datetime.now() + timedelta(hours=5)
            self._engine.play(stream_url)

    def _on_resolve_error(self, video_id: str, error_msg: str):
        """Handle stream resolution failure — skip to next."""
        if self._current and self._current.video_id == video_id:
            self._engine.error.emit(f"Cannot play: {error_msg}")
            # Auto-skip after a brief delay
            QTimer.singleShot(1000, self.next)

    def _on_watch_playlist(self, tracks: list[Track]):
        """Received related tracks from search service."""
        # Only add tracks that aren't already in the queue
        existing_ids = {t.video_id for t in self._queue}
        if self._current:
            existing_ids.add(self._current.video_id)
        new_tracks = [t for t in tracks if t.video_id not in existing_ids]
        self._queue.extend(new_tracks)
        if self._shuffle:
            self._shuffle_queue()
        self.queue_changed.emit()
        # If we had no queue and were waiting, start playing
        if self._queue and self._engine.state == "stopped":
            self.next()
        # Pre-resolve first in queue
        if self._queue:
            self._resolver.resolve(self._queue[0].video_id)
