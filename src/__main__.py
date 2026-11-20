import contextlib
import fcntl
import json
import os
import re
import sys
import tempfile

import requests
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

from src import config, logger, send_discord_message

# YouTube Data API limit on IDs per videos.list call
VIDEOS_LIST_MAX_IDS = 50

LOCK_PATH = "already.json.lock"


def get_playlist_items(youtube, playlist_id):
    playlistitems_list_request = youtube.playlistItems().list(
        playlistId=playlist_id, part="snippet, contentDetails", maxResults=50
    )
    videos = []
    while playlistitems_list_request:
        playlistitems_list_response = playlistitems_list_request.execute()

        for playlist_item in playlistitems_list_response["items"]:
            videos.append(playlist_item["snippet"])

        playlistitems_list_request = youtube.playlistItems().list_next(
            playlistitems_list_request, playlistitems_list_response
        )

    return videos


def get_videos_details(youtube, new_videos: list[str]):
    video_details_items = {}
    for i in range(0, len(new_videos), VIDEOS_LIST_MAX_IDS):
        new_videos_temp = new_videos[i : i + VIDEOS_LIST_MAX_IDS]
        new_videos_details_request = youtube.videos().list(
            part="snippet, liveStreamingDetails", id=",".join(new_videos_temp)
        )
        while new_videos_details_request:
            new_videos_details = new_videos_details_request.execute()

            for video_details in new_videos_details["items"]:
                if video_details["snippet"]["liveBroadcastContent"] == "none":
                    video_details_items[video_details["id"]] = video_details

            new_videos_details_request = youtube.videos().list_next(
                new_videos_details_request, new_videos_details
            )
    # Keep the caller's order so notifications stay in playlist order
    ret = [video_id for video_id in new_videos if video_id in video_details_items]
    return ret, video_details_items


def describe_http_error(error: HttpError) -> str:
    """Summarize an HttpError without the request URI, which embeds the API key.

    Only the HTTP status and machine-readable reason codes are included.
    """
    description = "HTTP {status}".format(status=error.status_code)
    details = error.error_details
    reasons = []
    if isinstance(details, list):
        for item in details:
            reason = item.get("reason") if isinstance(item, dict) else None
            if isinstance(reason, str) and re.fullmatch(r"[A-Za-z_]+", reason):
                reasons.append(reason)
    if reasons:
        description += ", reason: " + ",".join(reasons)
    return description


def check_playlists():
    already = {}
    if os.path.exists("already.json"):
        with open("already.json", "r") as f:
            already = json.load(f)

    youtube = build("youtube", "v3", developerKey=config.GOOGLE_TOKEN)

    with open("playlists.json", "r") as f:
        playlists = json.load(f)

    failed = False
    for playlist in playlists:
        try:
            if not check_playlist(youtube, playlist, already):
                failed = True
        except HttpError as e:
            logger.error(
                "YouTube API request failed: {failure}".format(
                    failure=describe_http_error(e)
                )
            )
            failed = True
    return not failed


class AlreadyRunningError(Exception):
    """Another process holds the instance lock."""


class InstanceLockError(Exception):
    """The instance lock could not be acquired for a reason other than contention."""


