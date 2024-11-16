from pydantic import BaseModel
from typing import Literal, List


class PlaylistCreateRequest(BaseModel):
    title: str
    description: str
    privacyStatus: Literal["public", "private", "unlisted"] = (
        "private"  # Options: "public", "private", or "unlisted"
    )


class PlaylistAddVideosRequest(BaseModel):
    playlist_id: str
    video_ids: str | List[str]  # List of video IDs to add
