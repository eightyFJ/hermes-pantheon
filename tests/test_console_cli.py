import argparse
import threading

import pantheon.cli as cli
import pantheon.console as console
import pytest
from pantheon.gods import PANTHEON


class RecordingConsole:
    def __init__(self):
        self.titles, self.restored = [], 0
        self.changed = threading.Condition()

    def set(self, title):
        with self.changed:
            self.titles.append(title)
            self.changed.notify_all()

    def restore(self):
        self.restored += 1

    def wait_for(self, predicate, timeout=5):
        with self.changed:
            assert self.changed.wait_for(lambda: predicate(self.titles), timeout), self.titles


def test_animator_cycles_frames_and_restores():
    screen = RecordingConsole()
    animator = console.Animator(screen)
    animator.show(("🔨💥", "🔨✨"), 10, "Fix the build")
    screen.wait_for(lambda titles: {"🔨💥 Fix the build", "🔨✨ Fix the build"} <= set(titles))
    animator.show(("🔨❔",), 0, "Fix the build")
    screen.wait_for(lambda titles: titles[-1] == "🔨❔ Fix the build")
    animator.stop()
    assert screen.restored == 1


def test_animator_with_nothing_to_show_sets_no_title():
    screen = RecordingConsole()
    animator = console.Animator(screen)
    animator.stop()
    assert screen.titles == []
    assert screen.restored == 1


class FakeKernel32:
    def __init__(self, original="PowerShell"):
        self.original, self.titles = original, []

    def GetConsoleTitleW(self, buffer, size):
        buffer.value = self.original
        return len(self.original)

    def SetConsoleTitleW(self, title):
        self.titles.append(title)


def windows_console(monkeypatch, kernel32):
    import ctypes

    monkeypatch.setattr(console.os, "name", "nt")
    monkeypatch.setattr(ctypes, "windll", type("WinDLL", (), {"kernel32": kernel32})(), raising=False)
    return console.ConsoleTitle()


def test_console_title_on_windows_restores_the_original(monkeypatch):
    kernel32 = FakeKernel32()
    title = windows_console(monkeypatch, kernel32)
    title.set("🔨✨ Hermes")
    title.restore()
    assert kernel32.titles == ["🔨✨ Hermes", "PowerShell"]


def test_console_title_without_an_original_restores_hermes(monkeypatch):
    kernel32 = FakeKernel32(original="")
    title = windows_console(monkeypatch, kernel32)
    title.restore()
    assert kernel32.titles == ["Hermes"]


def test_console_title_without_a_windows_console_falls_back_to_the_tty(monkeypatch):
    import ctypes

    monkeypatch.setattr(console.os, "name", "nt")
    monkeypatch.delattr(ctypes, "windll", raising=False)
    written = []

    class Tty:
        def __enter__(self):
            return self

        def __exit__(self, *exc):
            return False

        def write(self, text):
            written.append(text)

    monkeypatch.setattr("builtins.open", lambda *a, **k: Tty())
    console.ConsoleTitle().set("x")
    assert written == ["\x1b]2;x\x07"]


def test_console_title_without_any_terminal_is_silent(monkeypatch):
    monkeypatch.setattr(console.os, "name", "posix")

    def no_tty(*args, **kwargs):
        raise OSError("no tty")

    monkeypatch.setattr("builtins.open", no_tty)
    title = console.ConsoleTitle()
    title.set("x")
    title.restore()


def test_list_gods_shows_every_god_and_frame():
    text = cli.list_gods()
    for god in PANTHEON.values():
        assert god.key in text
        assert god.epithet in text
    assert "working: 🔨💥 🔨✨ 🔨🔥" in text


class FakeAnimator:
    def __init__(self):
        self.shown, self.stopped = [], False

    def show(self, frames, interval_ms, label):
        self.shown.append((tuple(frames), interval_ms, label))

    def stop(self):
        self.stopped = True


def test_preview_plays_every_state_and_restores(capsys):
    animator = FakeAnimator()
    cli.preview([PANTHEON["hestia"]], 0, animator=animator, sleep=lambda s: None)
    assert [frames for frames, _, _ in animator.shown] == [("🔥✨", "🔥💫"), ("🔥❔",), ("🔥",)]
    assert animator.stopped
    out = capsys.readouterr().out
    assert "tending the flame…" in out
    assert out.rstrip().endswith("Title restored.")


def test_preview_stops_cleanly_on_ctrl_c():
    animator = FakeAnimator()

    def interrupt(seconds):
        raise KeyboardInterrupt

    cli.preview(list(PANTHEON.values()), 1, animator=animator, sleep=interrupt)
    assert len(animator.shown) == 1
    assert animator.stopped


def args(*argv):

    parser = argparse.ArgumentParser()
    cli.setup(parser)
    return parser.parse_args(list(argv))


def test_setup_parses_preview_options():
    parsed = args("preview", "kronos", "--seconds", "2")
    assert (parsed.pantheon_cmd, parsed.god, parsed.seconds) == ("preview", "kronos", 2.0)


def test_run_list(capsys):
    assert cli.run(args("list")) == 0
    assert "hephaestus" in capsys.readouterr().out


def test_run_with_no_subcommand_lists(capsys):
    assert cli.run(args()) == 0
    assert "Preview one in this tab" in capsys.readouterr().out


def test_run_preview_rejects_an_unknown_god(capsys):
    assert cli.run(args("preview", "thor")) == 2
    assert "No god named 'thor'" in capsys.readouterr().out


@pytest.mark.parametrize(
    ("argv", "expected"),
    [
        (("preview", "Pan", "--seconds", "0.1"), (["pan"], 1.0)),
        (("preview",), (list(PANTHEON), 4.0)),
    ],
)
def test_run_preview_picks_gods_and_clamps_seconds(monkeypatch, argv, expected):
    calls = []
    monkeypatch.setattr(cli, "preview", lambda gods, seconds: calls.append(([g.key for g in gods], seconds)))
    assert cli.run(args(*argv)) == 0
    assert calls == [expected]
