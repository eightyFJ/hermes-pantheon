# Pantheon

A Hermes Agent plugin that puts a small Greek god in your terminal tab, showing what Hermes is doing.

| State | Hephaestus (default) |
|---|---|
| Working | `🔨💥 Fix the build` → `🔨✨ …` → `🔨🔥 …` (hammer strikes, sparks fly) |
| Waiting on you (an approval, a question, a sudo prompt) | `🔨❔ Fix the build` |
| Idle, turn done | `🔨🔥 Fix the build` ↔ `🔨🪵 …` (the forge cools) |

The status bar says it too, in your skin's colours: `🔨✨ forging…`, `🔨❔ awaits your word`, `🔨🔥 forge cooling`.

Leave a long task running in another tab and you can see across the room whether it is still
working, finished, or stuck waiting for you.

## The pantheon

23 gods. `/summon <name>` picks one; `hermes pantheon list` shows them all.

| God | Working | Waiting | Idle |
|---|---|---|---|
| Hephaestus, smith of the gods | 🔨💥 🔨✨ 🔨🔥 | 🔨❔ | 🔨🔥 🔨🪵 |
| Hermes, messenger of the gods | 🪽📜 🪽💨 | 📜❔ | 🪽 |
| Athena, goddess of wisdom | 🦉💭 🦉✨ | 🦉❔ | 🦉 |
| Iris, bearer of the oath-water | 🏺💧 🏺💦 | 🏺❔ | 🏺 |
| Kronos, titan of time | ⏳ ⌛ | ⌛❔ | 🕰️ |
| Hestia, keeper of the hearth | 🔥✨ 🔥💫 | 🔥❔ | 🔥 |
| Hypnos, god of sleep | 🥱 😪 | 👁️ | 😴💤 |
| Pan, god of the wild | 🐐🎶 🐐🎵 | 🐐❔ | 🐐 |
| Zeus, king of the gods | ⚡🌩 🌩⚡ | ⚡❔ | ☁️ |
| Poseidon, lord of the sea | 🔱🌊 🌊🔱 | 🔱❔ | 🐚 |
| Apollo, god of music and light | 🪕🎵 🪕🎶 | 🪕❔ | 🌞 |
| Artemis, the huntress | 🏹🎯 🏹💨 | 🏹❔ | 🌙 |
| Ares, god of war | 🛡💥 🗡💥 | 🛡❔ | 🛡 |
| Aphrodite, goddess of love | 💘✨ 💘💫 | 💌❔ | 🐚 |
| Dionysus, god of wine | 🍇🍷 🍷🍇 | 🍷❔ | 🍷 |
| Demeter, goddess of the harvest | 🌱 🌿 🌾 | 🌾❔ | 🌾 |
| Hades, lord of the underworld | 💀🔥 💀💨 | 🐕❔ | 💀 |
| Persephone, queen of spring | 🌸🌱 🌱🌸 | 🌸❔ | 🍎 |
| Nike, goddess of victory | 🏃💨 🪽💨 | 🏅❔ | 🏆 |
| Selene, goddess of the moon | 🌒 🌓 🌔 🌕 | 🌕❔ | 🌙 |
| Eros, god of desire | 🏹💘 💘💫 | 💘❔ | 💤 |
| Prometheus, the fire-bringer | 🔥🏃 🏃🔥 | 🔥❔ | 🪨 |
| Atlas, who holds up the sky | 🌍💦 🌏💦 | 🌍❔ | 🌍 |

The tab shows the session's title after the god: Hermes's automatic title, or your own from `/title`.

## Requirements

- Hermes Agent 0.23.3 or later.
- The animated tab and status bar need a Hermes chat that renders plugin terminal events
  (`plugin.<id>.terminal`). That support is proposed upstream; see [Status](#status). Without
  it, `hermes pantheon preview` still shows every god in your tab, and the plugin does nothing
  else.
- Tested on Windows 11 in Windows Terminal. Any terminal that honours title escape sequences
  should work.

## Install

```
hermes plugins install https://github.com/eightyFJ/hermes-pantheon
hermes plugins enable pantheon
```

Enabling reloads plugins in a running gateway, so no restart is needed.

## Commands

| Where | Command | What it does |
|---|---|---|
| In a chat | `/summon` | Lists the gods and marks the current one |
| In a chat | `/summon <god>` | Switches this chat to that god and makes it your default |
| Terminal | `hermes pantheon list` | Prints every god's frames |
| Terminal | `hermes pantheon preview [god] [--seconds N]` | Animates the gods in this tab's title, then restores it |

## Settings

Under `plugins.entries.pantheon.settings` in `config.yaml`:

| Key | Default | Meaning |
|---|---|---|
| `god` | `hephaestus` | Default god until `/summon` picks one |
| `naming_tool` | `false` | Give the model a `set_tab_title` tool. Off by default: Hermes already titles sessions, and on local models every extra tool costs prompt space. |

## How it works

Hermes runs the agent in its shared gateway, not in your terminal, so a plugin cannot set your
tab's title itself. Pantheon is the gateway half:

1. Hooks follow each session's state: `pre_llm_call` (working), `on_human_input_request` and
   `on_human_input_resolved` (waiting on you), `on_session_end` (idle, including interrupted turns),
   and `on_session_finalize` (the session closed).
2. On every change, and only then, it sends one `plugin.pantheon.terminal` event to the
   session's viewers. The event carries the god's frames and timing, the session title, a short
   status and a tone (`strong`, `warn` or `dim`). When the session closes it sends `{"clear": true}`.
3. The chat animates the frames in the tab title, shows the status in the status bar with the
   skin's `status-bar-<tone>` style, and puts your own title back when you leave.

## Disclosures

- **Data it reads.** The hooks receive every turn of every session, including the user's message.
  Pantheon keeps none of it, only each session's state and title in memory. It reads the
  session's title from Hermes's session store at the start and end of a turn.
- **Data it stores.** The god you last summoned, in the plugin's own state file in the Hermes
  data folder.
- **What it sends.** Session events to that session's viewers on this machine. It skips
  messaging platforms (Telegram, Discord, Slack and others), which have no terminal tab.
- **Optional tool.** `set_tab_title` stays hidden from the model unless you set `naming_tool: true`.
- No network calls, no telemetry, no self-update, no dependencies outside Hermes.

## Status

- The plugin works today with `hermes pantheon preview`.
- Rendering in the chat needs a Hermes change, which is being proposed to
  [NousResearch/hermes-agent](https://github.com/NousResearch/hermes-agent). The change adds
  `plugin.<id>.terminal` support to the classic CLI: a tab title, a `plugins` status-bar field
  and a restore on exit.
- The TUI and the Desktop app don't render it yet.

## Development

```
python -m pip install pytest pytest-cov ruff
python -m pytest tests --cov --cov-config=pyproject.toml
ruff check . && ruff format --check .
hermes plugins validate .
```

The gods live in `gods.toml`; add one there and it appears everywhere. The repository root is the plugin package; `tests/conftest.py` loads it as `pantheon`.

## License

[MIT](LICENSE)
