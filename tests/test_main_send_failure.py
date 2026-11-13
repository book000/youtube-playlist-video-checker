import json
import os
import tempfile
import unittest
from unittest import mock

import requests

# src.config requires these environment variables at import time, so set dummy values before importing
for _key in ("GOOGLE_TOKEN", "DISCORD_TOKEN", "DISCORD_CHANNEL_ID"):
    os.environ.setdefault(_key, "dummy")

from src import __main__ as app

VIDEO_IDS = ["v1", "v2", "v3"]
FAILING_URL = "https://youtu.be/v2"


def playlist_items():
    return [
        {
            "videoOwnerChannelTitle": "uploader",
            "resourceId": {"videoId": video_id},
            "title": "title " + video_id,
            "publishedAt": "2024-01-01T00:00:00Z",
        }
        for video_id in VIDEO_IDS
    ]


def video_details():
    details = {
        video_id: {
            "snippet": {
                "title": "title " + video_id,
                "channelTitle": "uploader",
                "publishedAt": "2024-01-01T00:00:00Z",
            }
        }
        for video_id in VIDEO_IDS
    }
    return VIDEO_IDS, details


def fail_for_second_video(token, channel_id, message, embed):
    if embed["url"] == FAILING_URL:
        raise requests.HTTPError("500 Server Error")


class TestMainSendFailure(unittest.TestCase):
    def setUp(self):
        original_cwd = os.getcwd()
        self.addCleanup(os.chdir, original_cwd)
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        os.chdir(tmp.name)
        with open("playlists.json", "w") as f:
            json.dump(["PL1"], f)

    def seed_already(self, already):
        with open("already.json", "w") as f:
            json.dump(already, f)

    def read_already(self):
        with open("already.json") as f:
            return json.load(f)

    def run_main(self, send):
        youtube = mock.MagicMock()
        youtube.playlists.return_value.list.return_value.execute.return_value = {
            "items": [{"snippet": {"title": "playlist", "channelTitle": "owner"}}]
        }
        with (
            mock.patch.object(app, "build", return_value=youtube),
            mock.patch.object(app, "get_playlist_items", return_value=playlist_items()),
            mock.patch.object(app, "get_videos_details", return_value=video_details()),
            mock.patch.object(app, "send_discord_message", side_effect=send) as sender,
        ):
            app.main()
        return sender

    def test_failed_send_is_not_recorded_and_others_are(self):
        self.seed_already({"PL1": ["old"]})

        sender = self.run_main(fail_for_second_video)

        self.assertEqual(sender.call_count, 3)
        self.assertEqual(self.read_already(), {"PL1": ["old", "v1", "v3"]})

    def test_first_run_records_ids_without_sending(self):
        sender = self.run_main(fail_for_second_video)

        sender.assert_not_called()
        self.assertEqual(self.read_already(), {"PL1": ["v1", "v2", "v3"]})


if __name__ == "__main__":
    unittest.main()
