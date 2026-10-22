import os
import unittest
from unittest import mock

# src.config は import 時に環境変数を要求するため、ダミー値を設定してから import する
for _key in ("GOOGLE_TOKEN", "DISCORD_TOKEN", "DISCORD_CHANNEL_ID"):
    os.environ.setdefault(_key, "dummy")

from src.__main__ import get_videos_details  # noqa: E402


def create_youtube_mock(live_ids=()):
    """videos().list(id=...) の呼び出しを記録し、ID ごとの動画情報を返すモック"""
    youtube = mock.MagicMock()
    requested_id_counts = []

    def videos_list(part, id):
        ids = id.split(",")
        requested_id_counts.append(len(ids))
        request = mock.MagicMock()
        request.execute.return_value = {
            "items": [
                {
                    "id": video_id,
                    "snippet": {
                        "liveBroadcastContent": "live" if video_id in live_ids else "none"
                    },
                }
                for video_id in ids
            ]
        }
        return request

    youtube.videos.return_value.list.side_effect = videos_list
    youtube.videos.return_value.list_next.return_value = None
    return youtube, requested_id_counts


class TestGetVideosDetails(unittest.TestCase):
    def test_all_videos_are_fetched(self):
        for count in (0, 1, 49, 50, 51, 101):
            with self.subTest(count=count):
                video_ids = ["video%d" % i for i in range(count)]
                youtube, requested_id_counts = create_youtube_mock()

                notify_ids, details = get_videos_details(youtube, video_ids)

                self.assertEqual(notify_ids, video_ids)
                self.assertEqual(list(details.keys()), video_ids)
                self.assertEqual(sum(requested_id_counts), count)
                self.assertTrue(all(c <= 50 for c in requested_id_counts))
                self.assertEqual(len(requested_id_counts), -(-count // 50))

    def test_live_videos_are_excluded(self):
        video_ids = ["video%d" % i for i in range(51)]
        live_ids = {"video0", "video50"}
        youtube, _ = create_youtube_mock(live_ids)

        notify_ids, details = get_videos_details(youtube, video_ids)

        expected = [v for v in video_ids if v not in live_ids]
        self.assertEqual(notify_ids, expected)
        self.assertEqual(list(details.keys()), expected)


if __name__ == "__main__":
    unittest.main()
