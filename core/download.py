from pydantic import BaseModel
from typing import List, Optional, Callable
import asyncio
from yt_dlp import YoutubeDL

from enum import Enum


class DownloadStatus(Enum):
    QUEUED = "queued"
    DOWNLOADING = "downloading"
    COMPLETE = "complete!"
    CANCELED = "canceled"
    ERROR = "error"


# Define the request model for download parameters
class DownloadRequest(BaseModel):
    video_ids: List[str]
    video_title: str
    quality: str
    save_folder: str


class DownloadTask:
    def __init__(self, video_id: str, on_complete: Optional[Callable] = None):
        self.video_id = video_id
        self.video_title = None
        self.downloaded_bytes = 0
        self.total_bytes = None
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
            self.status = DownloadStatus.DOWNLOADING
        elif d["status"] == "finished":
            self.status = DownloadStatus.COMPLETE
        elif d["status"] == "error":
            self.status = DownloadStatus.ERROR

    async def download(self, quality: str, save_folder: str, title):
        if self.status == DownloadStatus.CANCELED:
            # Reset the task status before starting a new download
            self.status = DownloadStatus.QUEUED

        ydl_opts = {
            "format": quality,
            "outtmpl": f"{save_folder}/{title} - {self.video_id}.mp4",
            "progress_hooks": [self.progress_hook],
            "merge_output_format": "mp4",
        }

        # Create a new task to run the download
        self._task = asyncio.create_task(self._run_download(ydl_opts))

        try:
            await self._task  # Wait for the download to complete or be cancelled
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
