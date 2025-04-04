from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from fastapi.responses import RedirectResponse
from google_auth_oauthlib.flow import Flow
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google.auth.exceptions import RefreshError
import os
import json

router = APIRouter(prefix="/oauth2", tags=["Ouath2"])

# Path to your client_secrets.json file
CLIENT_SECRETS_DIR = "creds"
CLIENT_SECRETS_FILENAME = "client_secrets.json"
CLIENT_SECRETS_FULL_PATH = os.path.join(CLIENT_SECRETS_DIR, CLIENT_SECRETS_FILENAME)
# This scope allows reading your YouTube subscriptions
SCOPES = [
    "https://www.googleapis.com/auth/youtube",
    "https://www.googleapis.com/auth/youtube.readonly",
    "https://www.googleapis.com/auth/youtube.force-ssl",
]
TOKEN_DIR = "creds"
TOKEN_FILE = "token.json"
TOKEN_FULL_PATH = os.path.join(TOKEN_DIR, TOKEN_FILE)
REDIRECT_URI = "http://localhost:8000/oauth2/oauth2callback"


def initiate_flow():
    if not os.path.exists(CLIENT_SECRETS_FULL_PATH):
        raise FileNotFoundError(
            "Cannot initiate flow. Client secrets file not found. Please upload the credentials file first."
        )
    flow = Flow.from_client_secrets_file(
        CLIENT_SECRETS_FULL_PATH,
        scopes=SCOPES,
        redirect_uri=REDIRECT_URI,
    )
    return flow


def authenticate_youtube():
    try:
        if os.path.exists(TOKEN_FULL_PATH):
            with open(TOKEN_FULL_PATH, "r") as token_file:
                credentials_data = json.load(token_file)
                credentials = Credentials.from_authorized_user_info(
                    credentials_data, SCOPES
                )
        if credentials and credentials.expired and credentials.refresh_token:
            credentials.refresh(Request())
            # Save the refreshed credentials
            with open(TOKEN_FULL_PATH, "w") as token_file:
                token_file.write(credentials.to_json())
        return credentials
    except RefreshError as e:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/authorize")
def authorize():
    try:
        flow = initiate_flow()
        authorization_url, _ = flow.authorization_url(prompt="consent")
        return RedirectResponse(authorization_url)
    except FileNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/oauth2callback")
def oauth2callback(code: str):
    flow = initiate_flow()
    flow.fetch_token(code=code)
    credentials = flow.credentials

    # Save credentials to a token file (or database for multi-user support)
    with open(TOKEN_FULL_PATH, "w") as token_file:
        token_file.write(credentials.to_json())

    # Redirect back to your React app
    return RedirectResponse(url="http://localhost:5173")  # Adjust the port if needed


@router.get("/check")
async def check_creds(credentials=Depends(authenticate_youtube)):
    has_secret = os.path.exists(CLIENT_SECRETS_FULL_PATH)
    try:
        if credentials and has_secret:
            return {
                "valid": True,
                "token": credentials.token,
                "refresh_token": credentials.refresh_token,
                "token_uri": credentials.token_uri,
                "client_id": credentials.client_id,
                "scopes": credentials.scopes,
            }
        elif not has_secret:
            return {"valid": False, "reason": "No client secrets found."}
        else:
            return {"valid": False, "reason": "No valid credentials found."}
    except RefreshError as e:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/")
async def upload_creds(file: UploadFile = File(...)):
    contents = await file.read()
    try:
        with open(CLIENT_SECRETS_FULL_PATH, "wb") as f:
            f.write(contents)
            return {"filename": file.filename, "message": "Credentials created."}
    except IOError as e:
        raise HTTPException(status_code=500, detail=f"Error writing file: {str(e)}")
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Error reading file: {str(e)}")
