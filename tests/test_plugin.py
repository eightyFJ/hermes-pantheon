import json
import sys
import types

import pantheon
import pytest


class FakeState:
    def __init__(self, broken=False):
        self.data, self.broken = {}, broken

    def get(self, key, default=None):
        if self.broken:
            raise OSError("state file unreadable")
        return self.data.get(key, default)

    def set(self, key, value):
        if self.broken:
            raise OSError("state file unwritable")
        self.data[key] = value


class FakeCtx:
    def __init__(self, settings=None, broken_state=False, broken_emit=False):
        self.settings = settings or {}
        self.state = FakeState(broken_state)
        self.broken_emit = broken_emit
        self.hooks, self.commands, self.tools, self.cli, self.emitted = {}, {}, {}, {}, []

    def get_config(self, key, default=None):
        return self.settings.get(key, default)

    def register_hook(self, name, fn):
        self.hooks[name] = fn

    def register_command(self, name, handler, **_):
        self.commands[name] = handler

    def register_tool(self, name, handler, check_fn=None, **_):
        self.tools[name] = (handler, check_fn)

    def register_cli_command(self, name, setup_fn, handler_fn, **_):
        self.cli[name] = (setup_fn, handler_fn)

    def emit_to_session(self, session_id, event, payload):
        if self.broken_emit:
            raise RuntimeError("no session authority")
        self.emitted.append((session_id, event, payload))
        return True


@pytest.fixture(autouse=True)
def titles(monkeypatch):
    stored = {"s1": "Inkling quant check"}
    monkeypatch.setattr(pantheon, "stored_title", lambda sid: stored.get(sid, ""))
    return stored


def plugin(**kwargs):
    ctx = FakeCtx(**kwargs)
    pantheon.register(ctx)
    return ctx


def states(ctx):
    return [(sid, payload.get("state", "clear")) for sid, _, payload in ctx.emitted]


def test_register_wires_hooks_command_tool_and_cli():
    ctx = plugin()
    assert set(ctx.hooks) == set(pantheon.HOOKS)
    assert set(ctx.commands) == {"summon"}
    assert set(ctx.tools) == {"set_tab_title"}
    assert set(ctx.cli) == {"pantheon"}


def test_a_full_turn_with_an_approval():
    ctx = plugin()
    hooks = ctx.hooks
    hooks["pre_llm_call"](session_id="s1", model="inkling-2-mini", platform="local")
    hooks["on_human_input_request"](session_id="s1", request_id="r1", kind="approval")
    hooks["on_human_input_resolved"](session_id="s1", request_id="r1", outcome="approved")
    hooks["on_session_end"](session_id="s1", completed=True)
    hooks["on_session_finalize"](session_id="s1")
    assert [state for _, state in states(ctx)] == ["working", "waiting", "working", "idle", "clear"]
    assert {event for _, event, _ in ctx.emitted} == {"terminal"}
    assert ctx.emitted[0][2]["label"] == "Inkling quant check"


def test_title_set_after_the_first_reply_is_picked_up_at_turn_end(titles):
    ctx = plugin()
    ctx.hooks["pre_llm_call"](session_id="s2", platform="cli")
    titles["s2"] = "Refactor auth"
    ctx.hooks["on_session_end"](session_id="s2")
    assert ctx.emitted[-1][2]["label"] == "Refactor auth"


def test_a_new_session_after_finalize_reads_the_title_again():
    ctx = plugin()
    ctx.hooks["pre_llm_call"](session_id="s1", platform="cli")
    ctx.hooks["on_session_finalize"](session_id="s1")
    ctx.hooks["pre_llm_call"](session_id="s1", platform="cli")
    assert ctx.emitted[-1][2]["label"] == "Inkling quant check"


def test_messaging_platforms_and_unknown_sessions_move_no_tab():
    ctx = plugin()
    ctx.hooks["pre_llm_call"](session_id="tg", platform="Telegram")
    ctx.hooks["pre_llm_call"](session_id="", platform="cli")
    ctx.hooks["on_session_end"](session_id="never-started")
    ctx.hooks["on_session_finalize"](session_id="")
    ctx.hooks["pre_llm_call"](session_id="cli", platform="cli")
    ctx.hooks["on_human_input_request"](session_id="telegram-1", request_id="r")
    assert states(ctx) == [("cli", "working")]


