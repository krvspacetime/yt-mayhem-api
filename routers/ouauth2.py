from fastapi import APIRouter
from fastapi.responses import RedirectResponse
from google_auth_oauthlib.flow import Flow
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
import os
import json

router = APIRouter(prefix="/oauth2", tags=["Ouath2"])

# Path to your client_secrets.json file
CLIENT_SECRETS_FILE = "./core/client_secrets_2.json"

# This scope allows reading your YouTube subscriptions
SCOPES = [
    "https://www.googleapis.com/auth/youtube",
    "https://www.googleapis.com/auth/youtube.readonly",
    "https://www.googleapis.com/auth/youtube.force-ssl",
]
TOKEN_FILE = "token.json"


def initiate_flow():
    flow = Flow.from_client_secrets_file(
        CLIENT_SECRETS_FILE,
        scopes=SCOPES,
        redirect_uri="http://localhost:8000/oauth2/oauth2callback",
    )
    return flow


@router.get("/authorize")
def authorize():
    flow = initiate_flow()
    authorization_url, _ = flow.authorization_url(prompt="consent")
    return RedirectResponse(authorization_url)


@router.get("/oauth2callback")
def oauth2callback(code: str):
    flow = initiate_flow()
    flow.fetch_token(code=code)
    credentials = flow.credentials

    # Save credentials to a token file (or database for multi-user support)
    with open(TOKEN_FILE, "w") as token_file:
        token_file.write(credentials.to_json())

    return {"message": "Authorization complete. You can now access the API."}


def authenticate_youtube():
    if os.path.exists(TOKEN_FILE):
        with open(TOKEN_FILE, "r") as token_file:
            credentials_data = json.load(token_file)
            credentials = Credentials.from_authorized_user_info(
                credentials_data, SCOPES
            )
    else:
        raise Exception("Credentials not found. Please authorize first.")

    if credentials and credentials.expired and credentials.refresh_token:
        credentials.refresh(Request())
        # Save the refreshed credentials
        with open(TOKEN_FILE, "w") as token_file:
            token_file.write(credentials.to_json())

    return credentials
