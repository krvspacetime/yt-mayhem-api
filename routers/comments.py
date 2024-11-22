from typing import Annotated
from fastapi import APIRouter, Depends, Query
from fastapi.exceptions import HTTPException
from googleapiclient.errors import HttpError
from googleapiclient.discovery import build

from ..models.comments import AddCommentRequest
from ..dependencies.dependency import get_youtube, get_credentials

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


@router.post("/add")
async def add_comment(
    request: AddCommentRequest,
    credentials=Depends(get_credentials),
):
    try:
        # Define the body for the commentThreads.insert method
        body = {
            "snippet": {
                "videoId": request.video_id,
                "topLevelComment": {
                    "snippet": {
                        "textOriginal": request.comment_text,
                    }
                },
            }
        }

        # Build the YouTube API client
        youtube = build("youtube", "v3", credentials=credentials)

        # Call the YouTube API to insert the comment
        response = youtube.commentThreads().insert(part="snippet", body=body).execute()

        return {
            "message": "Comment added successfully.",
            "comment_id": response["id"],
            "comment_details": response["snippet"]["topLevelComment"]["snippet"],
        }

    except HttpError as e:
        raise HTTPException(
            status_code=e.resp.status,
            detail=f"Failed to add comment: {e.error_details}",
        )
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"An unexpected error occurred: {str(e)}"
        )
