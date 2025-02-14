import os
import asyncio
import json
import time
import subprocess

from pathlib import Path
from fastapi import APIRouter, HTTPException, BackgroundTasks, Query, Depends
from fastapi.responses import StreamingResponse
from typing import Dict, Any, AsyncGenerator, Optional
from yt_dlp import YoutubeDL
from sqlalchemy.orm import Session

from ..db.db import Download

# Replace these with the imports and definitions of your custom classes and enums
from ..core.download import (
    DownloadTask,
    DownloadStatus,
)  # Example import

from ..dependencies.dependency import validate_video_id
from ..models.downloads import DownloadRequest, CancelParams
from ..db.db import get_db

# Router definition
router = APIRouter(prefix="/downloads", tags=["Downloads"])

# In-memory tasks and cache
download_tasks: Dict[str, DownloadTask] = {}
video_formats_cache: Dict[str, Dict[str, Any]] = {}
cache_expiration_time = 60 * 30  # Cache expiration time in seconds
# semaphore = asyncio.Semaphore(5)  # Limit to 5 concurrent extractions


@router.get("/download/")
async def initiate_download(
    background_tasks: BackgroundTasks,
    video_id: str = Depends(validate_video_id),
    channel_title: str = Query(None, description="Channel title"),
    quality: str = Query(None, description="Video quality"),
    video_format_id: str = Query(..., description="Format ID for video"),
    audio_format_id: str = Query(..., description="Format ID for audio"),
    output_filename: str = Query(..., description="Output filename"),
    output_format: Optional[str] = Query("mp4", description="Output file format"),
    output_dir: str = Query("./tmp", description="Output directory"),
    db: Session = Depends(get_db),
):
    def cleanup_task(video_id: str):
        # Remove the task from download_tasks once it's complete or canceled
        download_tasks.pop(video_id, None)

    # Check for existing downloads with the same video_id
    existing_download = db.query(Download).filter_by(video_id=video_id).first()

    # If an existing download is cancelled or errored, delete it
    if existing_download:
        try:
            db.delete(existing_download)
            db.commit()
        except Exception as e:
            db.rollback()
            raise HTTPException(
                status_code=500, detail=f"Error removing existing download: {str(e)}"
            )

    # Create and store a DownloadTask for each video with the cleanup callback
    task = DownloadTask(
        video_id=video_id,
        video_title=output_filename,
        on_complete=cleanup_task,
        db=db,
    )

    # task = DownloadTask(video_id, on_complete=cleanup_task, db=db)
    download_tasks[video_id] = task
    # Schedule the background download task
    background_tasks.add_task(
        task.download,
        channel_title,
        quality,
        video_format_id,
        audio_format_id,
        output_filename,
        output_format,
    )

    return {"message": "Download started", "video_ids": video_id}


@router.get("/progress/{video_id}")
async def stream_progress(video_id: str) -> StreamingResponse:
    """Streams download progress data via SSE."""
    if video_id not in download_tasks:
        raise HTTPException(
            status_code=404, detail=f"Download with id: '{video_id}' not found"
        )

    task = download_tasks[video_id]

    async def event_generator() -> AsyncGenerator[str, None]:
        while task.status not in {DownloadStatus.COMPLETE, DownloadStatus.CANCELED}:
            progress_data = {
                "video_id": task.video_id,
                "downloaded_bytes": task.downloaded_bytes,
                "total_bytes": task.total_bytes,
                "status": task.status.value,
                "progress": (
                    task.downloaded_bytes / task.total_bytes * 100
                    if task.total_bytes
                    else 0
                ),
                "eta": task.eta if task.eta else 0,
                "elapsed": task.elapsed_time if task.elapsed_time else 0,
                "speed": task.speed if task.speed else 0,
                "stage": task.stage,  # Include stage information
            }
            yield f"data: {json.dumps(progress_data)}\n\n"
            await asyncio.sleep(1)  # Try to stress test this and increase if needed

        # Final update after download is complete
        progress_data = {
            "video_id": task.video_id,
            "downloaded_bytes": task.downloaded_bytes,
            "total_bytes": task.total_bytes,
            "status": task.status.value,
            "stage": task.stage,
        }
        yield f"data: {json.dumps(progress_data)}\n\n"

    return StreamingResponse(event_generator(), media_type="text/event-stream")


