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
pip3 install -U -r requirements.txt   # install dependencies
python3 -m src                        # run (src/__main__.py:main)
ruff check && ruff format --check     # lint / format check (config in ruff.toml)
pytest                                # tests
```

CI (`.github/workflows/python-ci.yml`, reusable workflow from `book000/templates`) runs `python -m compileall`, `ruff check`, `ruff format --check`, and `pytest`.
CI tests Python 3.9 and 3.15. Keep the minimum in the CI matrix in step with the declared minimum (`README.md`, `ruff.toml` and this file). `.python-version` selects the default Python version for local tools.

Run from the repository root: `playlists.json`, `already.json` and `logs/` are resolved against the current working directory. `.env` is located by `python-dotenv` searching upward from `src/`.

## Runtime configuration (git-ignored)

- `.env` (loaded in `src/config.py`). Each key is required; a missing one logs `critical` and calls `sys.exit(1)`: `GOOGLE_TOKEN` (YouTube Data API v3 key), `DISCORD_TOKEN` (bot token), `DISCORD_CHANNEL_ID` (target channel).
- `playlists.json`: JSON array of playlist IDs (see `playlists.sample.json`).
- `already.json`: state written by the app, mapping each playlist ID to the video IDs already announced. Do not hand-edit while running.
- `already.json.lock`: lock file created by the app next to `already.json` (see `single_instance_lock`). Never delete it while a run is in progress.
- `.env`, `playlists.json`, `already.json`, `already.json.lock` and `logs/` are git-ignored. Never commit real tokens or state.

## Structure

- `src/__main__.py`: entry point. For each playlist it lists items (`get_playlist_items`), diffs against `already.json`, fetches video details (`get_videos_details`), and sends a Discord embed per new video.
  `single_instance_lock()` takes `fcntl.flock` (`LOCK_EX | LOCK_NB`) on `already.json.lock` in the working directory and is held for the whole run (read state, YouTube, Discord, persist). If another process holds it, `main` logs `Another instance is already running; exiting` and exits 1; if the lock file cannot be opened or locked it logs `Cannot acquire the instance lock: <error>` and exits 1. The kernel releases the lock on process exit, so a crash leaves no stale lock. POSIX only.
  YouTube `HttpError` responses and empty playlist lookups are logged per playlist; processing continues and the command exits 1 if any playlist failed. Successful notifications are checkpointed immediately in `already.json`.
  The exception text embeds the request URI, which contains the Google API key (`describe_http_error` keeps only the status and `[A-Za-z_]+` reason codes), so it must never be logged or left to a traceback.
  A failed send is logged and skipped without recording the video ID, so it is retried on the next run.
- `src/config.py`: loads `.env` and exposes `GOOGLE_TOKEN`, `DISCORD_TOKEN`, `DISCORD_CHANNEL_ID` via `getKey`.
- `src/__init__.py`: `init_logger` (stream handler plus daily-rotating file handler under `logs/`, 30 backups) and `send_discord_message` (raw `requests` POST to the Discord REST API with a `Bot` token, not a Discord library).
  `send_discord_message` sends the embed in the `embeds` array, retries HTTP 429 (up to 3 times, waiting the delay Discord requests, at most 60 seconds), and raises `requests.HTTPError` for responses with status 400 or above.
- `tests/test_get_videos_details.py`: unit tests for `get_videos_details` with a mocked YouTube client.
- `tests/test_send_discord_message.py`: unit tests for `send_discord_message` with mocked `requests.post` and `time.sleep` (payload shape, 429 retry and wait cap, HTTP error raising, token not logged).
- `tests/test_main_send_failure.py`: tests that `main` does not record a video whose send failed in `already.json`, and that the first run records IDs without sending.
- `tests/test_main_youtube_error.py`: tests that an `HttpError` from each YouTube call site yields exit code 1, a status/reason-only log message with no API key (synthetic key), no exception chaining, and unchanged prior state when the request fails.
- `tests/test_save_already.py`: tests that `save_already` writes atomically: success leaves only `already.json`, and `json.dump`/`fsync`/`os.replace` failures keep the prior state and leave no temp file.
- `tests/test_single_instance_lock.py`: tests that a lock held by another fd or a competing subprocess makes `main` exit 1 without reading state or calling YouTube/Discord, that the lock is released after the body or exit, that open/lock errors are reported, and that a body `OSError` is not reported as a lock error.
- `tests/test_playlist_failure_isolation.py`: tests that playlist failures do not stop later playlists or discard successful notifications, and that a failed first run remains uninitialized.

## Behavior to preserve

- Silent first run: when a playlist is not yet in `already.json` (`init = True`), its existing videos are recorded but NOT sent to Discord. This prevents announcing the whole backlog.
- Live and upcoming entries are excluded: `get_videos_details` keeps only items whose `liveBroadcastContent == "none"`, so premieres and live streams are not announced until they become regular videos.
- Announce exactly once in normal operation: a video is not announced twice while runs complete and persist their state, and that idempotency comes solely from `already.json`. Any change to when IDs are appended must keep this intact. The crash window between Discord accepting a message and `already.json` being updated is the at-least-once limitation described below.
- Keep the whole run inside `single_instance_lock()` so overlapping runs cannot race on `already.json`.
- Delivery is at-least-once, not exactly-once, across a crash between Discord accepting a message and `already.json` being updated: the video is announced again on the next run. This is a documented limitation.
- Keep the `list_next` pagination loops in the YouTube fetch code, and send Discord messages through `send_discord_message`.

## Conventions

- Match the existing style: `snake_case` functions, standard library first, `str.format()` / `%` formatting. Do not convert to f-strings (`ruff.toml` ignores UP031/UP032 for this reason).
- Python 3.9+ is required: `ruff.toml` sets `target-version = "py39"`, and `requirements.txt` selects compatible dependency versions for Python 3.9. Union annotations (`str | None`) use `from __future__ import annotations`.
- If you change dependencies, runtime files or the run command, update `README.md` and this file.
- Commits follow [Conventional Commits](https://www.conventionalcommits.org/); branches follow [Conventional Branch](https://conventional-branch.github.io) short form (`feat/...`, `fix/...`).
- Do not commit to Renovate PRs. Never commit secrets.
