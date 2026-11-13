# Copilot code review instructions

Follow `AGENTS.md` for project guidance. Prioritize correctness and secret safety over style nits.

## Language

Deliverables (commit messages, PR/Issue text, review comments, code comments, docs) are written in English. Runtime messages are English. Flag non-English prose in new or changed deliverables, except quotations, technical identifiers, generated files and external source text.

## Review checklist

- **Secrets and state must not be committed.** Flag real values in `.env`, `playlists.json` or `already.json`, or removal of those entries from `.gitignore`. Only `sample.env` and `playlists.sample.json` may contain placeholders.
- **Preserve "announce once".** State lives only in `already.json`. Flag changes that could re-announce old videos, drop the dedup check (`videoId in already[playlist]`), or record an ID before the video is handled.
- **Preserve the silent first run.** A new playlist (`init = True`) records its videos without sending them to Discord.
- **Preserve the live/upcoming filter** in `get_videos_details` (`liveBroadcastContent == "none"`).
- **Pagination.** YouTube calls use `list_next` loops; flag edits that read only the first page.
- **Fatal-on-missing config** in `src/config.py` is intentional; do not suggest silent defaults for required keys.
- **HTTP error handling.** `send_discord_message` and the YouTube calls do not check for failures or rate limits. Raising this is welcome but is not a blocker for unrelated changes.
- Keep `README.md` and `AGENTS.md` in sync with dependency, runtime-file or run-command changes.

## Known non-issues (do not flag)

- `str.format()` / `%` formatting instead of f-strings.
- Direct `requests` POST to the Discord REST API instead of a library.
- Small test coverage; do not request tests unless the PR adds testable logic.
