from fastapi import APIRouter, HTTPException, BackgroundTasks
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from typing import List, Dict, Any, Generator
import asyncio
import json
import time
from yt_dlp import YoutubeDL

# Replace these with the imports and definitions of your custom classes and enums
from ..core.download import (
    DownloadRequest,
    DownloadTask,
    DownloadStatus,
)  # Example import

# Router definition
router = APIRouter(prefix="/downloads", tags=["Downloads"])

# In-memory tasks and cache
download_tasks: Dict[str, DownloadTask] = {}
video_formats_cache: Dict[str, Dict[str, Any]] = {}
cache_expiration_time = 60 * 30  # Cache expiration time in seconds
# semaphore = asyncio.Semaphore(5)  # Limit to 5 concurrent extractions


@router.post("/download/")
async def initiate_download(
    request: DownloadRequest, background_tasks: BackgroundTasks
):
    def cleanup_task(video_id: str):
        # Remove the task from download_tasks once it's complete or canceled
        download_tasks.pop(video_id, None)

    for video_id in request.video_ids:
        # Create and store a DownloadTask for each video with the cleanup callback
        task = DownloadTask(video_id, on_complete=cleanup_task)
        download_tasks[video_id] = task
        # Schedule the background download task
        background_tasks.add_task(
            task.download, request.quality, request.save_folder, request.video_title
        )

    return {"message": "Download started", "video_ids": request.video_ids}


@router.get("/progress/{video_id}")
async def stream_progress(video_id: str) -> StreamingResponse:
    """Streams download progress data via SSE."""
    if video_id not in download_tasks:
        raise HTTPException(
            status_code=404, detail=f"Download with id: '{video_id}' not found"
        )

    task = download_tasks[video_id]

    async def event_generator() -> Generator[str, None, None]:
        while task.status not in {DownloadStatus.COMPLETE, DownloadStatus.CANCELED}:
            progress_data = {
                "video_id": task.video_id,
                "downloaded_bytes": task.downloaded_bytes,
                "total_bytes": task.total_bytes,
                "status": task.status.value,
            }
            yield f"data: {json.dumps(progress_data)}\n\n"
            await asyncio.sleep(1)

        # Final update after download is complete
        progress_data = {
            "video_id": task.video_id,
            "downloaded_bytes": task.downloaded_bytes,
            "total_bytes": task.total_bytes,
            "status": task.status.value,
        }
        yield f"data: {json.dumps(progress_data)}\n\n"

    return StreamingResponse(event_generator(), media_type="text/event-stream")


class CancelParams(BaseModel):
    video_ids: List[str]


@router.post("/cancel_downloads/")
async def cancel_downloads(params: CancelParams):
    for video_id in params.video_ids:
        if video_id in download_tasks:
            download_tasks[video_id].cancel()
            # Immediately remove from download_tasks after cancellation
            download_tasks.pop(video_id, None)
    return {
        "message": "Cancellation requested for specified downloads",
        "video_ids": params.video_ids,
    }


async def fetch_video_formats(video_id: str):
    """Fetch video formats with yt-dlp for a given video ID."""
    ydl_opts = {
        "skip_download": True,
        "quiet": False,
        "verbose": True,
    }
    # async with semaphore:  # Limit concurrency
    try:
        with YoutubeDL(ydl_opts) as ydl:
            info = await asyncio.to_thread(
                ydl.extract_info,
                f"https://www.youtube.com/watch?v={video_id}",
            )
            formats = [
                {
                    "format_id": f["format_id"],
                    "ext": f["ext"],
                    "resolution": f.get("resolution"),
                    "vcodec": f.get("vcodec"),
                    "acodec": f.get("acodec"),
                    "filesize": f.get("filesize"),
                    "fps": f.get("fps"),
                    "type": (
                        "video+audio"
                        if f.get("vcodec") != "none" and f.get("acodec") != "none"
                        else (
                            "video-only" if f.get("vcodec") != "none" else "audio-only"
                        )
                    ),
                }
                for f in info.get("formats", [])
            ]

            return {
                "video_id": video_id,
                "title": info.get("title"),
                "formats": formats,
            }
    except Exception as e:
        print(f"Error fetching video formats for {video_id}: {e}")
        raise HTTPException(
            status_code=500,
            detail="An unexpected error occurred while fetching formats.",
        )


async def get_video_formats(video_id: str):
    """Get video formats from cache or fetch them if not cached."""
    current_time = time.time()

    # Check cache first
    if video_id in video_formats_cache:
        cache_entry = video_formats_cache[video_id]
        if current_time - cache_entry["timestamp"] < cache_expiration_time:
            return cache_entry["data"]

    # Fetch data if not in cache or expired
    data = await fetch_video_formats(video_id)
    video_formats_cache[video_id] = {"data": data, "timestamp": current_time}
    return data


@router.get("/formats/{video_id}")
async def get_formats(video_id: str):
    return await get_video_formats(video_id)
