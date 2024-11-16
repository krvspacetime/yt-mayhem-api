import re
from pathlib import Path
from typing import List
from pydantic import BaseModel, validator


class DownloadRequest(BaseModel):
    video_ids: List[str]
    video_title: str
    quality: str
    save_folder: str

    @validator("video_ids", each_item=True)
    def validate_video_id(cls, video_id):
        try:
            # Regex for YouTube video ID (11 characters, alphanumeric + - and _)
            video_id_pattern = r"^[a-zA-Z0-9_-]{11}$"
            # Regex for YouTube video URL
            video_url_pattern = (
                r"^https://www\.youtube\.com/watch\?v=[a-zA-Z0-9_-]{11}$"
            )

            if re.match(video_id_pattern, video_id) or re.match(
                video_url_pattern, video_id
            ):
                return video_id
        except Exception as e:
            raise ValueError(f"Invalid video ID or URL: {video_id}. Error: {e}")

    @validator("save_folder")
    def validate_save_folder(cls, folder):
        try:
            path = Path(folder)
            # Check if the path is valid and can be resolved
            path.resolve(strict=False)
            # Optionally, check if the folder already exists
            if not path.exists():
                path.mkdir(parents=True, exist_ok=True)
            return folder
        except Exception as e:
            raise ValueError(f"Invalid folder path: {folder}. Error: {e}")
