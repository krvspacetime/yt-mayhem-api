import json
import asyncio
import os
import time
from datetime import datetime
from typing import List, Literal, Dict, Generator, Any
from dotenv import load_dotenv

from typing import Annotated
from fastapi import FastAPI, Query, Depends, BackgroundTasks
from fastapi.responses import StreamingResponse
from fastapi.exceptions import HTTPException
from fastapi.middleware.cors import CORSMiddleware
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from pydantic import BaseModel, Field
from yt_dlp import YoutubeDL

from .core.tools import (
    authenticate_youtube,
    get_playlist,
    add_playlist_videos,
    get_subscriptions,
    get_subscriptions_videos,
)

from .core.download import DownloadTask, DownloadRequest, DownloadStatus
from yt_dlp import YoutubeDL

app = FastAPI()
load_dotenv()
download_tasks: Dict[str, "DownloadTask"] = {}

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

YOUTUBE_API_KEY = os.getenv("YOUTUBE_API_KEY")
youtube = build("youtube", "v3", developerKey=YOUTUBE_API_KEY)


async def get_credentials():
    # Dependency to inject credentials
    credentials = authenticate_youtube()
    return credentials


class YouTubeSearchParams(BaseModel):
    query: str
    max_results: int = Field(15, ge=1, le=50)
    page_token: str | None = None
    safeSearch: Literal["none", "moderate", "strict"] = "none"
    videoDefinition: Literal["any", "high", "medium", "low"] = "any"
    videoDuration: Literal["any", "long", "medium", "short"] = "any"
    videoType: Literal["any", "episode", "movie"] = "any"
    order: Literal["relevance", "date", "rating", "viewCount"] = "relevance"
    publishedAfter: datetime | None = None
    publishedBefore: datetime | None = None


@app.get("/search")
def youtube_search(params: YouTubeSearchParams = Depends()):
    request = youtube.search().list(
        part="snippet",
        q=params.query,
        type="video",
        maxResults=params.max_results,
        pageToken=params.page_token,  # If provided, fetch the next page
        safeSearch=params.safeSearch,
        videoDefinition=params.videoDefinition,
        videoDuration=params.videoDuration,
        videoType=params.videoType,
        order=params.order,
        publishedAfter=(
            params.publishedAfter.isoformat() if params.publishedAfter else None
        ),
        publishedBefore=(
            params.publishedBefore.isoformat() if params.publishedBefore else None
        ),
    )

    response = request.execute()

    # Return the results including the nextPageToken for pagination
    return {
        "results": response.get("items", []),
        "nextPageToken": response.get("nextPageToken"),
        "totalResults": response["pageInfo"]["totalResults"],
        "resultsPerPage": response["pageInfo"]["resultsPerPage"],
    }


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
class PlaylistCreateRequest(BaseModel):
    title: str
    description: str
    privacyStatus: Literal["public", "private", "unlisted"] = (
        "private"  # Options: "public", "private", or "unlisted"
    )


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


class PlaylistAddVideosRequest(BaseModel):
    playlist_id: str
    video_ids: str | List[str]  # List of video IDs to add


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
    credentials=Depends(authenticate_youtube),
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
    credentials=Depends(authenticate_youtube),
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


# Initiate download for multiple videos in the background
@app.post("/download/")
async def initiate_download(
    request: DownloadRequest, background_tasks: BackgroundTasks
):
    def cleanup_task(video_id: str):
        # Remove the task from download_tasks once it's complete or canceled
        download_tasks.pop(video_id, None)

    for video_id in request.video_ids:
        # Create and store a DownloadTask for each video with the cleanup callback
        task = DownloadTask(video_id, on_complete=cleanup_task)
        download_tasks[video_id] = task
        # Schedule the background download task
        background_tasks.add_task(task.download, request.quality, request.save_folder)

    return {"message": "Download started", "video_ids": request.video_ids}


