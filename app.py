from dotenv import load_dotenv

from typing import Annotated
from fastapi import FastAPI, Query, Depends
from fastapi.exceptions import HTTPException
from fastapi.middleware.cors import CORSMiddleware
from .routers import downloads, search, channels, ouauth2, playlists

from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

from .core.tools import (
    get_subscriptions,
    get_subscriptions_videos,
)

from .dependencies.dependency import get_credentials, get_youtube

app = FastAPI()
app.include_router(downloads.router)
app.include_router(search.router)
app.include_router(channels.router)
app.include_router(ouauth2.router)
app.include_router(playlists.router)

load_dotenv()

origins = [
    "http://localhost.tiangolo.com",
    "https://localhost.tiangolo.com",
    "http://localhost",
    "http://localhost:5173",
    "http://localhost:5173/",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Endpoint to get subscribed channels
@app.get("/collect/channels/")
async def collect_channels(
    max_results: int = Query(10, ge=1, le=50), credentials=Depends(get_credentials)
):
    try:
        youtube = build("youtube", "v3", credentials=credentials)
        request = youtube.subscriptions().list(
            part="snippet",
            mine=True,  # This will get your subscriptions
            maxResults=max_results,
        )
        response = request.execute()
        return {"channels": response["items"]}

    except HttpError as e:
        raise HTTPException(status_code=500, detail=f"An error occurred: {e}")


@app.get("/collect/subscriptions/")
async def collect_subscriptions(
    credentials=Depends(get_credentials),
    max_results=Annotated[int, Query(50, ge=1, le=2000)],
):
    try:
        response = get_subscriptions(credentials, max_results)

        # Process and return the subscriptions
        return {"subscriptions": response.get("items", [])}

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/collect/comments/")
async def get_video_comments(
    video_id: str,
    max_results: int = Query(10, ge=1, le=100),
    page_token: str | None = None,
    youtube=Depends(get_youtube),
):
    """
    Get comments for a specific YouTube video.

    Args:
        video_id (str): The ID of the YouTube video.
        max_results (int): The maximum number of comments to retrieve.
        page_token (str): Token for pagination (optional).

    Returns:
        dict: A dictionary with the comments and pagination info.
    """
    try:
        # Make the API request to get comments
        request_params = {
            "part": "snippet",
            "videoId": video_id,
            "maxResults": max_results,
            "textFormat": "plainText",
        }
        if page_token:  # Add pageToken only if it's not None
            request_params["pageToken"] = page_token

        request = youtube.commentThreads().list(**request_params)
        response = request.execute()

        # Only return necessary data
        return {
            "items": response.get("items", []),
            "nextPageToken": response.get("nextPageToken"),
        }

    except HttpError as e:
        raise HTTPException(status_code=500, detail=f"An error occurred: {e}")


@app.get("/subs/videos/")
async def fetch_home_feed(
    max_results: int = 10,
    credentials=Depends(get_credentials),
):
    """
    Fetches the user's YouTube home feed.
    """
    try:
        feed = get_subscriptions_videos(credentials, max_results)
        return feed
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/collect/video")
async def get_video_details(
    video_id: str = Query(..., description="The ID of the YouTube video"),
    part: str = "snippet",
    credentials=Depends(get_credentials),
):
    """
    Fetch details of a YouTube video by video ID.
    """
    try:
        youtube = build("youtube", "v3", credentials=credentials)
        request = youtube.videos().list(part=part, id=video_id)
        response = request.execute()

        if not response["items"]:
            raise HTTPException(status_code=404, detail="Video not found")

        # video_data = response["items"][0]
        return response

    except HttpError as e:
        raise HTTPException(status_code=500, detail=f"An error occurred: {e}")
