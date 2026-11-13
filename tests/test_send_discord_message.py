import contextlib
import json
import os
import unittest
from unittest import mock

import requests

# src.config requires these environment variables at import time, so set dummy values before importing
for _key in ("GOOGLE_TOKEN", "DISCORD_TOKEN", "DISCORD_CHANNEL_ID"):
    os.environ.setdefault(_key, "dummy")

from src import send_discord_message

LOGGER_NAME = "youtube-playlist-video-checker"
TOKEN = "secret-token-xyz"


def make_response(status_code=200, body=None, text=None, headers=None):
    """Build a real requests.Response so raise_for_status behaves as in production."""
    response = requests.Response()
    response.status_code = status_code
    if text is None:
        text = json.dumps(body) if body is not None else ""
    response._content = text.encode("utf-8")
    response.headers.update(headers or {})
    return response


@contextlib.contextmanager
def patched_network(responses):
    """Patch requests.post to return `responses` in order, and time.sleep to a no-op."""
    with (
        mock.patch("src.requests.post", side_effect=responses) as post,
        mock.patch("src.time.sleep") as sleep,
    ):
        yield post, sleep


def send(responses, **kwargs):
    with patched_network(responses) as (post, sleep):
        send_discord_message(TOKEN, "123", **kwargs)
    return post, sleep


class TestSendDiscordMessage(unittest.TestCase):
    def send_failing(self, responses):
        with (
            patched_network(responses) as (post, sleep),
            self.assertRaises(requests.HTTPError),
        ):
            send_discord_message(TOKEN, "123", message="hello")
        return post, sleep

    def test_payload_uses_embeds_array(self):
        embed = {"title": "t", "url": "https://youtu.be/v1"}

        post, _ = send([make_response(200)], message="hello", embed=embed)

        self.assertEqual(
            post.call_args.kwargs["json"], {"content": "hello", "embeds": [embed]}
        )

    def test_payload_without_embed_has_no_embed_keys(self):
        post, _ = send([make_response(200)], message="hello")

        self.assertEqual(post.call_args.kwargs["json"], {"content": "hello"})

    def test_success_posts_once_with_timeout(self):
        post, sleep = send([make_response(200)], message="hello")

        self.assertEqual(post.call_count, 1)
        self.assertEqual(post.call_args.kwargs["timeout"], 30)
        sleep.assert_not_called()

    def test_rate_limit_is_retried_after_body_retry_after(self):
        post, sleep = send(
            [make_response(429, {"retry_after": 1.5}), make_response(200)],
            message="hello",
        )

        self.assertEqual(post.call_count, 2)
        sleep.assert_called_once_with(1.5)

    def test_rate_limit_falls_back_to_retry_after_header(self):
        cases = {
            "non-json body": make_response(
                429, text="not json", headers={"Retry-After": "2"}
            ),
            "body without retry_after": make_response(
                429, {"message": "slow down"}, headers={"Retry-After": "2"}
            ),
        }
        for name, rate_limited in cases.items():
            with self.subTest(case=name):
                post, sleep = send([rate_limited, make_response(200)], message="hello")

                self.assertEqual(post.call_count, 2)
                sleep.assert_called_once_with(2.0)

    def test_rate_limit_without_usable_wait_raises_without_sleeping(self):
        post, sleep = self.send_failing([make_response(429, text="not json")])

        self.assertEqual(post.call_count, 1)
        sleep.assert_not_called()

    def test_rate_limit_retries_are_bounded(self):
        responses = [make_response(429, {"retry_after": 1}) for _ in range(4)]

        post, sleep = self.send_failing(responses)

        self.assertEqual(post.call_count, 4)
        self.assertEqual(sleep.call_count, 3)

    def test_rate_limit_wait_over_cap_raises_without_sleeping(self):
        post, sleep = self.send_failing([make_response(429, {"retry_after": 61})])

        self.assertEqual(post.call_count, 1)
        sleep.assert_not_called()

    def test_http_errors_raise_without_retry(self):
        for status_code in (400, 500):
            with self.subTest(status_code=status_code):
                post, sleep = self.send_failing(
                    [make_response(status_code, text="boom")]
                )

                self.assertEqual(post.call_count, 1)
                sleep.assert_not_called()

    def test_token_is_not_logged_or_raised(self):
        with (
            self.assertLogs(LOGGER_NAME, level="DEBUG") as logs,
            patched_network([make_response(403, text="forbidden")]),
            self.assertRaises(requests.HTTPError) as raised,
        ):
            send_discord_message(TOKEN, "123", message="hello")

        for record in logs.records:
            self.assertNotIn(TOKEN, record.getMessage())
        self.assertNotIn(TOKEN, "\n".join(logs.output))
        self.assertNotIn(TOKEN, str(raised.exception))


if __name__ == "__main__":
    unittest.main()