@router.post("/cancel_downloads/")
async def cancel_downloads(params: CancelParams):
    for video_id in params.video_ids:
        if video_id in download_tasks:
            download_tasks[video_id].cancel()
            download_tasks[video_id].status = DownloadStatus.CANCELED
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
        # if current_time - cache_entry["timestamp"] < cache_expiration_time:
        return cache_entry["data"]

    # Fetch data if not in cache or expired
    data = await fetch_video_formats(video_id)
    video_formats_cache[video_id] = {"data": data, "timestamp": current_time}
    return data


@router.get("/formats/{video_id}")
async def get_formats(video_id: str):
    return await get_video_formats(video_id)


@router.post("/download/sub")
async def download_video(request: DownloadRequest):
    output_dir = Path("downloads")  # Directory to save the files
    output_dir.mkdir(exist_ok=True)  # Create the directory if it doesn't exist

    # Construct the full output path
    output_file = output_dir / f"{request.output_filename}.{request.output_format}"

    # yt-dlp command to download specified formats and combine
    cmd = [
        "yt-dlp",
        request.video_url,
        "-f",
        f"{request.video_format_id}+{request.audio_format_id}",  # Specify formats
        "--merge-output-format",
        request.output_format,  # Output format
        "-o",
        str(output_file),  # Output filename
    ]

    try:
        # Run the yt-dlp command
        subprocess.run(cmd, check=True, text=True, capture_output=True)
        return {
            "message": "Download and merge completed successfully.",
            "file_path": str(output_file),
        }
    except subprocess.CalledProcessError as e:
        raise HTTPException(
            status_code=500, detail=f"Error downloading video: {e.stderr}"
        )


@router.get("/open_folder/{video_id}")
async def open_folder(video_id: str):
    # Ensure the video ID exists in the task manager
    if video_id not in download_tasks:
        raise HTTPException(
            status_code=404, detail=f"No download task found for video ID: {video_id}"
        )

    # Get the output directory from the task
    task = download_tasks[video_id]
    folder_path = task.output_dir
    print(f"Folder: {folder_path}")

    if not folder_path:
        raise HTTPException(
            status_code=400, detail="Output directory not set for this download task."
        )

    # Resolve absolute path
    absolute_path = os.path.abspath(folder_path)
    print(f"Abs path: {absolute_path}")
    # Verify folder exists
    if not os.path.isdir(absolute_path):
        raise HTTPException(
            status_code=404, detail=f"Folder does not exist: {absolute_path}"
        )

    # Open the folder using subprocess
    try:
        # Windows-specific command
        if os.name == "nt":
            subprocess.Popen(f'explorer "{absolute_path}"', shell=True)
        # macOS
        elif os.name == "posix" and "darwin" in os.uname().sysname.lower():
            subprocess.Popen(["open", absolute_path])
        # Linux
        else:
            subprocess.Popen(["xdg-open", absolute_path])

        return {"message": f"Folder '{absolute_path}' opened successfully."}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to open folder: {str(e)}")


@router.get("/history")
async def get_download_status(
    video_id: str | None = Query(None),
    status: DownloadStatus | None = Query("DOWNLOADING"),
    video_title: str | None = Query(None),
    stage: str | None = Query(None),
    quality: str | None = Query(None),
    db: Session = Depends(get_db),
):
    if video_id:
        download = db.query(Download).filter(Download.video_id == video_id).first()
        return download
    elif status:
        downloads = db.query(Download).filter(Download.status == status).all()
        return downloads
    elif video_title:
        # Use case-insensitive substring matching
        downloads = (
            db.query(Download).filter(Download.title.ilike(f"%{video_title}%")).all()
        )
        return downloads
    elif stage:
        downloads = db.query(Download).filter(Download.stage == stage).all()
        return downloads
    elif quality:
        downloads = db.query(Download).filter(Download.quality == quality).all()
        return downloads
    else:
        downloads = db.query(Download).all()
        return downloads


@router.delete("/history")
def delete_download_history(video_id: str, db: Session = Depends(get_db)):
    try:
        db.query(Download).filter(Download.video_id == video_id).delete()
        db.commit()
        return {
            "message": "OK",
            "video_id": video_id,
            "data": f"Successfully deleted video with id {video_id}",
        }
    except Exception as e:
        raise HTTPException(f"Error occured when deleting file. {e}")
