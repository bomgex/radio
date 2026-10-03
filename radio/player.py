"""Playback engine built on libVLC (python-vlc)."""
from __future__ import annotations

import os
import sys
import threading
import time
from typing import Optional

from .reconnect import Reconnector

STALL_SECONDS = 12      # no playback progress for this long -> reconnect
WATCHDOG_PERIOD = 2

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
        "Could not load libVLC. Install VLC (https://www.videolan.org) "
        "and the python-vlc package (pip install python-vlc).\n"
        f"Details: {exc}"
    )


class RadioPlayer:
    """Thin wrapper around a VLC media player for streaming audio.

    Internet radio streams drop every now and then (server rotation, network
    switch, a lost packet).  VLC then reports EndReached or EncounteredError
    and stays silent, so we reconnect automatically with a growing delay.
    """

    def __init__(self) -> None:
        # --http-reconnect lets VLC itself retry short HTTP hiccups first.
        self._instance = vlc.Instance("--no-video", "--quiet", "--http-reconnect")
        self._player = self._instance.media_player_new()
        self._media = None
        self.current_url: Optional[str] = None
        self._reconnector = Reconnector(self._reconnect)
        events = self._player.event_manager()
        events.event_attach(vlc.EventType.MediaPlayerEncounteredError, self._on_stream_lost)
        events.event_attach(vlc.EventType.MediaPlayerEndReached, self._on_stream_lost)
        # A stalled connection keeps VLC in "Playing" with no data flowing and
        # fires no event, so a watchdog checks that the stream position advances.
        self._last_pos = -1
        self._last_advance = time.monotonic()
        self._closed = False
        threading.Thread(target=self._watchdog, daemon=True).start()

    # ---- playback ---------------------------------------------------------
    def play(self, url: str) -> None:
        self.stop()
        self.current_url = url
        self._start(url)

    def _start(self, url: str) -> None:
        self._media = self._instance.media_new(url)
        self._player.set_media(self._media)
        self._player.play()

    def stop(self) -> None:
        self._reconnector.cancel()
        self.current_url = None
        self._player.stop()

    def is_playing(self) -> bool:
        return bool(self._player.is_playing())

    def state(self) -> str:
        """Opening / Buffering / Playing / Reconnecting / Stopped / Ended / Error."""
        if self._reconnector.pending:
            return "Reconnecting"
        state = str(self._player.get_state()).split(".")[-1]
        if state == "Playing":
            self._reconnector.reset()
        return state

    # ---- reconnection -----------------------------------------------------
    def _on_stream_lost(self, _event) -> None:
        # Runs on VLC's event thread: never call libvlc here, just arm a timer.
        if self.current_url is not None:
            self._reconnector.schedule()

    def _reconnect(self) -> None:
        url = self.current_url
        if url is None:
            return
        self._player.stop()
        self._start(url)

    def _watchdog(self) -> None:
        while not self._closed:
            time.sleep(WATCHDOG_PERIOD)
            try:
                self._check_stall()
            except Exception:
                pass

    def _check_stall(self) -> None:
        now = time.monotonic()
        if (self.current_url is None or self._reconnector.pending
                or self._player.get_state() != vlc.State.Playing):
            self._last_pos = -1
            self._last_advance = now
            return
        pos = self._player.get_time()
        if pos != self._last_pos:
            self._last_pos = pos
            self._last_advance = now
        elif now - self._last_advance > STALL_SECONDS:
            self._last_advance = now
            self._reconnector.schedule()

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

    def release(self) -> None:
        if self._instance is None:          # already released
            return
        self._closed = True
        self.stop()
        self._player.release()
        self._instance.release()
        self._player = self._instance = None
