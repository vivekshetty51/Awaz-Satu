"""
Awaaz Setu - LiveKit Voice Agent with Voice Engine Integration.

Features:
- Connects to LiveKit rooms.
- Receives caller audio.
- Detects speech and collects audio clips.
- Sends audio to the FastAPI voice engine.
- Receives AI-generated audio.
- Plays the response back to the caller.
- Preserves DPI result publishing.

Run:
    python agent.py dev
"""

import asyncio
import base64
import io
import json
import logging
import os
import wave

import av
import httpx
import numpy as np

from dotenv import load_dotenv
from scipy.signal import resample_poly

from livekit import rtc
from livekit.agents import AutoSubscribe, JobContext, WorkerOptions, cli


load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
)

logger = logging.getLogger("awaaz-setu")

DPI_TOPIC = "dpi_result"

# Voice engine URL
VOICE_ENGINE_URL = (
    "http://127.0.0.1:8002/process-voice-turn"
)

# Audio configuration
VOICE_SAMPLE_RATE = 16000
OUTPUT_SAMPLE_RATE = 24000

# Speech detection configuration
SILENCE_THRESHOLD = 500
SILENCE_DURATION_FRAMES = 30
MIN_SPEECH_FRAMES = 10
MAX_SPEECH_FRAMES = 750


# --------------------------------------------------
# Environment configuration
# --------------------------------------------------

def check_env() -> None:
    missing = [
        key
        for key in (
            "LIVEKIT_URL",
            "LIVEKIT_API_KEY",
            "LIVEKIT_API_SECRET",
        )
        if not os.getenv(key)
    ]

    if missing:
        raise RuntimeError(
            f"Missing environment variables: {', '.join(missing)}. "
            "Check backend/.env."
        )


# --------------------------------------------------
# DPI result publishing
# --------------------------------------------------

async def send_dpi_result(
    room: rtc.Room,
    service: str,
    details: str,
) -> None:
    """Send DPI results to the frontend over LiveKit."""

    payload = json.dumps(
        {
            "service": service,
            "details": details,
        }
    ).encode("utf-8")

    await room.local_participant.publish_data(
        payload,
        reliable=True,
        topic=DPI_TOPIC,
    )

    logger.info("Sent DPI result to UI: %s", service)


# --------------------------------------------------
# Audio conversion
# --------------------------------------------------

def audio_to_wav(audio_bytes: bytes) -> bytes:
    """
    Convert raw PCM audio bytes into a WAV file.

    The input must contain 16-bit, mono PCM audio
    sampled at 16 kHz.
    """

    wav_buffer = io.BytesIO()

    with wave.open(wav_buffer, "wb") as wav_file:
        wav_file.setnchannels(1)
        wav_file.setsampwidth(2)
        wav_file.setframerate(VOICE_SAMPLE_RATE)
        wav_file.writeframes(audio_bytes)

    return wav_buffer.getvalue()


# --------------------------------------------------
# Voice engine connection
# --------------------------------------------------

async def send_audio_to_voice_engine(
    audio_bytes: bytes,
    user_phone: str,
    language: str = "hi",
) -> dict:
    """
    Send a complete WAV audio clip to the voice engine.

    Expected API response includes:
        recognized_text
        ai_text_response
        output_audio_base64
    """

    wav_bytes = audio_to_wav(audio_bytes)

    payload = {
        "user_phone": user_phone,
        "audio_base64": base64.b64encode(
            wav_bytes
        ).decode("utf-8"),
        "language": language,
        "sample_rate": VOICE_SAMPLE_RATE,
    }

    logger.info(
        "Sending audio to voice engine for user %s",
        user_phone,
    )

    async with httpx.AsyncClient(
        timeout=120.0
    ) as client:

        response = await client.post(
            VOICE_ENGINE_URL,
            json=payload,
        )

        response.raise_for_status()

        result = response.json()

    logger.info(
        "Voice engine response received. Status: %s",
        result.get("status", "unknown"),
    )

    return result


# --------------------------------------------------
# Publish generated speech to LiveKit
# --------------------------------------------------

