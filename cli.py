"""``hermes pantheon list`` and ``hermes pantheon preview``."""

from __future__ import annotations

import time

from .console import Animator
from .gods import PANTHEON, STATES, God

PREVIEW_LABEL = "pantheon preview"


def list_gods() -> str:
    lines = []
    for god in PANTHEON.values():
        acts = "  ".join(f"{state}: {' '.join(god.act(state).frames)}" for state in STATES)
        lines.append(f"{god.key:<11} {god.name}, {god.epithet}\n            {acts}")
    lines.append("\nPreview one in this tab: hermes pantheon preview <name>")
    return "\n".join(lines)


def preview(gods: list[God], seconds: float, animator: Animator | None = None, sleep=time.sleep) -> None:
    animator = animator or Animator()
    try:
        for god in gods:
            for state in STATES:
                act = god.act(state)
                print(f"{god.name:<11} {state:<8} {act.phrase}", flush=True)
                animator.show(act.frames, act.interval_ms, PREVIEW_LABEL)
                sleep(seconds)
    except KeyboardInterrupt:
        pass
    finally:
        animator.stop()
    print("Title restored.")


def setup(parser) -> None:
    sub = parser.add_subparsers(dest="pantheon_cmd")
    preview_parser = sub.add_parser("preview", help="Animate the gods in this terminal's tab title")
    preview_parser.add_argument("god", nargs="?", default="", help="God to preview (default: all, in turn)")
    preview_parser.add_argument("--seconds", type=float, default=4.0, help="Seconds per state (minimum 1)")
    sub.add_parser("list", help="List the gods and their frames")


def run(args) -> int:
    if getattr(args, "pantheon_cmd", None) != "preview":
        print(list_gods())
        return 0
    wanted = (args.god or "").strip().lower()
    if wanted and wanted not in PANTHEON:
        print(f"No god named {wanted!r}. Try: {', '.join(PANTHEON)}")
        return 2
    preview([PANTHEON[wanted]] if wanted else list(PANTHEON.values()), max(1.0, float(args.seconds)))
    return 0
