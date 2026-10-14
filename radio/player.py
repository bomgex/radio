"""Playback engine built on libVLC (python-vlc)."""
from __future__ import annotations

import os
import sys
import threading
import time
from collections import deque
from typing import Optional

from .reconnect import STALL_SECONDS, Reconnector

NETWORK_CACHE_MS = 8000     # seconds of audio VLC keeps ahead; bridges short network stalls
WATCHDOG_PERIOD = 1         # seconds between watchdog samples
EVENT_FRESH_SECONDS = 2     # trust VLC's own buffering percent for this long after it arrives
RATE_WINDOW_SECONDS = 5     # receive rate is averaged over this window (servers send in bursts)
STALL_GRACE_SECONDS = 2     # no data for this long is normal burst spacing, not draining

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
    switch, packet loss).  VLC then reports EndReached or EncounteredError, or
    simply hangs with no data, and stays silent, so we reconnect automatically
    with a growing delay.
    """

    def __init__(self) -> None:
        self._instance = vlc.Instance(
            "--no-video", "--quiet",
            "--http-reconnect",                        # VLC retries short HTTP hiccups itself
            f"--network-caching={NETWORK_CACHE_MS}",
        )
        self._player = self._instance.media_player_new()
        self._media = None
        self.current_url: Optional[str] = None
        self._reconnector = Reconnector(self._reconnect)
        events = self._player.event_manager()
        events.event_attach(vlc.EventType.MediaPlayerEncounteredError, self._on_stream_lost)
        events.event_attach(vlc.EventType.MediaPlayerEndReached, self._on_stream_lost)
        events.event_attach(vlc.EventType.MediaPlayerBuffering, self._on_buffering)

        # Buffer level as VLC reports it (only sent while it (re)buffers) ...
        self._buffer_event = 0
        self._buffer_event_time = 0.0
        # ... and as estimated from the input byte counter: when no data arrives
        # the cache drains at playback speed, so fill = 1 - stalled / cache.
        self._samples: deque[tuple[float, int]] = deque()   # (time, bytes read)
        self._last_bytes = 0
        self._last_bytes_time = 0.0
        self._input_stalled_since: Optional[float] = None
        self._rate_kbs = 0.0
        # Stall detection by playback position (a hung connection fires no event).
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
        self._reset_metrics()
        self._media = self._instance.media_new(url)
        self._player.set_media(self._media)
        self._player.play()

    def stop(self) -> None:
        self._reconnector.cancel()
        self.current_url = None
        self._reset_metrics()
        self._player.stop()

    def _reset_metrics(self) -> None:
        self._buffer_event = 0
        self._buffer_event_time = 0.0
        self._samples.clear()
        self._last_bytes = 0
        self._last_bytes_time = 0.0
        self._input_stalled_since = None
        self._rate_kbs = 0.0
        self._last_pos = -1
        self._last_advance = time.monotonic()

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
        self._buffer_event = 0
        self._buffer_event_time = time.monotonic()
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
                self._sample()
            except Exception:
                pass

    def _sample(self) -> None:
        now = time.monotonic()
        if (self.current_url is None or self._reconnector.pending or self._media is None
                or self._player.get_state() != vlc.State.Playing):
            self._last_pos = -1
            self._last_advance = now
            return

        # Input byte counter -> receive rate and "no data arriving" duration
        stats = vlc.MediaStats()
        if self._media.get_stats(stats):
            read = stats.read_bytes
            self._samples.append((now, read))
            while self._samples and now - self._samples[0][0] > RATE_WINDOW_SECONDS:
                self._samples.popleft()
            t0, b0 = self._samples[0]
            self._rate_kbs = max(0.0, (read - b0) / 1024 / (now - t0)) if now > t0 else 0.0
            if read > self._last_bytes:
                self._last_bytes = read
                self._last_bytes_time = now
                self._input_stalled_since = None
            elif self._input_stalled_since is None:
                self._input_stalled_since = now

        # Playback position -> stalled stream detection
        pos = self._player.get_time()
        if pos != self._last_pos:
            self._last_pos = pos
            self._last_advance = now
        elif now - self._last_advance > STALL_SECONDS:
            self._last_advance = now
            self._buffer_event = 0
            self._buffer_event_time = now
            self._reconnector.schedule()

    # ---- buffer / network -------------------------------------------------
    def _on_buffering(self, event) -> None:
        self._buffer_event = int(event.u.new_cache)
        self._buffer_event_time = time.monotonic()

    @property
    def buffer_percent(self) -> int:
        """Fill level of the playback buffer, 0-100.

        VLC's own figure is used while it is (re)buffering; during normal playback
        the level is estimated from how long no data has been arriving.
        """
        if self.current_url is None:
            return 0
        now = time.monotonic()
        if now - self._buffer_event_time < EVENT_FRESH_SECONDS:
            value = self._buffer_event
        elif self._input_stalled_since is None:
            value = 100
        else:
            stalled = max(0.0, now - self._input_stalled_since - STALL_GRACE_SECONDS)
            value = int(100 * (1 - stalled / (NETWORK_CACHE_MS / 1000)))
        return max(0, min(100, value))

    @property
    def input_rate_kbs(self) -> Optional[float]:
        """Data receive rate in kB/s (None when the engine cannot measure it)."""
        return self._rate_kbs if self.current_url is not None else 0.0

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