async def publish_audio_response(
    room: rtc.Room,
    audio_base64: str,
) -> None:
    """
    Decode generated MP3 audio and publish it
    as an audio track in the LiveKit room.
    """

    if not audio_base64:
        logger.warning("Voice engine returned no audio.")
        return

    mp3_bytes = base64.b64decode(audio_base64)

    audio_source = rtc.AudioSource(
        OUTPUT_SAMPLE_RATE,
        1,
    )

    audio_track = rtc.LocalAudioTrack.create_audio_track(
        "awaaz-setu-ai-response",
        audio_source,
    )

    publication = await room.local_participant.publish_track(
        audio_track
    )

    logger.info(
        "Published AI audio track: %s",
        publication.sid,
    )

    try:
        with av.open(io.BytesIO(mp3_bytes), mode="r") as container:

            resampler = av.AudioResampler(
                format="s16",
                layout="mono",
                rate=OUTPUT_SAMPLE_RATE,
            )

            for packet in container.decode(audio=0):

                for frame in resampler.resample(packet):

                    samples = frame.to_ndarray().reshape(-1)
                    samples = np.ascontiguousarray(samples)

                    livekit_frame = rtc.AudioFrame(
                        data=samples,
                        sample_rate=OUTPUT_SAMPLE_RATE,
                        num_channels=1,
                        samples_per_channel=len(samples),
                    )

                    await audio_source.capture_frame(
                        livekit_frame
                    )

            # Flush remaining resampler samples.
            for frame in resampler.resample(None):

                samples = frame.to_ndarray().reshape(-1)
                samples = np.ascontiguousarray(samples)

                livekit_frame = rtc.AudioFrame(
                    data=samples,
                    sample_rate=OUTPUT_SAMPLE_RATE,
                    num_channels=1,
                    samples_per_channel=len(samples),
                )

                await audio_source.capture_frame(
                    livekit_frame
                )

        logger.info("Finished publishing AI audio.")

    finally:
        await room.local_participant.unpublish_track(
            publication.sid
        )

        await audio_source.aclose()


# --------------------------------------------------
# Process one complete caller utterance
# --------------------------------------------------

async def process_caller_audio(
    room: rtc.Room,
    audio_bytes: bytes,
    user_phone: str,
) -> None:
    """Send caller audio to the voice engine."""

    try:
        result = await send_audio_to_voice_engine(
            audio_bytes=audio_bytes,
            user_phone=user_phone,
            language="hi",
        )

        recognized_text = result.get(
            "recognized_text",
            "",
        )

        ai_response = result.get(
            "ai_text_response",
            "",
        )

        logger.info(
            "Recognized caller speech: %s",
            recognized_text,
        )

        logger.info(
            "AI response: %s",
            ai_response,
        )

        output_audio = result.get(
            "output_audio_base64",
            "",
        )

        if output_audio:
            await publish_audio_response(
                room,
                output_audio,
            )
        else:
            logger.warning(
                "The voice engine did not return generated audio."
            )

    except httpx.HTTPStatusError as exc:
        logger.error(
            "Voice engine returned HTTP %s: %s",
            exc.response.status_code,
            exc.response.text,
        )

    except httpx.RequestError as exc:
        logger.error(
            "Cannot connect to voice engine at %s: %s",
            VOICE_ENGINE_URL,
            exc,
        )

    except Exception:
        logger.exception(
            "Failed to process caller audio."
        )


# --------------------------------------------------
# Read incoming LiveKit audio
# --------------------------------------------------

async def read_caller_audio(
    room: rtc.Room,
    track: rtc.Track,
    participant: rtc.RemoteParticipant,
) -> None:
    """
    Collect incoming audio frames and identify speech
    using a simple silence-based detector.

    Audio is sent to the voice engine after the caller
    pauses, or when the maximum clip length is reached.
    """

    user_phone = participant.identity or "unknown"

    audio_stream = rtc.AudioStream(track)

    speech_frames = []
    silence_frames = 0
    speech_started = False
    processing_task = None

    logger.info(
        "Started reading audio from participant %s",
        user_phone,
    )

    try:
        async for event in audio_stream:

            frame = event.frame

            samples = frame.data

            if not isinstance(samples, np.ndarray):
                samples = np.frombuffer(
                    samples,
                    dtype=np.int16,
                )

            samples = np.asarray(samples).reshape(-1)

            if samples.size == 0:
                continue

            # Convert input samples to mono 16-bit PCM.
            if samples.dtype != np.int16:
                samples = samples.astype(np.int16)

            input_rate = frame.sample_rate

            if input_rate != VOICE_SAMPLE_RATE:
                samples = resample_poly(
                    samples.astype(np.float32),
                    VOICE_SAMPLE_RATE,
                    input_rate,
                )

                samples = np.clip(
                    samples,
                    -32768,
                    32767,
                ).astype(np.int16)

            # Calculate audio volume.
            rms = float(
                np.sqrt(
                    np.mean(
                        samples.astype(np.float32) ** 2
                    )
                )
            )

            if rms >= SILENCE_THRESHOLD:
                speech_started = True
                silence_frames = 0

                speech_frames.append(samples.tobytes())

            elif speech_started:
                speech_frames.append(samples.tobytes())
                silence_frames += 1

            # End speech after a period of silence.
            speech_finished = (
                speech_started
                and silence_frames >= SILENCE_DURATION_FRAMES
            )

            maximum_length_reached = (
                len(speech_frames) >= MAX_SPEECH_FRAMES
            )

            if speech_finished or maximum_length_reached:

                if len(speech_frames) >= MIN_SPEECH_FRAMES:

                    complete_audio = b"".join(
                        speech_frames
                    )

                    # Do not process overlapping utterances
                    # from the same participant.
                    if (
                        processing_task is None
                        or processing_task.done()
                    ):
                        processing_task = asyncio.create_task(
                            process_caller_audio(
                                room,
                                complete_audio,
                                user_phone,
                            )
                        )

                    else:
                        logger.warning(
                            "Skipping a speech clip because "
                            "the previous response is still processing."
                        )

                speech_frames = []
                silence_frames = 0
                speech_started = False

    except asyncio.CancelledError:
        raise

    except Exception:
        logger.exception(
            "Error while reading caller audio."
        )

    finally:
        await audio_stream.aclose()

        if processing_task is not None:
            await asyncio.gather(
                processing_task,
                return_exceptions=True,
            )

        logger.info(
            "Stopped reading audio from %s",
            user_phone,
        )


