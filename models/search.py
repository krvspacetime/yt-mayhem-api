from pydantic import BaseModel, Field
from datetime import datetime
from typing import Literal


class YouTubeSearchParams(BaseModel):
    query: str
    max_results: int = Field(15, ge=1, le=50)
    page_token: str | None = None
    safeSearch: Literal["none", "moderate", "strict"] = "none"
    videoDefinition: Literal["any", "high", "medium", "low"] = "any"
    videoDuration: Literal["any", "long", "medium", "short"] = "any"
    videoType: Literal["any", "episode", "movie"] = "any"
    order: Literal["relevance", "date", "rating", "viewCount"] = "relevance"
    publishedAfter: datetime | None = None
    publishedBefore: datetime | None = None
