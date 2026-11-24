"""The gods, loaded from ``gods.toml``: emoji frames and a status phrase for each state."""

from __future__ import annotations

import tomllib
from dataclasses import dataclass
from pathlib import Path

WORKING, WAITING, IDLE = "working", "waiting", "idle"
STATES = (WORKING, WAITING, IDLE)
DEFAULT_GOD = "hephaestus"


@dataclass(frozen=True)
class Act:
    frames: tuple[str, ...]
    interval_ms: int
    phrase: str


@dataclass(frozen=True)
class God:
    key: str
    name: str
    epithet: str
    acts: dict[str, Act]

    def act(self, state: str) -> Act:
        return self.acts[state]


def _load(path: Path) -> dict[str, God]:
    table = tomllib.loads(path.read_text(encoding="utf-8"))
    return {
        key: God(
            key,
            god["name"],
            god["epithet"],
            {
                state: Act(tuple(god[state]["frames"]), god[state].get("ms", 0), god[state]["phrase"])
                for state in STATES
            },
        )
        for key, god in table.items()
    }


PANTHEON = _load(Path(__file__).with_name("gods.toml"))


def get_god(key: str | None) -> God:
    return PANTHEON.get((key or "").strip().lower(), PANTHEON[DEFAULT_GOD])