# --------------------------------------------------
# LiveKit agent entrypoint
# --------------------------------------------------

async def entrypoint(ctx: JobContext):

    room = ctx.room

    audio_tasks = {}

    logger.info(
        "Job received for room '%s'",
        room.name,
    )

    @room.on("connection_state_changed")
    def on_state(state: rtc.ConnectionState):
        logger.info(
            "Connection state -> %s",
            state,
        )

    @room.on("participant_connected")
    def on_participant_connected(
        participant: rtc.RemoteParticipant,
    ):
        logger.info(
            "Caller joined: identity=%s",
            participant.identity,
        )

    @room.on("participant_disconnected")
    def on_participant_disconnected(
        participant: rtc.RemoteParticipant,
    ):
        logger.info(
            "Caller left: identity=%s",
            participant.identity,
        )

    @room.on("track_subscribed")
    def on_track_subscribed(
        track: rtc.Track,
        publication: rtc.RemoteTrackPublication,
        participant: rtc.RemoteParticipant,
    ):

        logger.info(
            "Subscribed to %s track from %s",
            track.kind,
            participant.identity,
        )

        if track.kind == rtc.TrackKind.KIND_AUDIO:

            task = asyncio.create_task(
                read_caller_audio(
                    room,
                    track,
                    participant,
                )
            )

            audio_tasks[
                (participant.identity, publication.sid)
            ] = task

            logger.info(
                "Incoming caller audio is connected to "
                "the voice-processing pipeline."
            )

    @room.on("track_unsubscribed")
    def on_track_unsubscribed(
        track: rtc.Track,
        publication: rtc.RemoteTrackPublication,
        participant: rtc.RemoteParticipant,
    ):

        logger.info(
            "Track unsubscribed from %s",
            participant.identity,
        )

        key = (
            participant.identity,
            publication.sid,
        )

        task = audio_tasks.pop(key, None)

        if task is not None:
            task.cancel()

    @room.on("participant_disconnected")
    def cleanup_participant_audio(
        participant: rtc.RemoteParticipant,
    ):

        for key, task in list(audio_tasks.items()):

            if key[0] == participant.identity:
                task.cancel()
                audio_tasks.pop(key, None)

    @room.on("disconnected")
    def on_disconnected(*_):

        logger.info(
            "Agent disconnected from room."
        )

        for task in audio_tasks.values():
            task.cancel()

        audio_tasks.clear()

    await ctx.connect(
        auto_subscribe=AutoSubscribe.AUDIO_ONLY
    )

    logger.info(
        "Agent connected to room '%s'",
        room.name,
    )

    # Preserve the existing demo DPI result.
    # Replace it with real DPI API results when ready.
    await ctx.wait_for_participant()

    await asyncio.sleep(3)

    await send_dpi_result(
        room,
        "e-NAM Mandi Prices (demo)",
        (
            "Tomato prices in Yeshwanthpur Mandi: "
            "Rs 2,400 per Quintal. Trend: Steady."
        ),
    )


# --------------------------------------------------
# Start agent
# --------------------------------------------------

if __name__ == "__main__":

    check_env()

    cli.run_app(
        WorkerOptions(
            entrypoint_fnc=entrypoint,
        )
    )