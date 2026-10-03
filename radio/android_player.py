"""Playback engine for Android: the system android.media.MediaPlayer via pyjnius.

Exposes the same interface as radio.player.RadioPlayer so the Kivy UI does not
care which one it talks to.
"""
from __future__ import annotations

import threading
from typing import Callable, Optional

from jnius import autoclass

MediaPlayer = autoclass("android.media.MediaPlayer")
AudioAttributes = autoclass("android.media.AudioAttributes")
AudioAttributesBuilder = autoclass("android.media.AudioAttributes$Builder")


class AndroidPlayer:
    def __init__(self) -> None:
        self._mp = None
        self._volume = 70
        self._state = "Stopped"
        self._generation = 0          # guards against late callbacks of an old stream
        self.current_url: Optional[str] = None
        self._on_error: Optional[Callable[[], None]] = None

    # ---- playback ---------------------------------------------------------
    def play(self, url: str) -> None:
        self.stop()
        self._generation += 1
        gen = self._generation

        mp = MediaPlayer()
        attrs = (AudioAttributesBuilder()
                 .setUsage(AudioAttributes.USAGE_MEDIA)
                 .setContentType(AudioAttributes.CONTENT_TYPE_MUSIC)
                 .build())
        mp.setAudioAttributes(attrs)
        v = self._volume / 100
        mp.setVolume(v, v)

        self._mp = mp
        self.current_url = url
        self._state = "Opening"
        # prepare() blocks while the stream buffers, so run it off the UI thread.
        threading.Thread(target=self._prepare, args=(mp, url, gen), daemon=True).start()

    def _prepare(self, mp, url: str, gen: int) -> None:
        try:
            mp.setDataSource(url)
            mp.prepare()
            if gen != self._generation:        # user switched station meanwhile
                mp.release()
                return
            mp.start()
            self._state = "Playing"
        except Exception:
            if gen == self._generation:
                self._state = "Error"
                if self._on_error:
                    self._on_error()
            try:
                mp.release()
            except Exception:
                pass

    def stop(self) -> None:
        self._generation += 1
        mp, self._mp = self._mp, None
        self.current_url = None
        self._state = "Stopped"
        if mp is not None:
            try:
                if mp.isPlaying():
                    mp.stop()
                mp.release()
            except Exception:
                pass

    def is_playing(self) -> bool:
        return self._state == "Playing"

    def state(self) -> str:
        return self._state

    # ---- volume -----------------------------------------------------------
    @property
    def volume(self) -> int:
        return self._volume

    @volume.setter
    def volume(self, value: float) -> None:
        self._volume = max(0, min(100, int(value)))
        if self._mp is not None:
            v = self._volume / 100
            try:
                self._mp.setVolume(v, v)
            except Exception:
                pass

    # ---- metadata ---------------------------------------------------------
    def now_playing(self) -> str:
        # android.media.MediaPlayer does not expose ICY stream titles.
        return ""

    # ---- events -----------------------------------------------------------
    def set_error_callback(self, cb: Callable[[], None]) -> None:
        self._on_error = cb

    def release(self) -> None:
        self.stop()
