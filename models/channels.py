from pydantic import BaseModel, validator, Field
from typing import Dict, Literal
from datetime import datetime


class ChannelInfoRequest(BaseModel):
    channel_id: str

    @validator("channel_id")
    def validate_channel_id(cls, channel_id):
        if not channel_id.startswith("UC"):
            raise ValueError(
                "Invalid channel ID format. Channel IDs must start with 'UC'."
            )
        return channel_id


class ChannelInfoResponse(BaseModel):
    id: str
    title: str
    description: str
    custom_url: str | None
    published_at: str
    country: str | None
    statistics: Dict
    thumbnails: Dict


class ChannelSearchParams(BaseModel):
    channel_id: str
    part: str = "snippet"
    max_results: int = Field(15, ge=1, le=50)
    page_token: str | None = None
    videoDefinition: Literal["any", "high", "medium", "low"] = "any"
    videoDuration: Literal["any", "long", "medium", "short"] = "any"
    videoType: Literal["any", "episode", "movie"] = "any"
    order: Literal["relevance", "date", "rating", "viewCount"] = "date"
    publishedAfter: datetime | None = None
    publishedBefore: datetime | None = None
