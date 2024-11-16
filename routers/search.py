from fastapi import APIRouter, Depends
from ..models.search import YouTubeSearchParams
from ..dependencies.dependency import get_youtube

router = APIRouter(prefix="/search", tags=["Search"])


@router.get("/")
def youtube_search(
    params: YouTubeSearchParams = Depends(), youtube=Depends(get_youtube)
):
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
