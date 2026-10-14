"""Playback engine for Android: AndroidX Media3 ExoPlayer via pyjnius.

Why ExoPlayer instead of android.media.MediaPlayer: MediaPlayer fails on many
Icecast/Shoutcast AAC streams (ADTS, HE-AAC), exposes no ICY titles and no
buffer information.  ExoPlayer plays them, parses ICY metadata into the media
title, reports the buffered duration and manages audio focus and wake/Wi-Fi
locks itself.

ExoPlayer must only be touched from the Android main (UI) thread, so every
call is posted there with run_on_ui_thread and the results are cached in plain
attributes that the Kivy thread reads.  The public interface matches
radio.player.RadioPlayer.
"""
from __future__ import annotations

import threading
import time
from typing import Optional

from android.runnable import run_on_ui_thread
from jnius import autoclass

from .reconnect import STALL_SECONDS, Reconnector

ExoPlayerBuilder = autoclass("androidx.media3.exoplayer.ExoPlayer$Builder")
MediaItem = autoclass("androidx.media3.common.MediaItem")
AudioAttributesBuilder = autoclass("androidx.media3.common.AudioAttributes$Builder")
C = autoclass("androidx.media3.common.C")
Player = autoclass("androidx.media3.common.Player")
PythonActivity = autoclass("org.kivy.android.PythonActivity")

TARGET_BUFFER_MS = 8000     # buffered audio ahead of playback shown as 100 %
WATCHDOG_PERIOD = 1         # seconds between state samples


class AndroidPlayer:
    def __init__(self) -> None:
        self._player = None
        self._volume = 70
        self._state = "Stopped"
        self._generation = 0          # ignores samples of an already replaced stream
        self.current_url: Optional[str] = None
        self._reconnector = Reconnector(self._reconnect)
        self._buffer = 0
        self._title = ""
        self._last_pos = -1
        self._last_advance = time.monotonic()
        self._closed = False
        self._ui_create()
        threading.Thread(target=self._watchdog, daemon=True).start()

    # ---- ExoPlayer calls (UI thread) ---------------------------------------
    @run_on_ui_thread
    def _ui_create(self) -> None:
        attrs = (AudioAttributesBuilder()
                 .setUsage(C.USAGE_MEDIA)
                 .setContentType(C.AUDIO_CONTENT_TYPE_MUSIC)
                 .build())
        player = ExoPlayerBuilder(PythonActivity.mActivity).build()
        player.setAudioAttributes(attrs, True)      # True: ExoPlayer handles audio focus
        player.setWakeMode(C.WAKE_MODE_NETWORK)     # keep CPU and Wi-Fi awake while playing
        player.setVolume(self._volume / 100)
        self._player = player

    @run_on_ui_thread
    def _ui_start(self, url: str) -> None:
        player = self._player
        if player is None:
            return
        player.stop()
        player.clearMediaItems()
        player.setMediaItem(MediaItem.fromUri(url))
        player.prepare()
        player.setPlayWhenReady(True)

    @run_on_ui_thread
    def _ui_stop(self) -> None:
        player = self._player
        if player is not None:
            player.stop()
            player.clearMediaItems()

    @run_on_ui_thread
    def _ui_set_volume(self, value: float) -> None:
        if self._player is not None:
            self._player.setVolume(value)

    @run_on_ui_thread
    def _ui_release(self) -> None:
        player, self._player = self._player, None
        if player is not None:
            player.release()

    @run_on_ui_thread
    def _ui_sample(self, gen: int) -> None:
        """Read ExoPlayer state into cached attributes; runs once a second."""
        player = self._player
        if player is None or gen != self._generation or self.current_url is None:
            return
        if player.getPlayerError() is not None:
            self._lost()
            return
        playback_state = player.getPlaybackState()
        if playback_state == Player.STATE_ENDED:
            self._lost()
            return

        ahead_ms = player.getBufferedPosition() - player.getCurrentPosition()
        self._buffer = max(0, min(100, int(100 * ahead_ms / TARGET_BUFFER_MS)))

        if playback_state == Player.STATE_READY and player.isPlaying():
            self._state = "Playing"
            self._reconnector.reset()
        elif playback_state == Player.STATE_BUFFERING:
            self._state = "Buffering"

        title = player.getMediaMetadata().title       # ICY StreamTitle, if any
        self._title = str(title) if title is not None else ""

        # Stall detection: a hung connection leaves the player "playing" with
        # the position frozen and no error.
        now = time.monotonic()
        if self._state == "Playing":
            pos = player.getCurrentPosition()
            if pos != self._last_pos:
                self._last_pos = pos
                self._last_advance = now
            elif now - self._last_advance > STALL_SECONDS:
                self._last_advance = now
                self._lost()
        else:
            self._last_advance = now

    # ---- playback (any thread) ----------------------------------------------
    def play(self, url: str) -> None:
        self.stop()
        self.current_url = url
        self._start(url)

    def _start(self, url: str) -> None:
        self._generation += 1
        self._state = "Opening"
        self._buffer = 0
        self._title = ""
        self._last_pos = -1
        self._last_advance = time.monotonic()
        self._ui_start(url)

    def stop(self) -> None:
        self._reconnector.cancel()
        self._generation += 1
        self.current_url = None
        self._state = "Stopped"
        self._buffer = 0
        self._title = ""
        self._ui_stop()

    def is_playing(self) -> bool:
        return self._state == "Playing"

    def state(self) -> str:
        if self._reconnector.pending:
            return "Reconnecting"
        return self._state

    # ---- reconnection -------------------------------------------------------
    def _lost(self) -> None:
        if self.current_url is None:
            return
        self._buffer = 0
        self._state = "Reconnecting"
        self._reconnector.schedule()

    def _reconnect(self) -> None:
        url = self.current_url
        if url is not None:
            self._start(url)

    def _watchdog(self) -> None:
        while not self._closed:
            time.sleep(WATCHDOG_PERIOD)
            try:
                self._ui_sample(self._generation)
            except Exception:
                pass

    # ---- volume -------------------------------------------------------------
    @property
    def volume(self) -> int:
        return self._volume

    @volume.setter
    def volume(self, value: float) -> None:
        self._volume = max(0, min(100, int(value)))
        self._ui_set_volume(self._volume / 100)

    # ---- metadata / buffer --------------------------------------------------
    def now_playing(self) -> str:
        return self._title

    @property
    def buffer_percent(self) -> int:
        """Seconds of audio buffered ahead, as a share of TARGET_BUFFER_MS."""
        return self._buffer

    @property
    def input_rate_kbs(self) -> Optional[float]:
        # ExoPlayer exposes no simple byte counter through this API.
        return None

    def release(self) -> None:
        self._closed = True
        self.stop()
        self._ui_release()
