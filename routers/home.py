import random
from googleapiclient.errors import HttpError
from googleapiclient.discovery import build

from fastapi import APIRouter, Depends, HTTPException
from typing import List, Dict
from ..dependencies.dependency import get_credentials

router = APIRouter(prefix="/home", tags=["Home Feed"])


# Function to fetch user's subscriptions
def get_subscriptions(youtube) -> List[str]:
    subscriptions = []
    request = youtube.subscriptions().list(part="snippet", mine=True, maxResults=50)

    while request:
        response = request.execute()
        for item in response.get("items", []):
            subscriptions.append(item["snippet"]["resourceId"]["channelId"])
        request = youtube.subscriptions().list_next(request, response)

    return subscriptions


# Function to fetch latest videos from subscriptions
def get_subscription_videos(youtube, channel_ids: List[str]) -> List[Dict]:
    videos = []
    for channel_id in channel_ids[:10]:  # Limit to avoid quota issues
        request = youtube.search().list(
            part="snippet", channelId=channel_id, order="date", maxResults=5
        )
        response = request.execute()

        for item in response.get("items", []):
            # Check if it's a video, not a channel or playlist
            if "id" in item and item["id"].get("kind") == "youtube#video":
                videos.append(
                    {
                        "title": item["snippet"]["title"],
                        "videoId": item["id"]["videoId"],  # Safe access
                        "thumbnail": item["snippet"]["thumbnails"]["high"]["url"],
                        "channelTitle": item["snippet"]["channelTitle"],
                    }
                )

    return videos


# Function to fetch trending videos
def get_trending_videos(youtube) -> List[Dict]:
    request = youtube.videos().list(
        part="snippet", chart="mostPopular", regionCode="US", maxResults=10
    )
    response = request.execute()
    return [
        {
            "title": item["snippet"]["title"],
            "videoId": item["id"],
            "thumbnail": item["snippet"]["thumbnails"]["high"]["url"],
            "channelTitle": item["snippet"]["channelTitle"],
        }
        for item in response.get("items", [])
    ]


@router.get("/")
def get_homefeed(credentials=Depends(get_credentials)):
    youtube = build("youtube", "v3", credentials=credentials)
    try:
        # Step 1: Fetch 30 subscribed channels
        subscriptions = (
            youtube.subscriptions()
            .list(part="snippet", mine=True, maxResults=5)
            .execute()
        )

        channel_ids = [
            item["snippet"]["resourceId"]["channelId"]
            for item in subscriptions.get("items", [])
        ]

        videos = []

        # Step 2: Fetch 1-3 random videos per channel
        for channel_id in channel_ids:
            num_videos = random.randint(1, 3)
            request = youtube.search().list(
                part="snippet",
                channelId=channel_id,
                order="date",
                maxResults=num_videos,
            )
            response = request.execute()

            for item in response.get("items", []):
                if "id" in item and item["id"].get("kind") == "youtube#video":
                    videos.append(
                        {
                            "title": item["snippet"]["title"],
                            "videoId": item["id"]["videoId"],
                            "thumbnail": item["snippet"]["thumbnails"]["high"]["url"],
                            "channelTitle": item["snippet"]["channelTitle"],
                        }
                    )

        # Step 3: Trim to exactly 50 videos
        random.shuffle(videos)  # Shuffle to keep it dynamic
        videos = videos[:10]

        return {"videos": videos}

    except HttpError as e:
        if e.resp.status == 403 and "quota" in e.content.decode():
            raise HTTPException(
                status_code=403, detail="Quota exceeded. Please try again later."
            )
        else:
            raise HTTPException(status_code=e.resp.status, detail=str(e))
