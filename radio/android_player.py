"""Playback engine for Android: the system android.media.MediaPlayer via pyjnius.

Exposes the same interface as radio.player.RadioPlayer so the Kivy UI does not
care which one it talks to.  Stream drops (onError / onCompletion) and failed
connections trigger an automatic reconnect with a growing delay.
"""
from __future__ import annotations

import threading
from typing import Optional

from jnius import PythonJavaClass, autoclass, java_method

from .reconnect import Reconnector

MediaPlayer = autoclass("android.media.MediaPlayer")
AudioAttributes = autoclass("android.media.AudioAttributes")
AudioAttributesBuilder = autoclass("android.media.AudioAttributes$Builder")
AudioManager = autoclass("android.media.AudioManager")
Context = autoclass("android.content.Context")
PythonActivity = autoclass("org.kivy.android.PythonActivity")

DUCK_VOLUME = 0.2


class _OnErrorListener(PythonJavaClass):
    __javainterfaces__ = ["android/media/MediaPlayer$OnErrorListener"]
    __javacontext__ = "app"

    def __init__(self, callback):
        super().__init__()
        self._callback = callback

    @java_method("(Landroid/media/MediaPlayer;II)Z")
    def onError(self, mp, what, extra):
        self._callback(mp)
        return True          # handled: suppress the default onCompletion call


class _OnCompletionListener(PythonJavaClass):
    __javainterfaces__ = ["android/media/MediaPlayer$OnCompletionListener"]
    __javacontext__ = "app"

    def __init__(self, callback):
        super().__init__()
        self._callback = callback

    @java_method("(Landroid/media/MediaPlayer;)V")
    def onCompletion(self, mp):
        self._callback(mp)


class _AudioFocusListener(PythonJavaClass):
    __javainterfaces__ = ["android/media/AudioManager$OnAudioFocusChangeListener"]
    __javacontext__ = "app"

    def __init__(self, callback):
        super().__init__()
        self._callback = callback

    @java_method("(I)V")
    def onAudioFocusChange(self, change):
        self._callback(change)


class AndroidPlayer:
    def __init__(self) -> None:
        self._mp = None
        self._volume = 70
        self._state = "Stopped"
        self._generation = 0          # guards against late callbacks of an old stream
        self.current_url: Optional[str] = None
        self._reconnector = Reconnector(self._reconnect)
        # Keep listener objects alive: Java holds only weak references to them.
        self._on_error = _OnErrorListener(self._on_stream_lost)
        self._on_completion = _OnCompletionListener(self._on_stream_lost)
        self._focus_listener = _AudioFocusListener(self._on_focus_change)
        self._audio_manager = PythonActivity.mActivity.getSystemService(Context.AUDIO_SERVICE)

    # ---- playback ---------------------------------------------------------
    def play(self, url: str) -> None:
        self.stop()
        self.current_url = url
        self._audio_manager.requestAudioFocus(
            self._focus_listener, AudioManager.STREAM_MUSIC, AudioManager.AUDIOFOCUS_GAIN)
        self._start(url)

    def _start(self, url: str) -> None:
        self._release_mp()
        self._generation += 1
        gen = self._generation

        mp = MediaPlayer()
        attrs = (AudioAttributesBuilder()
                 .setUsage(AudioAttributes.USAGE_MEDIA)
                 .setContentType(AudioAttributes.CONTENT_TYPE_MUSIC)
                 .build())
        mp.setAudioAttributes(attrs)
        mp.setOnErrorListener(self._on_error)
        mp.setOnCompletionListener(self._on_completion)
        v = self._volume / 100
        mp.setVolume(v, v)

        self._mp = mp
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
            self._reconnector.reset()
        except Exception:
            if gen == self._generation and self.current_url is not None:
                self._state = "Reconnecting"
                self._reconnector.schedule()

    def _release_mp(self) -> None:
        mp, self._mp = self._mp, None
        if mp is not None:
            try:
                mp.reset()
                mp.release()
            except Exception:
                pass

    def stop(self) -> None:
        self._reconnector.cancel()
        self._generation += 1
        self.current_url = None
        self._state = "Stopped"
        self._release_mp()
        try:
            self._audio_manager.abandonAudioFocus(self._focus_listener)
        except Exception:
            pass

    def is_playing(self) -> bool:
        return self._state == "Playing"

    def state(self) -> str:
        if self._reconnector.pending:
            return "Reconnecting"
        return self._state

    # ---- reconnection -----------------------------------------------------
    def _on_stream_lost(self, mp) -> None:
        # Called from a Java thread, possibly for an already replaced player.
        current = self._mp
        if current is None or not mp.equals(current) or self.current_url is None:
            return
        self._state = "Reconnecting"
        self._reconnector.schedule()

    def _reconnect(self) -> None:
        url = self.current_url
        if url is not None:
            self._start(url)

    # ---- audio focus ------------------------------------------------------
    def _on_focus_change(self, change: int) -> None:
        mp = self._mp
        if mp is None:
            return
        try:
            if change == AudioManager.AUDIOFOCUS_LOSS_TRANSIENT_CAN_DUCK:
                mp.setVolume(DUCK_VOLUME, DUCK_VOLUME)
            elif change == AudioManager.AUDIOFOCUS_LOSS_TRANSIENT:
                if mp.isPlaying():
                    mp.pause()
            elif change == AudioManager.AUDIOFOCUS_GAIN:
                v = self._volume / 100
                mp.setVolume(v, v)
                if self._state == "Playing" and not mp.isPlaying():
                    mp.start()
        except Exception:
            pass

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

    def release(self) -> None:
        self.stop()
