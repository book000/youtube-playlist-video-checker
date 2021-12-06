import youtube_dl
import json
import os
import requests
import datetime


def sendMessage(token: str, channelId: str, message: str = "", embed: dict = None):
    print("[INFO] sendMessage: {message}".format(message=message))
    headers = {
        "Content-Type": "application/json",
        "Authorization": "Bot {token}".format(token=token),
        "User-Agent": "Bot"
    }
    params = {
        "content": message,
        "embed": embed
    }
    response = requests.post(
        "https://discord.com/api/channels/{channelId}/messages".format(channelId=channelId), headers=headers,
        json=params)
    print("[INFO] response: {code}".format(code=response.status_code))
    print("[INFO] response: {message}".format(message=response.text))


already = {}
if os.path.exists("already.json"):
    with open("already.json", "r") as f:
        already = json.load(f)

if not os.path.exists("config.json"):
    print("The config.json cannot be found.")
    exit(1)

with open("config.json", "r") as f:
    config = json.load(f)

if not os.path.exists("playlists.json"):
    print("The playlists.json cannot be found.")
    exit(1)

with open("playlists.json", "r") as f:
    playlists = json.load(f)

for playlist_id in playlists:
    ydl = youtube_dl.YoutubeDL({"dump_single_json": "True",
                                "extract_flat": "True",
                                "continue_dl": True,
                                "ignoreerrors": True})

    url = "https://www.youtube.com/playlist?list=" + playlist_id

    with ydl:
        result = ydl.extract_info(url, False)
        
    if result is None:
        continue

    if not os.path.exists("output/"):
        os.mkdir("output/")
    with open("output/{playlist_id}.json".format(playlist_id=playlist_id), "w") as f:
        f.write(json.dumps(result))

    playlist_title = result["title"]
    entries = result["entries"]

    init = False
    if playlist_id not in already:
        init = True
        already[playlist_id] = []

    for entry in entries:
        if entry is None:
            continue

        vid = entry["id"]
        title = entry["title"]
        upload_date = entry["upload_date"]
        uploader = entry["uploader"]
        webpage_url = entry["webpage_url"]
        duration_sec = entry["duration"]  # sec
        duration = str(datetime.timedelta(seconds=duration_sec))

        if vid in already[playlist_id]:
            continue

        already[playlist_id].append(vid)

        print("{title} - {uploader} ({date} / {sec}sec)"
              .format(title=title, uploader=uploader, date=upload_date, sec=duration))

        if not init:
            sendMessage(config["discord_token"], config["discord_channel"], "", {
                "title": "{}".format(title),
                "type": "rich",
                "url": webpage_url,
                "fields": [
                    {
                        "name": "Playlist",
                        "value": "`{}`".format(playlist_title)
                    },
                    {
                        "name": "Upload",
                        "value": "`{}`".format(uploader)
                    },
                    {
                        "name": "Duration",
                        "value": duration
                    },
                    {
                        "name": "Date",
                        "value": "{}/{}/{}".format(
                            upload_date[0:4],
                            upload_date[4:6],
                            upload_date[6:8]
                        )
                    }
                ]
            })

with open("already.json", "w") as f:
    f.write(json.dumps(already))
