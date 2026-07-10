# Copilot code review instructions

Small Python CLI: polls YouTube playlists (Data API v3) and posts a Discord
embed per newly added video. No tests, linter, or CI exist. Prioritize
correctness and secret-safety over style nits.

## Review priorities

- **Secrets and state must not be committed.** Flag any diff that adds real
  values to `.env`, `playlists.json`, or `already.json`, or that removes those
  entries from `.gitignore`. Only `sample.env` / `playlists.sample.json` may
  contain placeholders.
- **Preserve "announce once" idempotency.** State lives only in `already.json`.
  Flag changes that could re-announce old videos, drop the dedup check
  (`videoId in already[playlist]`), or write state before a video is actually
  sent.
- **Preserve the silent first run.** When a playlist is new (`init = True`),
  its existing videos are recorded but not sent to Discord. Flag edits that
  would notify the whole backlog on first run.
- **Preserve the live/upcoming filter.** `get_videos_details` keeps only
  `liveBroadcastContent == "none"`. Flag removal of this filter.
- **API pagination.** YouTube calls use `list_next` loops; flag edits that read
  only the first page.
- **HTTP error handling.** `send_discord_message` and the YouTube calls do not
  check for failures/rate limits. Raising this is welcome, but see non-issues
  below before treating it as a blocker.
- **Fatal-on-missing config** in `src/config.py` (`logger.critical` +
  `exit(1)`) is intentional; do not suggest silently defaulting required keys.

## Known non-issues (do not flag)

- `str.format()` and `%` formatting instead of f-strings — this is the
  established style; do not suggest converting.
- Direct `requests` POST to the Discord REST API instead of a Discord library —
  intentional and minimal.
- `list[str]` type hints while the README says Python 3.6+ — the README is
  stale; the code targets 3.9+. Flag the README, not the code.
- `requirements.txt` being UTF-16 encoded is a pre-existing repo condition, not
  introduced by a normal PR; only mention it if a PR touches that file.
- Absence of a test suite / CI — known; do not request adding tests unless the
  PR itself adds testable logic.

## Conventions

- Python, standard-library-first, `snake_case` functions.
- Runtime files (`.env`, `playlists.json`, `already.json`, `logs/`) are
  git-ignored and read from the current working directory at run time.
