import os
import google.generativeai as genai
import pprint

from dotenv import load_dotenv
from fastapi import APIRouter, Depends, Query
from fastapi.exceptions import HTTPException
from googleapiclient.errors import HttpError
from googleapiclient.discovery import build

from ..models.comments import AddCommentRequest, AICommentRequest
from ..dependencies.dependency import get_youtube, get_credentials

router = APIRouter(prefix="/comments", tags=["Comments"])

load_dotenv()

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")


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


@router.get("/ai")
async def generate_comment(request: AICommentRequest = Depends()):
    genai.configure(api_key=os.environ["GEMINI_API_KEY"])

    model = genai.GenerativeModel(model_name="gemini-1.5-flash")
    response = model.generate_content(
        f"Please improve this comment by making it more {request.category}: {request.comment_text}"
    )
    text_response = response.text.split("\n")

    # Clean and categorize comments
    categorized_comments = {}
    current_category = None
    for line in text_response:
        line = line.strip()  # Remove leading/trailing whitespace
        if line.startswith("**") and line.endswith("**"):  # Detect category headers
            current_category = line.strip("**")
            categorized_comments[current_category] = []
        elif line and current_category:  # Add comments to the current category
            categorized_comments[current_category].append(line)

    return {
        "message": "Comment generated successfully.",
        "comments": categorized_comments,
    }
