from googleapiclient.discovery import build
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from models.search import YouTubeSearchParams
from dependencies.dependency import get_credentials
from db.db import get_db, create_search_record
from schemas.schemas import SearchRecord
from models.search import SearchRecordAddRequest

router = APIRouter(prefix="/search", tags=["Search"])


@router.get("/")
async def youtube_search(
    params: YouTubeSearchParams = Depends(),
    credentials=Depends(get_credentials),
):
    youtube = build("youtube", "v3", credentials=credentials)
    request = youtube.search().list(
        part="snippet",
        q=params.query,
        type="video",
        maxResults=params.max_results,
        pageToken=params.page_token,  # If provided, fetch the next page
        safeSearch=params.safeSearch,
        videoDefinition=params.videoDefinition,
        videoDuration=params.videoDuration,
        videoType=params.videoType,
        order=params.order,
        publishedAfter=(
            params.publishedAfter.isoformat() if params.publishedAfter else None
        ),
        publishedBefore=(
            params.publishedBefore.isoformat() if params.publishedBefore else None
        ),
    )

    response = request.execute()

    # Return the results including the nextPageToken for pagination
    return {
        "results": response.get("items", []),
        "nextPageToken": response.get("nextPageToken"),
        "totalResults": response["pageInfo"]["totalResults"],
        "resultsPerPage": response["pageInfo"]["resultsPerPage"],
    }


@router.post("/add")
def add_search_record(request: SearchRecordAddRequest, db: Session = Depends(get_db)):
    try:
        new_record = create_search_record(db, SearchRecord(query=request.query))
        return {
            "message": "Search record added successfully",
            "record": new_record,
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.delete("/delete")
def delete_search_record(q: str, db: Session = Depends(get_db)):
    try:
        db.query(SearchRecord).filter(SearchRecord.query == q).delete()
        db.commit()
        return {"message": "Search record deleted successfully"}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
