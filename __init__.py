"""Pantheon: a small Greek god in your terminal tab that shows what Hermes is doing."""

from __future__ import annotations

import json
import logging
from typing import Any

from . import cli
from .gods import DEFAULT_GOD, PANTHEON, get_god
from .tracker import Tracker

logger = logging.getLogger(__name__)

HOOKS = (
    "pre_llm_call",
    "on_session_end",
    "on_human_input_request",
    "on_human_input_resolved",
    "on_session_finalize",
)

# fmt: off
NO_TAB_PLATFORMS = frozenset({
    "telegram", "discord", "slack", "whatsapp", "signal", "email", "sms",
    "matrix", "mattermost", "teams", "webhook", "api_server", "yuanbao", "cron",
})
# fmt: on

TITLE_TOOL_SCHEMA = {
    "name": "set_tab_title",
    "description": "Name this chat's terminal tab (2-5 words).",
    "parameters": {"type": "object", "properties": {"title": {"type": "string"}}, "required": ["title"]},
}


def stored_title(session_id: str) -> str:
    try:
        from persistence_assembly import open_persistence_reader, profile_scope

        with open_persistence_reader(profile_scope().profile_dir) as reader:
            record = reader.sessions.get(session_id)
        return str(getattr(record, "title", "") or "")
    except Exception:
        logger.debug("pantheon: title lookup failed", exc_info=True)
        return ""


class Pantheon:
    def __init__(self, ctx: Any) -> None:
        self.ctx = ctx
        self._seen_titles: dict[str, str] = {}
        self.tracker = Tracker(self._emit, default_god=self.default_god)

    def default_god(self) -> str:
        try:
            return self.ctx.state.get("default_god", default="") or self.ctx.get_config("god", default=DEFAULT_GOD)
        except Exception:
            logger.debug("pantheon: could not read the default god", exc_info=True)
            return DEFAULT_GOD

    def _emit(self, session_id: str, payload: dict) -> None:
        if payload.get("clear"):
            self._seen_titles.pop(session_id, None)
        try:
            self.ctx.emit_to_session(session_id, "terminal", payload)
        except Exception:
            logger.debug("pantheon: emit failed", exc_info=True)

    def _new_title(self, session_id: str) -> str:
        title = stored_title(session_id)
        if title and title != self._seen_titles.get(session_id):
            self._seen_titles[session_id] = title
            return title
        return ""

    def _wait_target(self, session_id: str) -> str:
        # A wait for a session with no tab (a Telegram approval, say) must not move another tab.
        if session_id:
            return session_id if self.tracker.has(session_id) else ""
        return self.tracker.only_active() or ""

    def pre_llm_call(self, session_id: str = "", platform: str = "", **_: Any) -> None:
        if session_id and str(platform).lower() not in NO_TAB_PLATFORMS:
            self.tracker.working(session_id, label=self._new_title(session_id))

    def on_session_end(self, session_id: str = "", **_: Any) -> None:
        if self.tracker.has(session_id):
            self.tracker.done(session_id, label=self._new_title(session_id))

    def on_human_input_request(self, session_id: str = "", request_id: str = "", **_: Any) -> None:
        if sid := self._wait_target(session_id):
            self.tracker.wait_start(sid, request_id)

    def on_human_input_resolved(self, session_id: str = "", request_id: str = "", **_: Any) -> None:
        if sid := self._wait_target(session_id):
            self.tracker.wait_end(sid, request_id)

    def on_session_finalize(self, session_id: str = "", **_: Any) -> None:
        if session_id:
            self.tracker.forget(session_id)

    def summon(self, raw_args: str = "", *, session_id: str = "", **_: Any) -> str:
        wanted = (raw_args or "").strip().lower()
        if not wanted:
            current = get_god(self.default_god()).key
            rows = [
                f"{'▸' if god.key == current else ' '} {god.act('working').frames[0]}  {god.key:<11} "
                f"{god.name}, {god.epithet}"
                for god in PANTHEON.values()
            ]
            return "The pantheon (/summon <name>):\n" + "\n".join(rows)
        if wanted not in PANTHEON:
            return f"No god named {wanted!r}. Try: {', '.join(PANTHEON)}"
        god = PANTHEON[wanted]
        try:
            self.ctx.state.set("default_god", god.key)
        except Exception:
            logger.debug("pantheon: could not save the default god", exc_info=True)
        if session_id:
            self.tracker.set_god(session_id, god.key)
        return f"{god.act('idle').frames[0]}  {god.name}, {god.epithet}, is summoned."

    def set_tab_title(self, args: dict, session_id: str = "", **_: Any) -> str:
        if not session_id:
            return json.dumps({"ok": False, "error": "no session"})
        if not self.tracker.set_label(session_id, str((args or {}).get("title", ""))):
            return json.dumps({"ok": False, "error": "empty title"})
        return json.dumps({"ok": True})


def register(ctx: Any) -> None:
    pantheon = Pantheon(ctx)
    for hook in HOOKS:
        ctx.register_hook(hook, getattr(pantheon, hook))
    ctx.register_command("summon", handler=pantheon.summon, description="Choose the god in your tab", args_hint="[god]")
    ctx.register_tool(
        name="set_tab_title",
        toolset="pantheon",
        schema=TITLE_TOOL_SCHEMA,
        handler=pantheon.set_tab_title,
        description=TITLE_TOOL_SCHEMA["description"],
        emoji="🔨",
        check_fn=lambda: ctx.get_config("naming_tool", default=False) is True,
    )
    ctx.register_cli_command("pantheon", help="List and preview the gods", setup_fn=cli.setup, handler_fn=cli.run)
