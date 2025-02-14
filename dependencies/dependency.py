import os
import re
from fastapi.exceptions import HTTPException
from dotenv import load_dotenv
from fastapi import Query
from googleapiclient.discovery import build

from routers.ouauth2 import authenticate_youtube

load_dotenv()
YOUTUBE_API_KEY = os.getenv("YOUTUBE_API_KEY")


async def get_credentials():
    # Dependency to inject credentials
    credentials = authenticate_youtube()
    return credentials


async def get_youtube():
    return build("youtube", "v3", developerKey=YOUTUBE_API_KEY)


# Regular expressions for video ID and YouTube URL
YOUTUBE_VIDEO_ID_REGEX = r"^[a-zA-Z0-9_-]{11}$"
YOUTUBE_URL_REGEX = (
    r"^(https?:\/\/)?(www\.)?(youtube\.com|youtu\.be)\/(watch\?v=)?[a-zA-Z0-9_-]{11}$"
)


def validate_video_id(
    video_id: str = Query(..., description="List of video IDs or URLs"),
) -> str:
    """Validates a list of YouTube video IDs or URLs."""
    validated_id = None
    if re.match(YOUTUBE_VIDEO_ID_REGEX, video_id):
        validated_id = video_id  # Valid video ID
    elif re.match(YOUTUBE_URL_REGEX, video_id):
        # Extract video ID from URL if it's a valid YouTube URL
        video_id_match = re.search(r"[a-zA-Z0-9_-]{11}$", video_id)
        if video_id_match:
            validated_id = video_id_match.group(0)
        else:
            raise HTTPException(
                status_code=400, detail=f"Invalid YouTube URL format: {video_id}"
            )
    else:
        raise HTTPException(
            status_code=400, detail=f"Invalid video ID or URL: {video_id}"
        )
    return validated_id