# Stream download progress for a specific video ID
@app.get("/progress/{video_id}")
async def stream_progress(video_id: str) -> StreamingResponse:
    """Streams download progress data via SSE."""
    if video_id not in download_tasks:
        raise HTTPException(
            status_code=404, detail=f"Download with id: '{video_id}' not found"
        )

    task = download_tasks[video_id]

    async def event_generator() -> Generator[str, None, None]:
        while task.status not in {DownloadStatus.COMPLETE, DownloadStatus.CANCELED}:
            progress_data = {
                "video_id": task.video_id,
                "downloaded_bytes": task.downloaded_bytes,
                "total_bytes": task.total_bytes,
                "status": task.status.value,  # Now `status` is an enum
            }
            yield f"data: {json.dumps(progress_data)}\n\n"
            await asyncio.sleep(1)

        # Final update after download is complete
        progress_data = {
            "video_id": task.video_id,
            "downloaded_bytes": task.downloaded_bytes,
            "total_bytes": task.total_bytes,
            "status": task.status.value,
        }
        yield f"data: {json.dumps(progress_data)}\n\n"

    return StreamingResponse(event_generator(), media_type="text/event-stream")


class CancelParams(BaseModel):
    video_ids: List[str]


# Cancel downloads for specified video IDs
@app.post("/cancel_downloads/")
async def cancel_downloads(params: CancelParams):
    for video_id in params.video_ids:
        if video_id in download_tasks:
            download_tasks[video_id].cancel()
            # Immediately remove from download_tasks after cancellation
            download_tasks.pop(video_id, None)
    return {
        "message": "Cancellation requested for specified downloads",
        "video_ids": params.video_ids,
    }


# Simple in-memory cache
video_formats_cache: Dict[str, Dict[str, Any]] = {}
cache_expiration_time = 300  # Cache expiration time in seconds (5 minutes)


async def fetch_video_formats(video_id: str):
    """Fetch video formats with yt-dlp for a given video ID."""
    ydl_opts = {
        "skip_download": True,
        # "format": "bestvideo+bestaudio/best",
        "merge_output_format": "mp4",
        "quiet": False,  # Disable quiet mode for detailed logs
        "verbose": True,  # Enable verbose output
        "postprocessors": [
            {
                "key": "FFmpegMerger",
            }
        ],
    }

    try:
        with YoutubeDL(ydl_opts) as ydl:
            info = await asyncio.to_thread(
                ydl.extract_info,
                f"https://www.youtube.com/watch?v={video_id}",
                # False,
            )

            # download_tasks[video_id].video_title = info.get(
            #     "title", f"Video {video_id}"
            # )
            # Process formats
            formats = [
                {
                    "format_id": f["format_id"],
                    "ext": f["ext"],
                    "resolution": f.get("resolution"),
                    "vcodec": f.get("vcodec"),
                    "acodec": f.get("acodec"),
                    "filesize": f.get("filesize"),
                    "fps": f.get("fps"),
                    "type": (
                        "video+audio"
                        if f.get("vcodec") != "none" and f.get("acodec") != "none"
                        else "video-only" if f.get("vcodec") != "none" else "audio-only"
                    ),
                }
                for f in info.get("formats", [])
            ]

            return {
                "video_id": video_id,
                "title": info.get("title"),
                "formats": formats,
            }
    except Exception as e:
        print(f"Error fetching video formats for {video_id}: {e}")
        raise HTTPException(
            status_code=500,
            detail="An unexpected error occurred while fetching formats.",
        )


async def get_video_formats(video_id: str):
    """Get video formats from cache or fetch them if not cached."""
    current_time = time.time()

    # Check cache first
    if video_id in video_formats_cache:
        cache_entry = video_formats_cache[video_id]
        if current_time - cache_entry["timestamp"] < cache_expiration_time:
            return cache_entry["data"]

    # Fetch data if not in cache or expired
    data = await fetch_video_formats(video_id)
    video_formats_cache[video_id] = {"data": data, "timestamp": current_time}
    return data


@app.get("/formats/{video_id}")
async def get_formats(video_id: str):
    return await get_video_formats(video_id)
