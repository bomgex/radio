"""Retry scheduler with exponential backoff, shared by both playback engines."""
from __future__ import annotations

import threading
from typing import Callable, Optional, Sequence

DEFAULT_DELAYS = (2, 4, 8, 15, 30)


class Reconnector:
    """Calls `action` after a growing delay each time `schedule()` is invoked.

    Thread-safe. Only one retry is pending at a time; `reset()` restores the
    shortest delay once playback is healthy again and `cancel()` drops a
    pending retry (user pressed Stop or chose another station).
    """

    def __init__(self, action: Callable[[], None],
                 delays: Sequence[float] = DEFAULT_DELAYS) -> None:
        self._action = action
        self._delays = tuple(delays)
        self._attempt = 0
        self._timer: Optional[threading.Timer] = None
        self._lock = threading.Lock()

    def schedule(self) -> Optional[float]:
        """Arm a retry; returns its delay in seconds, or None if one is already pending."""
        with self._lock:
            if self._timer is not None:
                return None
            delay = self._delays[min(self._attempt, len(self._delays) - 1)]
            self._attempt += 1
            self._timer = threading.Timer(delay, self._fire)
            self._timer.daemon = True
            self._timer.start()
            return delay

    def _fire(self) -> None:
        with self._lock:
            self._timer = None
        self._action()

    def reset(self) -> None:
        with self._lock:
            self._attempt = 0

    def cancel(self) -> None:
        with self._lock:
            if self._timer is not None:
                self._timer.cancel()
                self._timer = None
            self._attempt = 0

    @property
    def pending(self) -> bool:
        return self._timer is not None
