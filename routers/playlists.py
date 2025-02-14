from typing import Annotated, Optional
from fastapi import Query, Depends, APIRouter
from fastapi.exceptions import HTTPException

from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

from ..core.tools import (
    get_playlist_items,
    add_playlist_videos,
    get_playlists,
)

from ..models.playlists import (
    PlaylistCreateRequest,
    PlaylistAddVideosRequest,
    SortOrder,
)

from ..dependencies.dependency import get_credentials


router = APIRouter(prefix="/playlists", tags=["Playlists"])


@router.get("/mine")
async def collect_playlists_mine(
    max_results=Annotated[int, Query(50, ge=1, le=100)],
    credentials=Depends(get_credentials),
):
    try:
        youtube = build("youtube", "v3", credentials=credentials)

        # Check if the user has a channel
        channel_request = youtube.channels().list(part="id", mine=True)
        channel_response = channel_request.execute()
        if not channel_response.get("items"):
            raise HTTPException(
                status_code=404, detail="User does not have a YouTube channel."
            )

        # Fetch playlists
        playlist_request = youtube.playlists().list(
            part="snippet", mine=True, maxResults=max_results
        )
        playlist_response = playlist_request.execute()
        return {"playlists": playlist_response["items"]}

    except HttpError as e:
        raise HTTPException(status_code=500, detail=f"API error: {e}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Unexpected error: {e}")


@router.get("/")
async def collect_playlists(
    channel_id: str,
    max_results: int = Query(50, ge=1, le=100),
    credentials=Depends(get_credentials),
    page_token: Optional[str] = None,
):
    try:
        playlists = get_playlists(credentials, channel_id, max_results, page_token)
        return playlists
    except HttpError as e:
        raise HTTPException(status_code=500, detail=f"An error occurred: {e}")


@router.post("/add/")
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


@router.post("/videos/add/")
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


@router.get("/items/")
async def get_playlist_videos(
    playlist_id: str = "PLX7CQOTnV_M35rbnhHyMHLrUXQlG71zef",
    max_results: int = Query(500, ge=1, le=1000),
    sort_order: SortOrder = Query(SortOrder.OLDEST),
    credentials=Depends(get_credentials),
):
    try:
        videos = get_playlist_items(credentials, playlist_id, max_results, sort_order)
        return videos
    except HttpError as e:
        raise HTTPException(status_code=500, detail=f"An error occurred: {e}")
