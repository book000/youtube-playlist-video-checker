# youtube-playlist-video-checker

Notify Discord of newly added videos in multiple YouTube playlists.

The script checks each playlist through the YouTube Data API v3 and posts a Discord embed for every video it has not announced yet. It is meant to be run periodically (for example from cron).

## Requirements

- A valid Discord bot token and a channel the bot can post messages to
- A Google Cloud Platform API key with the YouTube Data API v3 enabled
- Python 3.9+
- The packages in [requirements.txt](requirements.txt), notably `google-api-python-client`, `python-dotenv` and `requests`.

## Installation

1. Clone the repository: `git clone https://github.com/book000/youtube-playlist-video-checker.git`
2. Install the dependencies: `pip3 install -U -r requirements.txt`

## Configuration

- Copy `sample.env` to `.env` and fill in the values. All three are required; the program exits if one is missing.
  - `DISCORD_TOKEN`: Discord bot token
  - `DISCORD_CHANNEL_ID`: ID of the channel to post to
  - `GOOGLE_TOKEN`: Google Cloud Platform API key
- Copy `playlists.sample.json` to `playlists.json` and list the IDs of the playlists to check (a JSON array of strings).

## Usage

```shell
cd /path/to/youtube-playlist-video-checker
python3 -m src
```

Run it from the project root: `playlists.json`, `already.json` and the `logs/` directory are read and written relative to the current directory.

- `already.json` is created automatically and records the video IDs already announced for each playlist, so each video is announced only once.
- The first run for a playlist only records its existing videos and does not post them to Discord.
- Live streams and premieres are skipped until they become regular videos.

## Warning / Disclaimer

The developer is not responsible for any problems caused by the user using this project.

## License

The license for this project is [MIT License](LICENSE).
