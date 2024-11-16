from pydantic import BaseModel, Field, validator
from typing import Dict


class ChannelInfoRequest(BaseModel):
    channel_id: str = Field(..., example="UC_x5XG1OV2P6uZZ5FSM9Ttw")

    @validator("channel_id")
    def validate_channel_id(cls, value):
        if not value.startswith("UC"):
            raise ValueError(
                "Invalid channel ID format. Channel IDs must start with 'UC'."
            )
        return value


class ChannelInfoResponse(BaseModel):
    id: str
    title: str
    description: str
    custom_url: str | None
    published_at: str
    country: str | None
    statistics: Dict
    thumbnails: Dict
