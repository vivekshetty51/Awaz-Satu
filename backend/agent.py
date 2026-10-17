"""
Awaaz Setu - LiveKit voice agent worker (Backend & WebRTC).

Joins a LiveKit room, subscribes to the caller's audio, logs every
connection-state change and can push DPI results to the browser UI
over a LiveKit data channel (topic: "dpi_result").

Run locally:  python agent.py dev
"""
import asyncio
import json
import logging
import os

from dotenv import load_dotenv
from livekit import rtc
from livekit.agents import AutoSubscribe, JobContext, WorkerOptions, cli

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
)
logger = logging.getLogger("awaaz-setu")

DPI_TOPIC = "dpi_result"


def check_env() -> None:
    missing = [k for k in ("LIVEKIT_URL", "LIVEKIT_API_KEY", "LIVEKIT_API_SECRET")
               if not os.getenv(k)]
    if missing:
        raise RuntimeError(f"Missing env vars: {', '.join(missing)} (see .env.example)")


async def send_dpi_result(room: rtc.Room, service: str, details: str) -> None:
    """Push a DPI result to the frontend. Call this after the LLM tool returns."""
    payload = json.dumps({"service": service, "details": details}).encode("utf-8")
    await room.local_participant.publish_data(payload, reliable=True, topic=DPI_TOPIC)
    logger.info("Sent DPI result to UI: %s", service)


async def entrypoint(ctx: JobContext):
    room = ctx.room
    logger.info("Job received for room '%s'", room.name)

    @room.on("connection_state_changed")
    def on_state(state: rtc.ConnectionState):
        logger.info("Connection state -> %s", state)

    @room.on("participant_connected")
    def on_participant_connected(p: rtc.RemoteParticipant):
        logger.info("Caller joined: identity=%s", p.identity)

    @room.on("participant_disconnected")
    def on_participant_disconnected(p: rtc.RemoteParticipant):
        logger.info("Caller left: identity=%s", p.identity)

    @room.on("track_subscribed")
    def on_track_subscribed(track: rtc.Track, pub: rtc.RemoteTrackPublication,
                            p: rtc.RemoteParticipant):
        logger.info("Subscribed to %s track from %s", track.kind, p.identity)
        if track.kind == rtc.TrackKind.KIND_AUDIO:
            # TODO (speech/LLM teammates): feed this track into STT -> LLM -> TTS
            logger.info("Incoming caller audio is live")

    @room.on("track_unsubscribed")
    def on_track_unsubscribed(track: rtc.Track, pub: rtc.RemoteTrackPublication,
                              p: rtc.RemoteParticipant):
        logger.info("Track unsubscribed from %s", p.identity)

    @room.on("disconnected")
    def on_disconnected(*_):
        logger.info("Agent disconnected from room")

    await ctx.connect(auto_subscribe=AutoSubscribe.AUDIO_ONLY)
    logger.info("Agent connected to room '%s'", room.name)

    # DEMO PLACEHOLDER: lets the UI show an end-to-end result before the LLM +
    # mock DPI API are wired in. Replace with real send_dpi_result() calls.
    await ctx.wait_for_participant()
    await asyncio.sleep(3)
    await send_dpi_result(
        room,
        "e-NAM Mandi Prices (demo)",
        "Tomato prices in Yeshwanthpur Mandi: Rs 2,400 per Quintal. Trend: Steady.",
    )


if __name__ == "__main__":
    check_env()
    cli.run_app(WorkerOptions(entrypoint_fnc=entrypoint))
