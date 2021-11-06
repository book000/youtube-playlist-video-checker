import json
import os

from googleapiclient.discovery import build

from src import config, send_discord_message


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

        videos = get_playlist_items(youtube, playlist)
        for video in videos:
            if "videoOwnerChannelTitle" not in video:
                continue

            videoId = video["resourceId"]["videoId"]
            title = video["title"]
            videoUploader = video["videoOwnerChannelTitle"]
            publishedAt = video["publishedAt"]

            if videoId in already[playlist]:
                continue
            already[playlist].append(videoId)

            print("{title} - {uploader} ({date})"
                  .format(title=title, uploader=videoUploader, date=publishedAt))

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
                            "value": "`{}`".format(videoUploader)
                        }
                    ],
                    "timestamp": publishedAt
                })

    with open("already.json", "w") as f:
        f.write(json.dumps(already))


if __name__ == "__main__":
    main()
