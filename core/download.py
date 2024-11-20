import re
import asyncio

from typing import List, Optional, Callable
from fastapi import HTTPException, Query
from yt_dlp import YoutubeDL

from enum import Enum


class DownloadStatus(Enum):
    QUEUED = "queued"
    DOWNLOADING = "downloading"
    COMPLETE = "complete!"
    CANCELED = "canceled"
    ERROR = "error"


# Define the request model for download parameters
# class DownloadRequest(BaseModel):
#     video_ids: List[str]
#     video_title: str
#     quality: str
#     save_folder: str


class DownloadTask:
    def __init__(self, video_id: str, on_complete: Optional[Callable] = None):
        self.video_id = video_id
        self.video_title = None
        self.downloaded_bytes = 0
        self.total_bytes = None
        self.elapsed_time = 0
        self.eta = None
        self.speed = 0
        # self.fragment_index = None
        # self.fragment_count = None
        self.status = DownloadStatus.QUEUED
        self._cancel_event = asyncio.Event()
        self._task: Optional[asyncio.Task] = None  # To store the async task
        self.on_complete = on_complete  # Callback for cleanup

    def progress_hook(self, d):
        if self._cancel_event.is_set():
            raise asyncio.CancelledError("Download cancelled by user.")

        if d["status"] == "downloading":
            self.downloaded_bytes = d["downloaded_bytes"]
            self.total_bytes = d["total_bytes"]
            self.elapsed_time = d["elapsed"]
            self.eta = d["eta"]
            self.speed = d["speed"]
            # self.fragment_count = d["fragment_count"]
            # self.fragment_index = d["fragment_index"]
            self.status = DownloadStatus.DOWNLOADING
        elif d["status"] == "finished":
            self.status = DownloadStatus.COMPLETE
        elif d["status"] == "error":
            self.status = DownloadStatus.ERROR

    async def download(
        self,
        quality: str | None = None,
        video_format_id: str | None = None,
        audio_format_id: str | None = None,
        output_filename: str = "output",
        output_format: str = "mp4",
        output_dir: str = "./tmp",
    ):
        if self.status == DownloadStatus.CANCELED:
            self.status = DownloadStatus.QUEUED

        print("Downloading video:", self.video_id)
        print("Quality:", quality)
        print("Format IDs:", video_format_id, audio_format_id)
        # Determine the format string
        if video_format_id and audio_format_id:
            format_str = f"{video_format_id}+{audio_format_id}"
        elif quality:
            format_str = quality
        else:
            raise ValueError("Either quality or explicit format IDs must be provided.")

        ydl_opts = {
            "format": format_str,
            "outtmpl": f"{output_dir}/{output_filename} - {self.video_id}.mp4",
            "progress_hooks": [self.progress_hook],
            "merge_output_format": "mp4",
        }

        # Create a new task to run the download
        self._task = asyncio.create_task(self._run_download(ydl_opts))

        try:
            await self._task
        except asyncio.CancelledError:
            self.status = DownloadStatus.CANCELED
            self._cancel_event.set()

    async def _run_download(self, ydl_opts):
        with YoutubeDL(ydl_opts) as ydl:
            await asyncio.to_thread(
                ydl.download, [f"https://www.youtube.com/watch?v={self.video_id}"]
            )

    def cancel(self):
        """Cancels the download by setting the event and cancelling the task."""
        if self._task and not self._task.done():
            self._task.cancel()  # This will trigger asyncio.CancelledError
            self.status = DownloadStatus.CANCELED
            self._cancel_event.set()


# Regular expressions for video ID and YouTube URL
YOUTUBE_VIDEO_ID_REGEX = r"^[a-zA-Z0-9_-]{11}$"
YOUTUBE_URL_REGEX = (
    r"^(https?:\/\/)?(www\.)?(youtube\.com|youtu\.be)\/(watch\?v=)?[a-zA-Z0-9_-]{11}$"
)


def validate_video_id(
    video_ids: List[str] = Query(..., description="List of video IDs or URLs")
) -> List[str]:
    """Validates a list of YouTube video IDs or URLs."""
    validated_ids = []
    for video_id in video_ids:
        if re.match(YOUTUBE_VIDEO_ID_REGEX, video_id):
            validated_ids.append(video_id)  # Valid video ID
        elif re.match(YOUTUBE_URL_REGEX, video_id):
            # Extract video ID from URL if it's a valid YouTube URL
            video_id_match = re.search(r"[a-zA-Z0-9_-]{11}$", video_id)
            if video_id_match:
                validated_ids.append(video_id_match.group(0))
            else:
                raise HTTPException(
                    status_code=400, detail=f"Invalid YouTube URL format: {video_id}"
                )
        else:
            raise HTTPException(
                status_code=400, detail=f"Invalid video ID or URL: {video_id}"
            )
    return validated_ids
