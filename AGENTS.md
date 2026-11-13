# AGENTS.md

Guidance for AI coding agents and contributors. `CLAUDE.md` imports this file, and `.github/copilot-instructions.md` adds the review checklist.

## Language

- All deliverables are written in **English**: commit messages, PR/Issue titles and bodies, review comments, code comments and docstrings, and documentation (`README.md`, `AGENTS.md`, etc.).
- Exceptions (keep as is): quotations, technical identifiers, generated files, and external source text.
- Runtime messages (logs, errors) are English.
- Do not rewrite Git history to change the language of past commits.

## Overview

`youtube-playlist-video-checker` polls a list of YouTube playlists via the YouTube Data API v3 and posts a Discord embed for each newly added video. It is a small Python CLI intended to run periodically (for example from cron). State is kept in a local JSON file so each video is announced only once.

## Commands

There is no build step.

```bash
pip3 install -U -r requirements.txt   # install dependencies (requirements.txt is UTF-16; pip reads it)
python3 -m src                        # run (src/__main__.py:main)
ruff check && ruff format --check     # lint / format check (config in ruff.toml)
pytest                                # tests
```

CI (`.github/workflows/python-ci.yml`, reusable workflow from `book000/templates`) runs `python -m compileall`, `ruff check`, `ruff format --check`, and `pytest`.

Run from the repository root: `playlists.json`, `already.json` and `logs/` are resolved against the current working directory. `.env` is located by `python-dotenv` searching upward from `src/`.

## Runtime configuration (git-ignored)

- `.env` (loaded in `src/config.py`). Each key is required; a missing one logs `critical` and calls `sys.exit(1)`: `GOOGLE_TOKEN` (YouTube Data API v3 key), `DISCORD_TOKEN` (bot token), `DISCORD_CHANNEL_ID` (target channel).
- `playlists.json`: JSON array of playlist IDs (see `playlists.sample.json`).
- `already.json`: state written by the app, mapping each playlist ID to the video IDs already announced. Do not hand-edit while running.
- `.env`, `playlists.json`, `already.json` and `logs/` are git-ignored. Never commit real tokens or state.

## Structure

- `src/__main__.py`: entry point. For each playlist it lists items (`get_playlist_items`), diffs against `already.json`, fetches video details (`get_videos_details`), and sends a Discord embed per new video.
  A failed send is logged and skipped without recording the video ID, so it is retried on the next run.
- `src/config.py`: loads `.env` and exposes `GOOGLE_TOKEN`, `DISCORD_TOKEN`, `DISCORD_CHANNEL_ID` via `getKey`.
- `src/__init__.py`: `init_logger` (stream handler plus daily-rotating file handler under `logs/`, 30 backups) and `send_discord_message` (raw `requests` POST to the Discord REST API with a `Bot` token, not a Discord library).
  `send_discord_message` sends the embed in the `embeds` array, retries HTTP 429 (up to 3 times, waiting the delay Discord requests, at most 60 seconds), and raises `requests.HTTPError` for responses with status 400 or above.
- `tests/test_get_videos_details.py`: unit tests for `get_videos_details` with a mocked YouTube client.
- `tests/test_send_discord_message.py`: unit tests for `send_discord_message` with mocked `requests.post` and `time.sleep` (payload shape, 429 retry and wait cap, HTTP error raising, token not logged).
- `tests/test_main_send_failure.py`: tests that `main` does not record a video whose send failed in `already.json`, and that the first run records IDs without sending.

## Behavior to preserve

- Silent first run: when a playlist is not yet in `already.json` (`init = True`), its existing videos are recorded but NOT sent to Discord. This prevents announcing the whole backlog.
- Live and upcoming entries are excluded: `get_videos_details` keeps only items whose `liveBroadcastContent == "none"`, so premieres and live streams are not announced until they become regular videos.
- Announce exactly once: idempotency comes solely from `already.json`. Any change to when IDs are appended must keep this intact.
- Keep the `list_next` pagination loops in the YouTube fetch code, and send Discord messages through `send_discord_message`.

## Conventions

- Match the existing style: `snake_case` functions, standard library first, `str.format()` / `%` formatting. Do not convert to f-strings (`ruff.toml` ignores UP031/UP032 for this reason).
- The code uses builtin generics (`list[str]`) and `str | None` with `from __future__ import annotations`, so Python 3.9+ is required (`ruff.toml` sets `target-version = "py39"`).
- `requirements.txt` pins `setuptools<81` because `googleapiclient` imports `pkg_resources`, which newer setuptools removed.
- If you change dependencies, runtime files or the run command, update `README.md` and this file.
- Commits follow [Conventional Commits](https://www.conventionalcommits.org/); branches follow [Conventional Branch](https://conventional-branch.github.io) short form (`feat/...`, `fix/...`).
- Do not commit to Renovate PRs. Never commit secrets.
