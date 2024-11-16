from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

from fastapi import APIRouter, HTTPException, Depends

from ..models.channels import ChannelInfoRequest
from ..dependencies.dependency import get_credentials

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
        channel_data = response["items"][0]
        return {
            "id": channel_data["id"],
            "title": channel_data["snippet"]["title"],
            "description": channel_data["snippet"]["description"],
            "custom_url": channel_data["snippet"].get("customUrl"),
            "published_at": channel_data["snippet"]["publishedAt"],
            "country": channel_data["snippet"].get("country"),
            "statistics": channel_data["statistics"],
            "thumbnails": channel_data["snippet"]["thumbnails"],
        }
    except HttpError as e:
        raise HTTPException(status_code=500, detail=f"Error fetching data: {str(e)}")