def test_waits_without_a_session_id_go_to_the_one_active_session():
    ctx = plugin()
    ctx.hooks["pre_llm_call"](session_id="cli", platform="cli")
    ctx.hooks["on_human_input_request"](request_id="r2")
    ctx.hooks["on_human_input_resolved"](request_id="r2")
    assert states(ctx)[-2:] == [("cli", "waiting"), ("cli", "working")]


def test_an_interrupted_turn_goes_idle():
    ctx = plugin()
    ctx.hooks["pre_llm_call"](session_id="cli", platform="cli")
    ctx.hooks["on_human_input_request"](session_id="cli", request_id="r")
    ctx.hooks["on_session_end"](session_id="cli", interrupted=True)
    assert states(ctx)[-1] == ("cli", "idle")


def test_summon_lists_switches_and_persists():
    ctx = plugin()
    summon = ctx.commands["summon"]
    ctx.hooks["pre_llm_call"](session_id="s1", platform="cli")
    listing = summon("")
    assert "▸ 🔨💥  hephaestus" in listing
    assert "pan" in listing
    assert "No god named 'thor'" in summon("thor")
    assert summon(" Hypnos ", session_id="s1") == "😴💤  Hypnos, god of sleep, is summoned."
    assert ctx.state.get("default_god") == "hypnos"
    assert ctx.emitted[-1][2]["god"] == "hypnos"
    assert "▸ 🥱  hypnos" in summon("")


def test_summon_without_a_session_only_sets_the_default():
    ctx = plugin()
    summon = ctx.commands["summon"]
    assert "Pan" in summon("pan")
    assert ctx.emitted == []
    ctx.hooks["pre_llm_call"](session_id="s1", platform="cli")
    assert ctx.emitted[-1][2]["god"] == "pan"


def test_the_god_setting_is_the_default_until_a_summon():
    ctx = plugin(settings={"god": "athena"})
    ctx.hooks["pre_llm_call"](session_id="s1", platform="cli")
    assert ctx.emitted[-1][2]["god"] == "athena"


def test_a_broken_state_file_falls_back_and_still_switches():
    ctx = plugin(broken_state=True)
    ctx.hooks["pre_llm_call"](session_id="s1", platform="cli")
    assert ctx.emitted[-1][2]["god"] == "hephaestus"
    assert "Kronos" in ctx.commands["summon"]("kronos", session_id="s1")
    assert ctx.emitted[-1][2]["god"] == "kronos"


def test_a_failing_emit_never_raises_into_hermes():
    ctx = plugin(broken_emit=True)
    ctx.hooks["pre_llm_call"](session_id="s1", platform="cli")


def test_long_titles_are_cut_to_fit_the_tab(titles):
    titles["s1"] = "A very long session title that will not fit"
    ctx = plugin()
    ctx.hooks["pre_llm_call"](session_id="s1", platform="cli")
    assert ctx.emitted[-1][2]["label"] == "A very long session title t…"


def test_naming_tool_is_hidden_unless_enabled():
    _, check = plugin().tools["set_tab_title"]
    assert check() is False
    ctx = plugin(settings={"naming_tool": True})
    handler, check = ctx.tools["set_tab_title"]
    assert check() is True
    assert json.loads(handler({"title": "x"})) == {"ok": False, "error": "no session"}
    assert json.loads(handler({"title": " \x07 "}, session_id="s1")) == {"ok": False, "error": "empty title"}
    assert json.loads(handler({"title": "Fix\x1b the build"}, session_id="s1")) == {"ok": True}
    assert ctx.emitted[-1][2]["label"] == "Fix the build"


def test_cli_command_is_the_cli_module():
    from pantheon import cli

    assert plugin().cli["pantheon"] == (cli.setup, cli.run)


def test_stored_title_reads_the_session_store(monkeypatch):
    monkeypatch.undo()
    record = types.SimpleNamespace(title="From the store")

    class Reader:
        sessions = types.SimpleNamespace(get=lambda sid: record if sid == "s1" else None)

        def __enter__(self):
            return self

        def __exit__(self, *exc):
            return False

    fake = types.ModuleType("persistence_assembly")
    fake.profile_scope = lambda: types.SimpleNamespace(profile_dir="home")
    fake.open_persistence_reader = lambda home: Reader()
    monkeypatch.setitem(sys.modules, "persistence_assembly", fake)
    assert pantheon.stored_title("s1") == "From the store"
    assert pantheon.stored_title("missing") == ""


def test_stored_title_is_empty_when_the_store_is_unavailable(monkeypatch):
    monkeypatch.undo()
    monkeypatch.setitem(sys.modules, "persistence_assembly", None)
    assert pantheon.stored_title("s1") == ""
