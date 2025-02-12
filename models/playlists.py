from pydantic import BaseModel
from typing import Literal, List
from enum import Enum


class SortOrder(str, Enum):
    NEWEST = "newest"
    OLDEST = "oldest"


class PlaylistCreateRequest(BaseModel):
    title: str
    description: str
    privacyStatus: Literal["public", "private", "unlisted"] = (
        "private"  # Options: "public", "private", or "unlisted"
    )


class PlaylistAddVideosRequest(BaseModel):
    playlist_id: str
    video_ids: str | List[str]  # List of video IDs to add
