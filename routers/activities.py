import logging
from fastapi import APIRouter, Depends, HTTPException
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from pydantic import BaseModel
from typing import List, Optional

from dependencies.dependency import get_credentials

router = APIRouter(prefix="/activities", tags=["Activities"])

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class NotificationItem(BaseModel):
    title: str
    description: Optional[str] = None
    link: str


class NotificationsResponse(BaseModel):
    notifications: List[NotificationItem]


def fetch_youtube_notifications(credentials) -> List[NotificationItem]:
    """
    Fetches the user's YouTube notifications using the YouTube Data API v3.
    """
    try:
        service = build("youtube", "v3", credentials=credentials)

        # Assuming notifications can be fetched from "activities" endpoint
        request = service.activities().list(
            part="snippet",
            mine=True,
            maxResults=10,  # Adjust as needed
        )
        response = request.execute()

        notifications = []
        for item in response.get("items", []):
            snippet = item.get("snippet", {})
            title = snippet.get("title", "No Title")
            description = snippet.get("description", "")
            link = f"https://www.youtube.com/watch?v={snippet.get('resourceId', {}).get('videoId', '')}"

            notifications.append(
                NotificationItem(title=title, description=description, link=link)
            )

        return notifications

    except HttpError as e:
        logger.error(f"YouTube API error: {e}")
        raise HTTPException(status_code=e.resp.status, detail=f"YouTube API error: {e}")

    except Exception as e:
        logger.exception("Unexpected error fetching YouTube notifications")
        raise HTTPException(status_code=500, detail="Internal Server Error")


@router.get("/notifications", response_model=NotificationsResponse)
async def get_notifications(credentials=Depends(get_credentials)):
    """
    FastAPI endpoint to get user's YouTube notifications.
    """
    notifications = fetch_youtube_notifications(credentials)
    return {"notifications": notifications}
