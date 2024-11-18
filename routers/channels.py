from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

from fastapi import APIRouter, HTTPException, Depends

from ..dependencies.dependency import get_credentials
from ..models.channels import ChannelSearchParams

router = APIRouter(prefix="/channels", tags=["Channels"])


@router.get("/")
async def get_channel_info(channel_id: str, credentials=Depends(get_credentials)):
    youtube = build("youtube", "v3", credentials=credentials)
    try:
        response = (
            youtube.channels().list(part="snippet,statistics", id=channel_id).execute()
        )
        if not response.get("items"):
            raise HTTPException(status_code=404, detail="Channel not found.")

        return response
    except HttpError as e:
        raise HTTPException(status_code=500, detail=f"Error fetching data: {str(e)}")


@router.get("/videos")
async def get_channel_sections(
    request: ChannelSearchParams = Depends(), credentials=Depends(get_credentials)
):
    youtube = build("youtube", "v3", credentials=credentials)
    try:
        response = (
            youtube.search()
            .list(
                part=request.part,
                channelId=request.channel_id,
                maxResults=request.max_results,
                pageToken=request.page_token,  # If provided, fetch the next page
                order=request.order,  # Order videos by date (most recent first)
                type=request.videoType,  # Filter results to include only videos
            )
            .execute()
        )
        if not response.get("items"):
            raise HTTPException(status_code=404, detail="Channel not found.")

        return response
    except HttpError as e:
        raise HTTPException(status_code=500, detail=f"Error fetching data: {str(e)}")
