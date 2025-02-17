from googleapiclient.discovery import build
from datetime import datetime
from models.playlists import SortOrder


def get_playlists(credentials, channel_id, max_results=50, page_token=None):
    youtube = build("youtube", "v3", credentials=credentials)

    # Request videos from the playlist
    request = youtube.playlists().list(
        part="snippet",
        channelId=channel_id,
        maxResults=max_results,
        pageToken=page_token,
    )
    response = request.execute()
    return {
        "playlists": response["items"],
        "nextPageToken": response.get("nextPageToken"),
        "totalResults": response.get("pageInfo", {}).get("totalResults"),
        "resultsPerPage": response.get("pageInfo", {}).get("resultsPerPage"),
    }


def get_playlist_items(
    credentials, playlist_id, max_results=50, sort_order: SortOrder = SortOrder.OLDEST
):
    youtube = build("youtube", "v3", credentials=credentials)
    videos = []
    next_page_token = None

    while True:
        # Request videos from the playlist
        request = youtube.playlistItems().list(
            part="snippet",
            playlistId=playlist_id,
            maxResults=min(max_results, 50),  # YouTube API limit is 50
            pageToken=next_page_token,
        )
        response = request.execute()
        print(f"totalResults: {response.get('pageInfo', {}).get('totalResults')}")

        # Extract video details
        for item in response["items"]:
            videos.append(item)

        # Check if there are more pages and if we need more results
        next_page_token = response.get("nextPageToken")
        if not next_page_token:
            break

    # Sort videos based on publishedAt using datetime parsing
    videos.sort(
        key=lambda x: (
            datetime.fromisoformat(
                x.get("snippet", {}).get("publishedAt", "").replace("Z", "+00:00")
            )
            if "publishedAt" in x.get("snippet", {})
            else datetime.min
        ),
        reverse=(sort_order == SortOrder.NEWEST),
    )

    return {
        "videos": videos,
    }


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
