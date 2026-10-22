import json
import os

from googleapiclient.discovery import build

from src import config, send_discord_message

# YouTube Data API の videos.list で 1 回に指定できる ID の最大数
VIDEOS_LIST_MAX_IDS = 50


def get_playlist_items(youtube,
                       playlist_id):
    playlistitems_list_request = youtube.playlistItems().list(
        playlistId=playlist_id,
        part="snippet, contentDetails",
        maxResults=50
    )
    videos = []
    while playlistitems_list_request:
        playlistitems_list_response = playlistitems_list_request.execute()

        for playlist_item in playlistitems_list_response["items"]:
            videos.append(playlist_item["snippet"])

        playlistitems_list_request = youtube.playlistItems().list_next(
            playlistitems_list_request, playlistitems_list_response)

    return videos


def get_videos_details(youtube,
                       new_videos: list[str]):
    video_details_items = {}
    # videos.list の id パラメータは最大 50 件のため、端数も含めて 50 件ずつ分割して取得する
    for i in range(0, len(new_videos), VIDEOS_LIST_MAX_IDS):
        new_videos_temp = new_videos[i:i + VIDEOS_LIST_MAX_IDS]
        new_videos_details_request = youtube.videos().list(
            part="snippet, liveStreamingDetails",
            id=",".join(new_videos_temp)
        )
        while new_videos_details_request:
            new_videos_details = new_videos_details_request.execute()

            for video_details in new_videos_details["items"]:
                if video_details["snippet"]["liveBroadcastContent"] == "none":
                    video_details_items[video_details["id"]] = video_details

            new_videos_details_request = youtube.videos().list_next(
                new_videos_details_request, new_videos_details)
    # ライブ配信中・配信予定の動画を除いた ID を、渡された順序のまま返す
    ret = [video_id for video_id in new_videos if video_id in video_details_items]
    return ret, video_details_items


def main():
    already = {}
    if os.path.exists("already.json"):
        with open("already.json", "r") as f:
            already = json.load(f)

    youtube = build("youtube", "v3", developerKey=config.GOOGLE_TOKEN)

    with open("playlists.json", "r") as f:
        playlists = json.load(f)

    for playlist in playlists:
        playlist_details = youtube.playlists().list(
            part="snippet",
            id=playlist
        ).execute()
        playlist_title = playlist_details["items"][0]["snippet"]["title"]
        playlist_channel = playlist_details["items"][0]["snippet"]["channelTitle"]

        init = False
        if playlist not in already:
            init = True
            already[playlist] = []

        new_videos = []

        videos = get_playlist_items(youtube, playlist)
        for video in videos:
            if "videoOwnerChannelTitle" not in video:
                continue

            videoId = video["resourceId"]["videoId"]
            title = video["title"]
            videoUploader = video["videoOwnerChannelTitle"]
            publishedAt = video["publishedAt"]

            if videoId in already[playlist] or videoId in new_videos:
                continue
            new_videos.append(videoId)

            print("{title} - {uploader} ({date})"
                  .format(title=title, uploader=videoUploader, date=publishedAt))

        if len(new_videos) == 0:
            continue

        [notify_new_videos, video_details] = get_videos_details(youtube, new_videos)

        for videoId in notify_new_videos:
            if videoId not in video_details:
                continue
            title = video_details[videoId]["snippet"]["title"]
            channelTitle = video_details[videoId]["snippet"]["channelTitle"]
            if "liveStreamingDetails" in video_details[videoId]:
                if "scheduledStartTime" in video_details[videoId]["liveStreamingDetails"]:
                    startTime = video_details[videoId]["liveStreamingDetails"]["scheduledStartTime"]
                else:
                    startTime = video_details[videoId]["liveStreamingDetails"]["actualStartTime"]
            else:
                startTime = video_details[videoId]["snippet"]["publishedAt"]

            if not init:
                send_discord_message(config.DISCORD_TOKEN, config.DISCORD_CHANNEL_ID, "", {
                    "title": title,
                    "type": "rich",
                    "url": "https://youtu.be/%s" % videoId,
                    "fields": [
                        {
                            "name": "Playlist",
                            "value": "`{}` in `{}`".format(playlist_title, playlist_channel)
                        },
                        {
                            "name": "Uploader",
                            "value": "`{}`".format(channelTitle)
                        }
                    ],
                    "timestamp": startTime
                })
            already[playlist].append(videoId)

    with open("already.json", "w") as f:
        f.write(json.dumps(already))


if __name__ == "__main__":
    main()
