from dotenv import load_dotenv
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from routers import (
    downloads,
    search,
    channels,
    ouauth2,
    playlists,
    comments,
    history,
    home,
    videos,
)

app = FastAPI()
app.include_router(downloads.router)
app.include_router(search.router)
app.include_router(channels.router)
app.include_router(ouauth2.router)
app.include_router(playlists.router)
app.include_router(comments.router)
app.include_router(history.router)
app.include_router(home.router)
app.include_router(videos.router)

load_dotenv()

origins = [
    "http://localhost.tiangolo.com",
    "https://localhost.tiangolo.com",
    "http://localhost",
    "http://localhost:5173",
    "http://localhost:5174/",
    "http://localhost:5175/",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def log_requests(request: Request, call_next):
    body = await request.body()
    print("Incoming request body:", body.decode("utf-8"))
    response = await call_next(request)
    return response
