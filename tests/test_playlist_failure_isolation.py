import json
import os
import tempfile
import unittest
from unittest import mock

import httplib2
from googleapiclient.errors import HttpError

for _key in ("GOOGLE_TOKEN", "DISCORD_TOKEN", "DISCORD_CHANNEL_ID"):
    os.environ.setdefault(_key, "dummy")

from src import __main__ as app


def item(video_id):
    return {
        "videoOwnerChannelTitle": "owner",
        "resourceId": {"videoId": video_id},
        "title": video_id,
        "publishedAt": "2024-01-01T00:00:00Z",
    }


def details(video_ids):
    return video_ids, {
        video_id: {
            "snippet": {
                "title": video_id,
                "channelTitle": "owner",
                "publishedAt": "2024-01-01T00:00:00Z",
            }
        }
        for video_id in video_ids
    }


class TestPlaylistFailureIsolation(unittest.TestCase):
    def test_unavailable_playlist_remains_uninitialized_but_empty_playlist_is_saved(
        self,
    ):
        with tempfile.TemporaryDirectory() as directory:
            original = os.getcwd()
            self.addCleanup(os.chdir, original)
            os.chdir(directory)
            with open("playlists.json", "w") as f:
                json.dump(["unavailable", "empty"], f)
            youtube = mock.MagicMock()
            youtube.playlists.return_value.list.return_value.execute.side_effect = [
                {"items": []},
                {"items": [{"snippet": {"title": "t", "channelTitle": "c"}}]},
            ]
            with (
                mock.patch.object(app, "build", return_value=youtube),
                mock.patch.object(app, "get_playlist_items", return_value=[]) as items,
                mock.patch.object(app, "get_videos_details") as video_details,
                mock.patch.object(app, "send_discord_message") as sender,
                self.assertLogs(app.logger, "ERROR") as logs,
                self.assertRaises(SystemExit) as raised,
            ):
                app.main()

            self.assertEqual(raised.exception.code, 1)
            self.assertEqual(
                [record.getMessage() for record in logs.records],
                ["Playlist not found: unavailable"],
            )
            items.assert_called_once_with(youtube, "empty")
            video_details.assert_not_called()
            sender.assert_not_called()
            with open("already.json") as f:
                self.assertEqual(json.load(f), {"empty": []})

    def test_later_video_details_failure_preserves_progress_and_retries(self):
        with tempfile.TemporaryDirectory() as directory:
            original = os.getcwd()
            self.addCleanup(os.chdir, original)
            os.chdir(directory)
            with open("playlists.json", "w") as f:
                json.dump(["first", "later"], f)
            with open("already.json", "w") as f:
                json.dump({"first": [], "later": []}, f)
            youtube = mock.MagicMock()
            youtube.playlists.return_value.list.return_value.execute.return_value = {
                "items": [{"snippet": {"title": "t", "channelTitle": "c"}}]
            }
            error = HttpError(httplib2.Response({"status": 403}), b"{}")
            with (
                mock.patch.object(app, "build", return_value=youtube),
                mock.patch.object(
                    app, "get_playlist_items", side_effect=lambda _, p: [item(p)]
                ),
                mock.patch.object(
                    app,
                    "get_videos_details",
                    side_effect=[details(["first"]), error, details(["later"])],
                ),
                mock.patch.object(app, "send_discord_message") as sender,
                self.assertLogs(app.logger, "ERROR"),
            ):
                with self.assertRaises(SystemExit) as raised:
                    app.main()
                self.assertEqual(raised.exception.code, 1)
                with open("already.json") as f:
                    self.assertEqual(json.load(f), {"first": ["first"], "later": []})
                app.main()

            self.assertEqual(sender.call_count, 2)
            self.assertEqual(
                [call.args[3]["url"] for call in sender.call_args_list],
                ["https://youtu.be/first", "https://youtu.be/later"],
            )
            with open("already.json") as f:
                self.assertEqual(json.load(f), {"first": ["first"], "later": ["later"]})

    def test_failures_do_not_lose_progress_or_stop_later_playlists(self):
        with tempfile.TemporaryDirectory() as directory:
            original = os.getcwd()
            self.addCleanup(os.chdir, original)
            os.chdir(directory)
            with open("playlists.json", "w") as f:
                json.dump(["first", "failed", "empty", "last"], f)
            with open("already.json", "w") as f:
                json.dump({"first": [], "last": []}, f)

            youtube = mock.MagicMock()
            lookup = youtube.playlists.return_value.list.return_value.execute
            lookup.side_effect = [
                {"items": [{"snippet": {"title": "t", "channelTitle": "c"}}]},
                HttpError(httplib2.Response({"status": 403}), b"{}"),
                {"items": []},
                {"items": [{"snippet": {"title": "t", "channelTitle": "c"}}]},
            ]

            def playlist_items(_youtube, playlist):
                if playlist == "last":
                    with open("already.json") as f:
                        self.assertEqual(json.load(f)["first"], ["v1"])
                return [item({"first": "v1", "last": "v2"}[playlist])]

            with (
                mock.patch.object(app, "build", return_value=youtube),
                mock.patch.object(
                    app, "get_playlist_items", side_effect=playlist_items
                ),
                mock.patch.object(
                    app, "get_videos_details", side_effect=lambda _, ids: details(ids)
                ),
                mock.patch.object(app, "send_discord_message") as sender,
                self.assertRaises(SystemExit) as raised,
            ):
                app.main()
            self.assertEqual(raised.exception.code, 1)
            self.assertEqual(sender.call_count, 2)
            with open("already.json") as f:
                self.assertEqual(json.load(f), {"first": ["v1"], "last": ["v2"]})

    def test_failed_initial_playlist_is_not_initialized_by_later_checkpoint(self):
        with tempfile.TemporaryDirectory() as directory:
            original = os.getcwd()
            self.addCleanup(os.chdir, original)
            os.chdir(directory)
            with open("playlists.json", "w") as f:
                json.dump(["failed", "first_run"], f)
            youtube = mock.MagicMock()
            youtube.playlists.return_value.list.return_value.execute.return_value = {
                "items": [{"snippet": {"title": "t", "channelTitle": "c"}}]
            }
            error = HttpError(httplib2.Response({"status": 403}), b"{}")
            with (
                mock.patch.object(app, "build", return_value=youtube),
                mock.patch.object(
                    app, "get_playlist_items", side_effect=[error, [item("v1")]]
                ),
                mock.patch.object(
                    app, "get_videos_details", return_value=details(["v1"])
                ),
                mock.patch.object(app, "send_discord_message") as sender,
                self.assertRaises(SystemExit),
            ):
                app.main()
            sender.assert_not_called()
            with open("already.json") as f:
                self.assertEqual(json.load(f), {"first_run": ["v1"]})
