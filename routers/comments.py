from fastapi import APIRouter, Depends, Query
from fastapi.exceptions import HTTPException
from googleapiclient.errors import HttpError

from ..dependencies.dependency import get_youtube

router = APIRouter(prefix="/comments", tags=["Comments"])


@router.get("/")
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
