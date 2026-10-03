"""Playback engine built on libVLC (python-vlc)."""
from __future__ import annotations

import os
import sys
from typing import Callable, Optional

# On Windows python-vlc must find libvlc.dll; register the standard install
# directory before importing vlc.  Override with the VLC_PATH env variable.
if sys.platform == "win32":
    for candidate in (
        os.environ.get("VLC_PATH"),
        r"C:\Program Files\VideoLAN\VLC",
        r"C:\Program Files (x86)\VideoLAN\VLC",
    ):
        if candidate and os.path.isdir(candidate):
            os.add_dll_directory(candidate)
            os.environ.setdefault("PYTHON_VLC_LIB_PATH", os.path.join(candidate, "libvlc.dll"))
            break

try:
    import vlc
except (ImportError, OSError) as exc:  # pragma: no cover
    raise SystemExit(
        "Не удалось загрузить libVLC. Установите VLC (https://www.videolan.org) "
        "и пакет python-vlc (pip install python-vlc).\n"
        f"Подробности: {exc}"
    )


class RadioPlayer:
    """Thin wrapper around a VLC media player for streaming audio."""

    def __init__(self) -> None:
        self._instance = vlc.Instance("--no-video", "--quiet")
        self._player = self._instance.media_player_new()
        self._media = None
        self.current_url: Optional[str] = None
        self._on_error: Optional[Callable[[], None]] = None
        self._player.event_manager().event_attach(
            vlc.EventType.MediaPlayerEncounteredError, self._handle_error
        )

    # ---- playback ---------------------------------------------------------
    def play(self, url: str) -> None:
        self.stop()
        self._media = self._instance.media_new(url)
        self._player.set_media(self._media)
        self.current_url = url
        self._player.play()

    def stop(self) -> None:
        self._player.stop()
        self.current_url = None

    def is_playing(self) -> bool:
        return bool(self._player.is_playing())

    def state(self) -> str:
        """Human-readable state: Opening / Buffering / Playing / Stopped / Error."""
        return str(self._player.get_state()).split(".")[-1]

    # ---- volume -----------------------------------------------------------
    @property
    def volume(self) -> int:
        return max(0, self._player.audio_get_volume())

    @volume.setter
    def volume(self, value: float) -> None:
        self._player.audio_set_volume(max(0, min(100, int(value))))

    # ---- metadata ---------------------------------------------------------
    def now_playing(self) -> str:
        """Current track from ICY metadata, if the stream provides it."""
        if self._media is None:
            return ""
        return self._media.get_meta(vlc.Meta.NowPlaying) or ""

    # ---- events -----------------------------------------------------------
    def set_error_callback(self, cb: Callable[[], None]) -> None:
        self._on_error = cb

    def _handle_error(self, _event) -> None:
        if self._on_error:
            self._on_error()

    def release(self) -> None:
        if self._instance is None:          # already released
            return
        self._player.stop()
        self._player.release()
        self._instance.release()
        self._player = self._instance = None
