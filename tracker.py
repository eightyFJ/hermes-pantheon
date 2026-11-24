"""Per-session state that turns Hermes hook calls into terminal events."""

from __future__ import annotations

import threading
from collections.abc import Callable
from dataclasses import dataclass, field

from .gods import IDLE, WAITING, WORKING, get_god
from .title import DEFAULT_LABEL, clean_label

TONES = {WORKING: "strong", WAITING: "warn", IDLE: "dim"}
CLEAR = {"clear": True}

Sink = Callable[[str, dict], None]


@dataclass(frozen=True)
class Scene:
    god: str
    state: str
    frames: tuple[str, ...]
    interval_ms: int
    label: str
    status: str

    def payload(self) -> dict:
        return {
            "frames": list(self.frames),
            "interval_ms": self.interval_ms,
            "label": self.label or DEFAULT_LABEL,
            "status": self.status,
            "tone": TONES[self.state],
            "state": self.state,
            "god": self.god,
        }


@dataclass
class _Session:
    god: str = ""
    label: str = ""
    state: str = IDLE
    waits: set[str] = field(default_factory=set)


class Tracker:
    """Thread-safe session states; calls ``sink(session_id, payload)`` whenever one changes."""

    def __init__(self, sink: Sink, *, default_god: Callable[[], str] = lambda: "") -> None:
        self._sink = sink
        self._default_god = default_god
        self._sessions: dict[str, _Session] = {}
        self._lock = threading.Lock()

    def working(self, session_id: str, *, label: str = "") -> None:
        self._update(session_id, state=WORKING, label=clean_label(label))

    def done(self, session_id: str, *, label: str = "") -> None:
        self._update(session_id, state=IDLE, label=clean_label(label), clear_waits=True)

    def wait_start(self, session_id: str, request_id: str) -> None:
        with self._lock:
            self._sessions.setdefault(session_id, _Session()).waits.add(request_id or "?")
        self._update(session_id, state=WAITING)

    def wait_end(self, session_id: str, request_id: str) -> None:
        with self._lock:
            session = self._sessions.get(session_id)
            if session is None:
                return
            session.waits.discard(request_id or "?")
            still_waiting = bool(session.waits)
        if not still_waiting:
            self._update(session_id, state=WORKING)

    def set_label(self, session_id: str, label: str) -> str:
        cleaned = clean_label(label)
        self._update(session_id, label=cleaned)
        return cleaned

    def set_god(self, session_id: str, god: str) -> None:
        self._update(session_id, god=get_god(god).key)

    def forget(self, session_id: str) -> None:
        with self._lock:
            existed = self._sessions.pop(session_id, None) is not None
        if existed:
            self._sink(session_id, dict(CLEAR))

    def has(self, session_id: str) -> bool:
        with self._lock:
            return session_id in self._sessions

    def only_active(self) -> str | None:
        with self._lock:
            active = [sid for sid, s in self._sessions.items() if s.state != IDLE]
        return active[0] if len(active) == 1 else None

    def scene(self, session_id: str) -> Scene:
        with self._lock:
            session = self._sessions.get(session_id) or _Session()
            god_key, state, label = session.god, session.state, session.label
        god = get_god(god_key or self._default_god())
        act = god.act(state)
        return Scene(god.key, state, act.frames, act.interval_ms, label, act.phrase)

    def _update(
        self, session_id: str, *, state: str | None = None, label: str = "", god: str = "", clear_waits: bool = False
    ) -> None:
        if not session_id:
            return
        with self._lock:
            session = self._sessions.setdefault(session_id, _Session())
            before = (session.god, session.label, session.state)
            session.state = state or session.state
            session.label = label or session.label
            session.god = god or session.god
            if clear_waits:
                session.waits.clear()
            changed = (session.god, session.label, session.state) != before
        if changed:
            self._sink(session_id, self.scene(session_id).payload())
