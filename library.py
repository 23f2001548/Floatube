"""
Floatube — Library & Downloads
Manages downloaded tracks and offline playback.
"""
import os
import json
from typing import Optional
from PyQt6.QtCore import QObject, pyqtSignal, QThread

from models import Track

import yt_dlp
from mutagen.mp4 import MP4, MP4Cover
import requests

LIBRARY_PATH = os.path.join(os.path.expanduser("~"), "Music", "Floatube_Downloads")
os.makedirs(LIBRARY_PATH, exist_ok=True)
DB_PATH = os.path.join(LIBRARY_PATH, "library.json")

class LocalLibrary(QObject):
    library_updated = pyqtSignal()
    
    def __init__(self):
        super().__init__()
        self.tracks: list[Track] = []
        self.load_db()
        
    def load_db(self):
        if not os.path.exists(DB_PATH):
            return
        try:
            with open(DB_PATH, "r", encoding="utf-8") as f:
                data = json.load(f)
                self.tracks = [Track.from_dict(d) for d in data]
        except Exception:
            self.tracks = []
            
    def save_db(self):
        with open(DB_PATH, "w", encoding="utf-8") as f:
            json.dump([t.to_dict() for t in self.tracks], f, indent=4)
            
    def add_track(self, track: Track):
        if not any(t.video_id == track.video_id for t in self.tracks):
            self.tracks.append(track)
            self.save_db()
            self.library_updated.emit()
            
    def remove_track(self, video_id: str):
        self.tracks = [t for t in self.tracks if t.video_id != video_id]
        self.save_db()
        self.library_updated.emit()
        
    def is_downloaded(self, video_id: str) -> bool:
        return any(t.video_id == video_id for t in self.tracks)

    def get_track(self, video_id: str) -> Optional[Track]:
        for t in self.tracks:
            if t.video_id == video_id:
                return t
        return None

class DownloadWorker(QThread):
    progress = pyqtSignal(str, int) # video_id, percentage
    finished = pyqtSignal(Track)
    error = pyqtSignal(str, str) # video_id, error
    
    def __init__(self, track: Track):
        super().__init__()
        self.track = track
        
    def run(self):
        try:
            filename = f"{self.track.title} - {self.track.artist}.m4a"
            # Sanitize filename
            filename = "".join(c for c in filename if c.isalnum() or c in " ._-()")
            filepath = os.path.join(LIBRARY_PATH, filename)
            
            if os.path.exists(filepath):
                os.remove(filepath)
                
            ydl_opts = {
                'format': 'bestaudio[ext=m4a]/bestaudio',
                'outtmpl': filepath,
                'quiet': True,
                'no_warnings': True,
            }
            
            def progress_hook(d):
                if d['status'] == 'downloading':
                    try:
                        p = d['_percent_str'].replace('%','').replace('\x1b[0;94m', '').replace('\x1b[0m', '').strip()
                        self.progress.emit(self.track.video_id, int(float(p)))
                    except:
                        pass
            
            ydl_opts['progress_hooks'] = [progress_hook]
            
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                ydl.download([f"https://www.youtube.com/watch?v={self.track.video_id}"])
                
            # Tag with mutagen
            audio = MP4(filepath)
            audio['\xa9nam'] = self.track.title
            audio['\xa9ART'] = self.track.artist
            
            if self.track.thumbnail_url:
                try:
                    resp = requests.get(self.track.thumbnail_url, timeout=5)
                    if resp.status_code == 200:
                        audio['covr'] = [MP4Cover(resp.content, imageformat=MP4Cover.FORMAT_JPEG)]
                except:
                    pass
            audio.save()
            
            # Create a cloned track object marked as local
            local_track = Track(
                video_id=self.track.video_id,
                title=self.track.title,
                artist=self.track.artist,
                album=self.track.album,
                duration_seconds=self.track.duration_seconds,
                thumbnail_url=self.track.thumbnail_url,
                is_local=True,
                local_path=filepath
            )
            self.finished.emit(local_track)
            
        except Exception as e:
            self.error.emit(self.track.video_id, str(e))

class DownloadManager(QObject):
    download_started = pyqtSignal(str) # video_id
    download_progress = pyqtSignal(str, int) # video_id, percentage
    download_finished = pyqtSignal(Track)
    download_error = pyqtSignal(str, str)
    
    def __init__(self, library: LocalLibrary):
        super().__init__()
        self.library = library
        self.active_workers = {}
        
    def download(self, track: Track):
        if track.video_id in self.active_workers:
            return
            
        worker = DownloadWorker(track)
        worker.progress.connect(self.download_progress.emit)
        worker.finished.connect(self._on_finished)
        worker.error.connect(self._on_error)
        
        self.active_workers[track.video_id] = worker
        self.download_started.emit(track.video_id)
        worker.start()
        
    def _on_finished(self, track: Track):
        self.active_workers.pop(track.video_id, None)
        self.library.add_track(track)
        self.download_finished.emit(track)
        
    def _on_error(self, video_id: str, err: str):
        worker = self.active_workers.pop(video_id, None)
        self.download_error.emit(video_id, err)
