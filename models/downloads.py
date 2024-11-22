from typing import List, Optional
from pydantic import BaseModel
from enum import Enum


class DownloadStatus(Enum):
    QUEUED = "queued"
    DOWNLOADING = "downloading"
    COMPLETE = "complete!"
    CANCELED = "canceled"
    ERROR = "error"
    MERGED = "merged"


# Currently not being used - replaced by Query
class DownloadRequest(BaseModel):
    video_ids: str
    video_title: str
    quality: Optional[str] = None  # For backward compatibility
    save_folder: str
    video_format_id: Optional[str] = None  # Explicit video format
    audio_format_id: Optional[str] = None  # Explicit audio format


class CancelParams(BaseModel):
    video_ids: List[str]


class DownloadCreate(BaseModel):
    video_id: str
    title: Optional[str]
    quality: Optional[str]
    output_dir: str


class DownloadRead(BaseModel):
    id: int
    video_id: str
    title: Optional[str]
    quality: Optional[str]
    output_dir: str
    status: DownloadStatus
    error_message: Optional[str]

    class Config:
        from_attributes = True
