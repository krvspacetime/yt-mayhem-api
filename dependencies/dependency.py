from ..core.tools import authenticate_youtube


async def get_credentials():
    # Dependency to inject credentials
    credentials = authenticate_youtube()
    return credentials