@contextlib.contextmanager
def single_instance_lock():
    """Hold an exclusive advisory lock on LOCK_PATH for the duration of the block.

    Raises AlreadyRunningError if another process holds the lock and
    InstanceLockError if the lock file cannot be opened or locked. The kernel
    releases the lock when the process exits, so a crash leaves no stale lock.
    The lock file is intentionally never deleted: removing it would let a second
    process lock a different inode.
    """
    with contextlib.ExitStack() as stack:
        try:
            lock_file = stack.enter_context(open(LOCK_PATH, "a"))
        except OSError as e:
            raise InstanceLockError(str(e)) from e
        try:
            fcntl.flock(lock_file, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as e:
            raise AlreadyRunningError() from e
        except OSError as e:
            raise InstanceLockError(str(e)) from e
        yield


def save_already(already):
    path = None
    try:
        with tempfile.NamedTemporaryFile(mode="w", dir=".", delete=False) as f:
            path = f.name
            json.dump(already, f)
            f.flush()
            os.fsync(f.fileno())
        os.replace(path, "already.json")
    finally:
        if path and os.path.exists(path):
            os.unlink(path)


def check_playlist(youtube, playlist, already):
    playlist_details = youtube.playlists().list(part="snippet", id=playlist).execute()
    if not playlist_details.get("items"):
        logger.error("Playlist not found: {playlist}".format(playlist=playlist))
        return False
    playlist_title = playlist_details["items"][0]["snippet"]["title"]
    playlist_channel = playlist_details["items"][0]["snippet"]["channelTitle"]

    init = playlist not in already
    seen = already.get(playlist, [])

    new_videos = []

    videos = get_playlist_items(youtube, playlist)
    for video in videos:
        if "videoOwnerChannelTitle" not in video:
            continue

        videoId = video["resourceId"]["videoId"]
        title = video["title"]
        videoUploader = video["videoOwnerChannelTitle"]
        publishedAt = video["publishedAt"]

        if videoId in seen or videoId in new_videos:
            continue
        new_videos.append(videoId)

        print(
            "{title} - {uploader} ({date})".format(
                title=title, uploader=videoUploader, date=publishedAt
            )
        )

    if len(new_videos) == 0:
        if init:
            already[playlist] = seen
            save_already(already)
        return True

    [notify_new_videos, video_details] = get_videos_details(youtube, new_videos)

    for videoId in notify_new_videos:
        if videoId not in video_details:
            continue
        title = video_details[videoId]["snippet"]["title"]
        channelTitle = video_details[videoId]["snippet"]["channelTitle"]
        if "liveStreamingDetails" in video_details[videoId]:
            if "scheduledStartTime" in video_details[videoId]["liveStreamingDetails"]:
                startTime = video_details[videoId]["liveStreamingDetails"][
                    "scheduledStartTime"
                ]
            else:
                startTime = video_details[videoId]["liveStreamingDetails"][
                    "actualStartTime"
                ]
        else:
            startTime = video_details[videoId]["snippet"]["publishedAt"]

        if not init:
            try:
                send_discord_message(
                    config.DISCORD_TOKEN,
                    config.DISCORD_CHANNEL_ID,
                    "",
                    {
                        "title": title,
                        "type": "rich",
                        "url": "https://youtu.be/%s" % videoId,
                        "fields": [
                            {
                                "name": "Playlist",
                                "value": "`{}` in `{}`".format(
                                    playlist_title, playlist_channel
                                ),
                            },
                            {
                                "name": "Uploader",
                                "value": "`{}`".format(channelTitle),
                            },
                        ],
                        "timestamp": startTime,
                    },
                )
            except requests.RequestException as e:
                logger.error(
                    "Failed to send notification for video {video} in playlist {playlist}: {error}".format(
                        video=videoId, playlist=playlist, error=e
                    )
                )
                continue
        seen.append(videoId)
        if not init:
            save_already(already)

    if init:
        already[playlist] = seen
        save_already(already)
    return True


def run_checks():
    failure = None
    try:
        if not check_playlists():
            sys.exit(1)
    except HttpError as e:
        failure = describe_http_error(e)
    # Exit outside the except block so the HttpError, whose message holds the
    # API key, is not chained onto SystemExit.
    if failure is not None:
        logger.error("YouTube API request failed: {failure}".format(failure=failure))
        sys.exit(1)


def main():
    lock_failure = None
    try:
        with single_instance_lock():
            run_checks()
    except AlreadyRunningError:
        lock_failure = "Another instance is already running; exiting"
    except InstanceLockError as e:
        lock_failure = "Cannot acquire the instance lock: {error}".format(error=e)
    if lock_failure is not None:
        logger.error(lock_failure)
        sys.exit(1)


if __name__ == "__main__":
    main()
