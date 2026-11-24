"""Animate frames in this process's own console title (used by ``hermes pantheon preview``)."""

from __future__ import annotations

import os
import threading
from collections.abc import Sequence

from .title import compose


class ConsoleTitle:
    """Sets the console title, and restores the one it found."""

    def __init__(self) -> None:
        self._kernel32 = None
        self._original: str | None = None
        if os.name == "nt":
            self._attach_windows_console()

    def _attach_windows_console(self) -> None:
        try:
            import ctypes

            kernel32 = ctypes.windll.kernel32
            buffer = ctypes.create_unicode_buffer(1024)
            if kernel32.GetConsoleTitleW(buffer, len(buffer)):
                self._original = buffer.value
            self._kernel32 = kernel32
        except (AttributeError, OSError):
            self._kernel32 = None

    def set(self, title: str) -> None:
        try:
            if self._kernel32 is not None:
                self._kernel32.SetConsoleTitleW(title)
            else:
                with open("/dev/tty", "w", encoding="utf-8") as tty:
                    tty.write(f"\x1b]2;{title}\x07")
        except OSError:
            pass

    def restore(self) -> None:
        self.set(self._original if self._original is not None else "hermes")


class Animator:
    """Cycles frames on a daemon thread until ``stop()``, which restores the title."""

    def __init__(self, console: ConsoleTitle | None = None) -> None:
        self.console = console or ConsoleTitle()
        self._frames: Sequence[str] = ()
        self._interval = 0.0
        self._label = ""
        self._changed = threading.Event()
        self._stopped = threading.Event()
        self._thread = threading.Thread(target=self._run, name="pantheon-title", daemon=True)
        self._thread.start()

    def show(self, frames: Sequence[str], interval_ms: int, label: str) -> None:
        self._frames, self._interval, self._label = tuple(frames), interval_ms / 1000, label
        self._changed.set()

    def stop(self) -> None:
        self._stopped.set()
        self._changed.set()
        self._thread.join(timeout=1)
        self.console.restore()

    def _run(self) -> None:
        index = 0
        while not self._stopped.is_set():
            frames, interval, label = self._frames, self._interval, self._label
            if frames:
                self.console.set(compose(frames[index % len(frames)], label))
            animating = len(frames) > 1 and interval > 0
            if self._changed.wait(interval if animating else None):
                self._changed.clear()
                index = 0
            else:
                index += 1
