"""
Floatube — Data Models
Track dataclass representing a YouTube Music song.
"""

from dataclasses import dataclass
from datetime import datetime
from typing import Optional


@dataclass
class Track:
    """Represents a single music track from YouTube Music."""
    video_id: str
    title: str
    artist: str
    album: str = ""
    duration_seconds: int = 0
    thumbnail_url: str = ""
    stream_url: Optional[str] = None
    stream_expiry: Optional[datetime] = None

    @property
    def duration_display(self) -> str:
        """Format duration as M:SS or H:MM:SS."""
        if self.duration_seconds <= 0:
            return "0:00"
        mins, secs = divmod(self.duration_seconds, 60)
        hours, mins = divmod(mins, 60)
        if hours > 0:
            return f"{hours}:{mins:02d}:{secs:02d}"
        return f"{mins}:{secs:02d}"

    @property
    def is_stream_valid(self) -> bool:
        """Check if the cached stream URL is still valid."""
        if not self.stream_url or not self.stream_expiry:
            return False
        return datetime.now() < self.stream_expiry

    def to_dict(self) -> dict:
        """Serialize for settings persistence (last played track)."""
        return {
            "video_id": self.video_id,
            "title": self.title,
            "artist": self.artist,
            "album": self.album,
            "duration_seconds": self.duration_seconds,
            "thumbnail_url": self.thumbnail_url,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "Track":
        """Deserialize from settings."""
        return cls(
            video_id=data.get("video_id", ""),
            title=data.get("title", ""),
            artist=data.get("artist", ""),
            album=data.get("album", ""),
            duration_seconds=data.get("duration_seconds", 0),
            thumbnail_url=data.get("thumbnail_url", ""),
        )
