from dotenv import load_dotenv

from typing import Annotated
from fastapi import FastAPI, Query, Depends
from fastapi.exceptions import HTTPException
from fastapi.middleware.cors import CORSMiddleware
from .routers import downloads, search

from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

from .core.tools import (
    get_playlist,
    add_playlist_videos,
    get_subscriptions,
    get_subscriptions_videos,
)

from .models.playlists import PlaylistCreateRequest, PlaylistAddVideosRequest

from .dependencies.dependency import get_credentials, get_youtube

app = FastAPI()
app.include_router(downloads.router)
app.include_router(search.router)

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

# YOUTUBE_API_KEY = os.getenv("YOUTUBE_API_KEY")
# youtube = build("youtube", "v3", developerKey=YOUTUBE_API_KEY)


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


# Example of reusing credentials in another endpoint
@app.get("/collect/playlists/")
async def collect_playlists(
    credentials=Depends(get_credentials),
    max_results=Annotated[int, Query(50, ge=1, le=2000)],
):
    try:
        youtube = build("youtube", "v3", credentials=credentials)
        request = youtube.playlists().list(
            part="snippet", mine=True, maxResults=max_results
        )
        response = request.execute()
        return {"playlists": response["items"]}

    except HttpError as e:
        raise HTTPException(status_code=500, detail=f"An error occurred: {e}")


@app.get("/collect/playlist/{playlist_id}")
async def get_playlist_videos(
    playlist_id: str,
    max_results: int = Query(1000, ge=1, le=1000),
    credentials=Depends(get_credentials),
):
    try:
        playlist = get_playlist(credentials, playlist_id, max_results)
        return playlist
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


# Define a model to receive playlist details


@app.post("/playlists/")
async def add_playlist(
    playlist_request: PlaylistCreateRequest = Depends(),
    credentials=Depends(get_credentials),
):
    """
    Creates a new YouTube playlist with the specified title, description, and privacy status.
    """
    try:
        youtube = build("youtube", "v3", credentials=credentials)

        # Prepare the request body with a hardcoded privacy status for testing
        request_body = {
            "snippet": {
                "title": playlist_request.title,
                "description": playlist_request.description,
            },
            "status": {"privacyStatus": playlist_request.privacyStatus.strip().lower()},
        }

        print("Request Body:", request_body)  # Debugging line

        # Call the YouTube API to insert the playlist
        request = youtube.playlists().insert(part="snippet,status", body=request_body)
        response = request.execute()

        return {
            "message": "Playlist created successfully.",
            "playlist": {
                "id": response["id"],
                "title": response["snippet"]["title"],
                "description": response["snippet"]["description"],
                "privacyStatus": response["status"]["privacyStatus"],
            },
        }

    except HttpError as e:
        print(f"HttpError: {e}")  # Print error details for further inspection
        raise HTTPException(status_code=500, detail=f"An error occurred: {e}")


@app.post("/playlists/add/")
async def add_videos_to_playlist(
    videos_request: PlaylistAddVideosRequest,
    credentials=Depends(get_credentials),
):
    """
    Adds a list of videos to a specified YouTube playlist.

    Args:
        playlist_id (str): ID of the playlist to add videos to.
        videos_request (PlaylistAddVideosRequest): Contains the list of video IDs to add.
        credentials: OAuth 2.0 credentials for the authenticated user.

    Returns:
        dict: Summary of the added videos.
    """
    try:
        youtube = build("youtube", "v3", credentials=credentials)
        response = add_playlist_videos(youtube, videos_request)
        return response

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
    credentials=Depends(get_credentials),
):
    """
    Fetch details of a YouTube video by video ID.
    """
    try:
        youtube = build("youtube", "v3", credentials=credentials)
        request = youtube.videos().list(
            part="snippet,statistics, contentDetails", id=video_id
        )
        # request = youtube.videos().list(
        #     part="snippet,statistics,contentDetails", id=video_id
        # )
        response = request.execute()

        if not response["items"]:
            raise HTTPException(status_code=404, detail="Video not found")

        # video_data = response["items"][0]
        return response

    except HttpError as e:
        raise HTTPException(status_code=500, detail=f"An error occurred: {e}")
