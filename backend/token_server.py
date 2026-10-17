"""
Token server: the browser "Virtual Phone Dialer" (Vivek) calls this to get a
LiveKit access token before joining a room.

Run:  uvicorn token_server:app --port 8001 --reload
Test: http://localhost:8001/token?room=awaaz-demo&identity=caller1
"""
import os

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from livekit import api

load_dotenv()

app = FastAPI(title="Awaaz Setu Token Server")
app.add_middleware(CORSMiddleware, allow_origins=["*"],
                   allow_methods=["*"], allow_headers=["*"])


@app.get("/token")
def get_token(room: str = "awaaz-demo", identity: str = "caller"):
    token = (
        api.AccessToken(os.environ["LIVEKIT_API_KEY"], os.environ["LIVEKIT_API_SECRET"])
        .with_identity(identity)
        .with_grants(api.VideoGrants(room_join=True, room=room))
        .to_jwt()
    )
    return {"token": token, "url": os.environ["LIVEKIT_URL"], "room": room}
