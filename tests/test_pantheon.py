import pytest
from pantheon.gods import DEFAULT_GOD, PANTHEON, STATES, get_god
from pantheon.title import clean_label, compose
from pantheon.tracker import CLEAR, Tracker


def test_clean_label_removes_escapes_and_invisible_characters():
    assert clean_label("evil\x1b]0;pwned\x07title") == "evil ]0;pwned title"
    assert clean_label("a‮b​c") == "abc"
    assert clean_label("  many \n\t spaces  ") == "many spaces"
    assert clean_label(None) == ""


def test_clean_label_truncates_with_an_ellipsis():
    assert clean_label("x" * 40, 10) == "x" * 9 + "…"
    assert clean_label("x" * 40, 0) == "x" * 40


def test_compose_joins_frame_and_label():
    assert compose("🔨✨", "Fix the build") == "🔨✨ Fix the build"
    assert compose("🔨✨", "") == "🔨✨ Hermes"
    assert compose("", "x") == "x"
    assert "\x1b" not in compose("\x1b]0;", "t")


@pytest.mark.parametrize("god", PANTHEON.values(), ids=PANTHEON.keys())
def test_every_god_has_every_state(god):
    for state in STATES:
        act = god.act(state)
        assert act.phrase
        assert all(frame.strip() and len(frame) <= 8 for frame in act.frames)
        assert len(act.frames) == 1 or act.interval_ms > 0


def test_get_god_is_case_insensitive_with_a_default():
    assert get_god(" ATHENA ").key == "athena"
    assert get_god("thor").key == DEFAULT_GOD
    assert get_god(None).key == DEFAULT_GOD


@pytest.fixture
def tracked():
    events = []
    return Tracker(lambda sid, payload: events.append((sid, payload))), events


def states(events):
    return [payload.get("state", "clear") for _, payload in events]


def test_a_turn_with_overlapping_waits(tracked):
    tracker, events = tracked
    tracker.working("s1")
    tracker.working("s1")
    tracker.wait_start("s1", "r1")
    tracker.wait_start("s1", "r2")
    tracker.wait_end("s1", "r1")
    tracker.wait_end("s1", "r2")
    tracker.done("s1")
    assert states(events) == ["working", "waiting", "working", "idle"]


def test_payload_shape(tracked):
    tracker, events = tracked
    tracker.working("s1", label="Fix the build")
    assert events[-1][1] == {
        "frames": ["🔨💥", "🔨✨", "🔨🔥"],
        "interval_ms": 260,
        "label": "Fix the build",
        "status": "forging…",
        "tone": "strong",
        "state": "working",
        "god": "hephaestus",
    }


def test_unlabelled_sessions_show_hermes(tracked):
    tracker, events = tracked
    tracker.working("s1")
    assert events[-1][1]["label"] == "Hermes"


def test_wait_end_for_an_unknown_session_is_ignored(tracked):
    tracker, events = tracked
    tracker.wait_end("ghost", "r1")
    assert events == []


def test_sessions_are_independent_and_forget_clears(tracked):
    tracker, events = tracked
    tracker.working("a")
    tracker.working("b")
    assert tracker.only_active() is None
    tracker.done("a")
    assert tracker.only_active() == "b"
    tracker.forget("b")
    assert events[-1] == ("b", CLEAR)
    tracker.forget("b")
    assert len(events) == 4


def test_label_and_god(tracked):
    tracker, events = tracked
    tracker.working("s")
    assert tracker.set_label("s", "Inkling\x07 quant check") == "Inkling quant check"
    tracker.set_god("s", "kronos")
    assert events[-1][1]["god"] == "kronos"
    assert events[-1][1]["label"] == "Inkling quant check"
    tracker.wait_start("s", "r")
    tracker.done("s")
    assert events[-1][1]["state"] == "idle"


def test_updates_without_a_session_id_are_ignored(tracked):
    tracker, events = tracked
    tracker.working("")
    assert events == []


def test_default_god_comes_from_the_callback():
    events = []
    Tracker(lambda sid, p: events.append(p), default_god=lambda: "pan").working("s")
    assert events[-1]["god"] == "pan"
