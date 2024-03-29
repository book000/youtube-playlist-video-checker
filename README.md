# youtube-playlist-video-checker

Notify Discord of newly added videos to multiple YouTube playlists.

## Requirements

- Vaild Discord Bot token and Writeable message channel
- Python 3.6+
- [requirements.txt](requirements.txt): `requests`, `youtube-dl`

## Installation

1. Clone from GitHub repository: `git clone https://github.com/book000/youtube-playlist-video-checker.git`
2. Install the dependency package from `requirements.txt`: `pip3 install -U -r requirements.txt`

## Configuration

- Rewrite `sample.env` and rename to `.env`.
  - `DISCORD_TOKEN`: Discord Bot token
  - `DISCORD_CHANNEL_ID`: Discord Send to channel ID
  - `GOOGLE_TOKEN`: Google Cloud Platform API key
- Rewrite `playlists.sample.json` and rename to `playlists.json`.
  - Enter the ID of the playlist to check.

## Usage

```shell
cd /path/to/
python3 -m src
```

The `.env` file in the current directory will be read, so change to the root directory of the project in advance before executing.

## Warning / Disclaimer

The developer is not responsible for any problems caused by the user using this project.

## License

The license for this project is [MIT License](LICENSE).
