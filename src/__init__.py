from __future__ import annotations

import datetime
import logging
import math
import os
import time
from logging.handlers import TimedRotatingFileHandler

import requests


def init_logger(child_name: str | None = None) -> logging.Logger:
    _logger = logging.getLogger("youtube-playlist-video-checker")
    if child_name is not None:
        return _logger.getChild(child_name)
    dt = datetime.datetime.now().date()
    date_time = dt.strftime("%Y-%m-%d")

    if not os.path.exists("logs/"):
        os.mkdir("logs/")

    rotatedHandler = TimedRotatingFileHandler(
        filename="logs/%s.log" % date_time,
        encoding="UTF-8",
        when="MIDNIGHT",
        backupCount=30,
    )
    rotatedHandler.setLevel(logging.INFO)
    rotatedHandler.setFormatter(
        logging.Formatter("[%(asctime)s] [%(name)s/%(levelname)s]: %(message)s")
    )
    _logger.addHandler(rotatedHandler)
    streamHandler = logging.StreamHandler()
    streamHandler.setFormatter(
        logging.Formatter("[%(asctime)s] [%(name)s/%(levelname)s]: %(message)s")
    )
    _logger.addHandler(streamHandler)

    return _logger


logger = init_logger()


REQUEST_TIMEOUT_SECONDS = 30
MAX_RATE_LIMIT_RETRIES = 3
MAX_RATE_LIMIT_WAIT_SECONDS = 60


def _retry_after_seconds(response: requests.Response) -> float | None:
    try:
        value = response.json()["retry_after"]
    except (ValueError, KeyError, TypeError):
        value = response.headers.get("Retry-After")
    try:
        seconds = float(value)
    except (ValueError, TypeError):
        return None
    return seconds if math.isfinite(seconds) and seconds >= 0 else None


def send_discord_message(
    token: str, channelId: str, message: str = "", embed: dict | None = None
):
    """Post a message to a Discord channel.

    On HTTP 429 the request is retried up to MAX_RATE_LIMIT_RETRIES times,
    waiting the delay Discord asks for (at most MAX_RATE_LIMIT_WAIT_SECONDS).

    Raises:
        requests.HTTPError: the final response status is 400 or above.
        requests.RequestException: a network error or timeout occurred.
    """
    logger.debug("sendDiscordMessage: {message}".format(message=message))
    headers = {
        "Content-Type": "application/json",
        "Authorization": "Bot {token}".format(token=token),
        "User-Agent": "Bot",
    }
    params = {"content": message}
    if embed is not None:
        params["embeds"] = [embed]
    url = "https://discord.com/api/channels/{channelId}/messages".format(
        channelId=channelId
    )
    for attempt in range(MAX_RATE_LIMIT_RETRIES + 1):
        response = requests.post(
            url, headers=headers, json=params, timeout=REQUEST_TIMEOUT_SECONDS
        )
        logger.debug("response: {code}".format(code=response.status_code))
        logger.debug("response: {message}".format(message=response.text))
        if response.status_code != 429 or attempt == MAX_RATE_LIMIT_RETRIES:
            break
        wait = _retry_after_seconds(response)
        if wait is None or wait > MAX_RATE_LIMIT_WAIT_SECONDS:
            break
        logger.warning(
            "Rate limited by Discord; retrying in {wait} seconds".format(wait=wait)
        )
        time.sleep(wait)
    if response.status_code >= 400:
        logger.error(
            "Discord request failed: {code} {body}".format(
                code=response.status_code, body=response.text
            )
        )
        response.raise_for_status()
