from pydantic import BaseModel, HttpUrl
from typing import Optional, Dict


class VideoThumbnails(BaseModel):
    url: HttpUrl
    width: Optional[int] = None
    height: Optional[int] = None


class VideoSnippet(BaseModel):
    title: str
    description: str
    publishedAt: str
    channelId: str
    channelTitle: str
    thumbnails: Dict[str, VideoThumbnails]


class VideoStatistics(BaseModel):
    viewCount: int
    likeCount: Optional[int] = None
    dislikeCount: Optional[int] = None  # Set default to None
    commentCount: Optional[int] = None  # Set default to None


class VideoDetailsResponse(BaseModel):
    id: str
    snippet: VideoSnippet
    statistics: VideoStatistics
    # contentDetails: Dict[str, str]
