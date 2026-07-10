# CLAUDE.md

## Overview

`youtube-playlist-video-checker` polls a list of YouTube playlists via the
YouTube Data API v3 and posts a Discord embed for each newly added video.
It is a small Python CLI intended to run periodically (e.g. via cron). State
is kept in a local JSON file so each video is announced only once.

## Development commands

There is no build step, test suite, linter, or CI configured in this repo.

- Install dependencies: `pip3 install -U -r requirements.txt`
- Run: `python3 -m src` (executes `src/__main__.py:main`)

Run from the repository root: at runtime the process reads `.env`,
`playlists.json`, and `already.json` from the current working directory and
writes logs under `logs/`.

## Configuration (runtime, git-ignored)

- `.env` (loaded by `python-dotenv` in `src/config.py`). Required keys, each
  fatal if missing (`logger.critical` + `exit(1)`):
  - `GOOGLE_TOKEN`: YouTube Data API v3 key.
  - `DISCORD_TOKEN`: Discord bot token.
  - `DISCORD_CHANNEL_ID`: target Discord channel ID.
- `playlists.json`: JSON array of playlist IDs to check. See
  `playlists.sample.json` for the shape.
- `already.json`: state file written by the app, mapping each playlist ID to
  the list of video IDs already announced. Do not hand-edit while running.

`.env`, `playlists.json`, `already.json`, and `logs/` are all git-ignored;
never commit real tokens or state.

## Architecture

- `src/__main__.py`: entry point. For each playlist it lists items
  (`get_playlist_items`), diffs against `already.json`, fetches video details
  (`get_videos_details`), and sends a Discord embed per new video.
- `src/config.py`: loads `.env` and exposes `GOOGLE_TOKEN`, `DISCORD_TOKEN`,
  `DISCORD_CHANNEL_ID` via `getKey`.
- `src/__init__.py`: `init_logger` (stream + daily-rotating file handler under
  `logs/`, 30 backups) and `send_discord_message` (raw POST to the Discord REST
  API with a `Bot` token, not a library).

## Behavioral rules to preserve

- First run of a playlist is a silent baseline: when a playlist is not yet in
  `already.json` (`init = True`), its existing videos are recorded but NOT sent
  to Discord. This prevents announcing the entire backlog. Keep this guard.
- Live/upcoming entries are intentionally excluded: `get_videos_details` only
  keeps items whose `liveBroadcastContent == "none"`, so premieres and live
  streams are not announced until they become regular videos.
- Idempotency comes solely from `already.json`. Any change to when IDs are
  appended must keep "announce exactly once" intact.

## Coding conventions

- Match the existing style: `snake_case` functions, standard-library-first,
  `str.format()` / `%` formatting (do not churn these into f-strings).
- YouTube API calls use `googleapiclient` with `list_next` pagination; preserve
  the pagination loops when editing fetch logic.
- Discord messages are sent by direct `requests` calls in `send_discord_message`
  rather than a Discord library; keep new Discord logic going through it.
- The code uses PEP 585 builtin generics (`list[str]`), so Python 3.9+ is
  required despite the README saying 3.6+.

## Documentation update rules

- If you change dependencies, runtime files, or the run command, update both
  `README.md` and this file. Note that `README.md` currently understates the
  dependency set (see it listing only `requests`/`youtube-dl`).
