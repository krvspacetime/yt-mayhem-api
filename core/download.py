import asyncio
import logging

from typing import Optional, Callable
from yt_dlp import YoutubeDL

from sqlalchemy.orm import Session

from ..db.db import Download
from ..models.downloads import DownloadStatus


logging.basicConfig()
logging.getLogger("sqlalchemy.engine").setLevel(logging.INFO)


class DownloadTask:
    def __init__(
        self,
        video_id: str,
        video_title: str = None,
        db: Session = None,
        on_complete: Optional[Callable] = None,
    ):
        self.video_id = video_id
        self.video_title = video_title
        self.channel_title = None
        self.output_dir = "./tmp"
        self.downloaded_bytes = 0
        self.total_bytes = None
        self.elapsed_time = 0
        self.eta = None
        self.speed = 0
        self.status = DownloadStatus.QUEUED
        self.stage = "queued"  # New field to track the current stage
        self._cancel_event = asyncio.Event()
        self._task: Optional[asyncio.Task] = None
        self.on_complete = on_complete
        self.db = db
        self.download_record = None

    def progress_hook(self, d):
        if self._cancel_event.is_set():
            raise asyncio.CancelledError("Download cancelled by user.")

        if d["status"] == "downloading":
            self.downloaded_bytes = d["downloaded_bytes"]
            self.total_bytes = d.get("total_bytes", self.total_bytes)
            self.elapsed_time = d["elapsed"]
            self.eta = d["eta"]
            self.speed = d["speed"]

            # Update stage based on the fragment count or downloaded bytes
            if "fragments" in d:
                fragment_index = d.get("fragment_index", 0)
                fragment_count = d["fragments"]
                self.stage = f"downloading {'video' if 'video' in d['info_dict']['ext'] else 'audio'} (fragment {fragment_index}/{fragment_count})"
            elif self.stage != "merging":
                self.stage = f"downloading {'audio' if d['info_dict']['ext'] == 'm4a' else 'video'}"

            self.status = DownloadStatus.DOWNLOADING

            # Update the stage dynamically
            self.stage = (
                f"downloading {'audio' if d['info_dict']['ext'] == 'm4a' else 'video'}"
            )

        elif d["status"] == "finished":
            self.stage = "download complete"
            self.status = DownloadStatus.DOWNLOADING  # Still downloading if merging

        elif d["status"] == "error":
            self.status = DownloadStatus.ERROR

        print(
            f"Progress Update: {self.status}, {self.stage}, {self.downloaded_bytes}/{self.total_bytes}"
        )

    def postprocessor_hook(self, pp_info):
        if self._cancel_event.is_set():
            raise asyncio.CancelledError("Download cancelled by user.")

        # Update stage based on postprocessing info
        if pp_info["status"] == "started":
            self.stage = f"merging: {pp_info['postprocessor']}"
        elif pp_info["status"] == "finished":
            self.stage = "merge complete"
            self.status = DownloadStatus.MERGED

    def _create_db_record(self):
        """Actual database record creation logic (blocking)."""
        try:
            record = Download(
                video_id=self.video_id,
                title=self.video_title,
                output_dir=self.output_dir,
                status=self.status,
                downloaded_bytes=self.downloaded_bytes,
                total_bytes=self.total_bytes,
                stage=self.stage,
            )
            self.db.add(record)
            self.db.commit()
            logging.debug("Database record created successfully")
            return record
        except Exception as e:
            logging.error(f"Error creating database record: {e}")
            self.db.rollback()
            raise

    async def create_db_record(self):
        """Create the record in the database without blocking the event loop."""
        return await asyncio.to_thread(
            self._create_db_record
        )  # Run the blocking DB operation in a separate thread

    async def download(
        self,
        channel_title: str | None = None,
        quality: str | None = None,
        video_format_id: str | None = None,
        audio_format_id: str | None = None,
        output_filename: str = "output",
        output_format: str = "mp4",
        output_dir: str = "./tmp",
    ):
        if self.status == DownloadStatus.CANCELED:
            self.status = DownloadStatus.QUEUED

        self.output_dir = output_dir

        # Determine the format string
        if video_format_id and audio_format_id:
            format_str = f"{video_format_id}+{audio_format_id}"
        elif quality:
            format_str = quality
        else:
            raise ValueError("Either quality or explicit format IDs must be provided.")

        ydl_opts = {
            "quiet": True,
            "format": format_str,
            "outtmpl": f"{output_dir}/{output_filename} - {channel_title} - {self.video_id}.mp4",
            "progress_hooks": [self.progress_hook],
            "postprocessor_hooks": [self.postprocessor_hook],
            "merge_output_format": "mp4",
        }

        # Create the download record in the database
        self.download_record = (
            await self.create_db_record()
        )  # Ensuxre record is created

        asyncio.create_task(self.sync_to_db())

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
            self._task.cancel()
            self.status = DownloadStatus.CANCELED
            self._cancel_event.set()

    async def sync_to_db(self):
        try:
            while True:
                if self.status in {
                    DownloadStatus.ERROR,
                    DownloadStatus.CANCELED,
                    DownloadStatus.MERGED,
                }:
                    self.db.commit()
                    break
                logging.debug(
                    f"Syncing to DB: {self.status}, {self.downloaded_bytes}/{self.total_bytes}"
                )

                def update_db():
                    self.download_record.status = self.status
                    self.download_record.stage = self.stage
                    self.download_record.downloaded_bytes = self.downloaded_bytes

                await asyncio.to_thread(update_db)
                await asyncio.sleep(1)
        except Exception as e:
            logging.error(f"Error syncing to DB: {e}")
