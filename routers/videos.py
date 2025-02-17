from googleapiclient.discovery import build
from fastapi import APIRouter, HTTPException, Query, Depends
from googleapiclient.http import HttpError

from dependencies.dependency import get_credentials


router = APIRouter(prefix="/videos", tags=["Video Details"])


@router.get("/")
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
