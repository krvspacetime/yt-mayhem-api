import os
from dotenv import load_dotenv

from googleapiclient.discovery import build

from ..core.tools import authenticate_youtube

load_dotenv()
YOUTUBE_API_KEY = os.getenv("YOUTUBE_API_KEY")


async def get_credentials():
    # Dependency to inject credentials
    credentials = authenticate_youtube()
    return credentials


async def get_youtube():
    return build("youtube", "v3", developerKey=YOUTUBE_API_KEY)
