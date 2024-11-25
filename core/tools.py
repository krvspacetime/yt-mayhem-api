from googleapiclient.discovery import build


# Path to your client_secrets.json file
CLIENT_SECRETS_FILE = "core/client_secrets.json"

# This scope allows reading your YouTube subscriptions
SCOPES = [
    "https://www.googleapis.com/auth/youtube",
    "https://www.googleapis.com/auth/youtube.readonly",
    "https://www.googleapis.com/auth/youtubepartner",
    "https://www.googleapis.com/auth/youtube.force-ssl",
]


def get_playlist(credentials, playlist_id, max_results=50):
    youtube = build("youtube", "v3", credentials=credentials)

    # Request videos from the playlist
    request = youtube.playlistItems().list(
        part="snippet", playlistId=playlist_id, maxResults=max_results
    )
    response = request.execute()

    # Extract and return video details
    videos = []
    for item in response["items"]:
        videos.append(
            {
                "videoId": item["snippet"]["resourceId"]["videoId"],
                "title": item["snippet"]["title"],
                "description": item["snippet"]["description"],
                "publishedAt": item["snippet"]["publishedAt"],
                "thumbnails": item["snippet"]["thumbnails"],
            }
        )

    return {"videos": videos}


def add_playlist_videos(youtube, videos_request):
    added_videos = []
    if isinstance(videos_request.video_ids, str):
        request_body = {
            "snippet": {
                "playlistId": videos_request.playlist_id,
                "resourceId": {
                    "kind": "youtube#video",
                    "videoId": videos_request.video_ids,
                },
            }
        }

        request = youtube.playlistItems().insert(part="snippet", body=request_body)
        response = request.execute()
        added_videos = [
            {
                "videoId": videos_request.video_ids,
                "title": response["snippet"]["title"],
            }
        ]
    else:
        for video_id in videos_request.video_ids:
            request_body = {
                "snippet": {
                    "playlistId": videos_request.playlist_id,
                    "resourceId": {
                        "kind": "youtube#video",
                        "videoId": video_id,
                    },
                }
            }

            # Insert video into playlist
            request = youtube.playlistItems().insert(part="snippet", body=request_body)
            response = request.execute()
            added_videos.append(
                {
                    "videoId": response["snippet"]["resourceId"]["videoId"],
                    "title": response["snippet"]["title"],
                }
            )
    return {"message": "Videos added successfully.", "added_videos": added_videos}


def get_subscriptions(credentials, max_results: int):
    youtube = build("youtube", "v3", credentials=credentials)
    # Get the list of subscriptions
    subscriptions_request = youtube.subscriptions().list(
        part="snippet", mine=True, maxResults=max_results
    )
    subscriptions_response = subscriptions_request.execute()
    return subscriptions_response


def get_subscriptions_videos(credentials, max_results: int):
    youtube = build("youtube", "v3", credentials=credentials)
    subscriptions_response = get_subscriptions(credentials, max_results)
    channels = [
        item["snippet"]["resourceId"]["channelId"]
        for item in subscriptions_response.get("items", [])
    ]

    # Get the latest videos from subscribed channels
    videos = []
    for channel_id in channels:
        search_request = youtube.search().list(
            part="snippet",
            channelId=channel_id,
            maxResults=5,
            order="date",  # Latest videos first
        )
        search_response = search_request.execute()

        for item in search_response.get("items", []):
            videos.append(
                {
                    "videoId": item["id"]["videoId"],
                    "title": item["snippet"]["title"],
                    "description": item["snippet"]["description"],
                    "publishedAt": item["snippet"]["publishedAt"],
                    "thumbnail": item["snippet"]["thumbnails"]["default"]["url"],
                }
            )

    return {"videos": videos}
