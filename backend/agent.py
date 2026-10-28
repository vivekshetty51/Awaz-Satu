"""
Awaaz Setu - LiveKit Voice Agent with Voice Engine Integration.

Features:
- Connects to LiveKit rooms via managed WebRTC SFU.
- Receives caller audio via WebRTC AudioStream.
- Detects speech boundaries using energy/silence VAD in memory.
- Concurrency control: prevents overlapping responses to the same utterance.
- Paces and delivers synthesized audio to caller with wait_for_playout() synchronization.
- Interrupt-aware: clears pending audio queue if user interrupts or disconnects.
- Robust session cleanup: cancels background tasks and releases resources on disconnect.
- PII protection: strictly masks phone numbers and telephony identities in all logs.
- Preserves DPI result publishing over LiveKit data channel.

Run:
    python agent.py dev
"""

import asyncio
import base64
from collections import deque
import io
import json
import logging
import os
from pathlib import Path
import re
import wave

import av
import httpx
import numpy as np

from dotenv import load_dotenv
from scipy.signal import resample_poly

from livekit import rtc
from livekit.agents import AutoSubscribe, JobContext, WorkerOptions, cli


# Load backend/.env relative to this file to guarantee correct configuration regardless of CWD
ENV_PATH = Path(__file__).resolve().parent / ".env"
if ENV_PATH.is_file():
    load_dotenv(dotenv_path=ENV_PATH)
else:
    load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
)

logger = logging.getLogger("awaaz-setu")

DPI_TOPIC = "dpi_result"

# Voice engine URL (configurable via environment, defaults to port 8000)
VOICE_ENGINE_URL = os.getenv(
    "VOICE_ENGINE_URL",
    "http://127.0.0.1:8000/process-voice-turn",
)

# Audio configuration
VOICE_SAMPLE_RATE = 16000
OUTPUT_SAMPLE_RATE = 24000

# Speech detection configuration
SILENCE_THRESHOLD = 350
SILENCE_DURATION_FRAMES = 25
MIN_SPEECH_FRAMES = 10
MAX_SPEECH_FRAMES = 750


# --------------------------------------------------
# Privacy & PII protection helpers
# --------------------------------------------------

def mask_phone_number(phone: str) -> str:
    """Masks telephone identifier to comply with zero-retention and PII logging guidelines."""
    if not phone or phone == "unknown":
        return "caller-anon"
    cleaned = phone.strip()
    if len(cleaned) <= 4:
        return "****"
    if len(cleaned) > 7:
        prefix = cleaned[:3]
        suffix = cleaned[-4:]
        mask_len = len(cleaned) - 7
        return f"{prefix}{'X' * mask_len}{suffix}"
    return f"***{cleaned[-4:]}"


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
    query: str = "",
    response: str = "",
) -> None:
    """Send DPI results to the frontend over LiveKit data channel."""
    payload_dict = {
        "service": service,
        "details": details,
    }
    if query:
        payload_dict["query"] = query
    if response:
        payload_dict["response"] = response

    payload = json.dumps(payload_dict).encode("utf-8")

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
    Convert raw PCM audio bytes into an in-memory WAV buffer.
    The input must contain 16-bit, mono PCM audio sampled at 16 kHz.
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
    language: str = "en",
) -> dict:
    """
    Send an in-memory WAV audio clip to the voice engine via HTTP POST.
    Expected API response includes recognized_text, ai_text_response, output_audio_base64.
    """
    wav_bytes = audio_to_wav(audio_bytes)

    payload = {
        "user_phone": user_phone,
        "audio_base64": base64.b64encode(wav_bytes).decode("utf-8"),
        "language": language,
        "sample_rate": VOICE_SAMPLE_RATE,
    }

    masked_phone = mask_phone_number(user_phone)
    logger.info("Sending audio to voice engine for user %s (payload bytes=%d)", masked_phone, len(wav_bytes))

    async with httpx.AsyncClient(timeout=120.0) as client:
        response = await client.post(
            VOICE_ENGINE_URL,
            json=payload,
        )
        response.raise_for_status()
        result = response.json()

    logger.info(
        "Voice engine response received. Status: %s (latency: %s ms)",
        result.get("status", "unknown"),
        result.get("processing_time_ms", 0.0),
    )

    return result


# --------------------------------------------------
# Publish generated speech to LiveKit
# --------------------------------------------------

async def play_audio_response(
    audio_source: rtc.AudioSource,
    audio_base64: str,
) -> None:
    """
    Decodes synthesized MP3 audio from the voice engine and streams PCM frames
    into the session's active AudioSource, pacing playback with wait_for_playout().
    """
    if not audio_base64:
        logger.warning("Voice engine returned no audio.")
        return

    mp3_bytes = base64.b64decode(audio_base64)
    total_frames = 0

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
                    samples = np.clip(samples, -32768, 32767).astype(np.int16)
                    samples = np.ascontiguousarray(samples)

                    livekit_frame = rtc.AudioFrame(
                        data=samples.tobytes(),
                        sample_rate=OUTPUT_SAMPLE_RATE,
                        num_channels=1,
                        samples_per_channel=len(samples),
                    )
                    await audio_source.capture_frame(livekit_frame)
                    total_frames += 1

            # Flush remaining resampler samples
            for frame in resampler.resample(None):
                samples = frame.to_ndarray().reshape(-1)
                samples = np.clip(samples, -32768, 32767).astype(np.int16)
                samples = np.ascontiguousarray(samples)

                livekit_frame = rtc.AudioFrame(
                    data=samples.tobytes(),
                    sample_rate=OUTPUT_SAMPLE_RATE,
                    num_channels=1,
                    samples_per_channel=len(samples),
                )
                await audio_source.capture_frame(livekit_frame)
                total_frames += 1

        # Synchronize with real-time playback: wait until queued audio completes
        logger.info(
            "Streamed %d audio frames to AudioSource (queue duration: %.2fs). Awaiting playout completion...",
            total_frames,
            audio_source.queued_duration,
        )
        await audio_source.wait_for_playout()
        logger.info("Finished audio playout.")

    except asyncio.CancelledError:
        logger.info("Audio playout cancelled. Clearing pending queue.")
        audio_source.clear_queue()
        raise
    except Exception as exc:
        logger.error("Error streaming audio to AudioSource: %s", exc, exc_info=True)


# --------------------------------------------------
# Process one complete caller utterance
# --------------------------------------------------

async def process_caller_audio(
    room: rtc.Room,
    audio_source: rtc.AudioSource,
    audio_bytes: bytes,
    user_phone: str,
) -> None:
    """Send caller audio to voice engine and deliver the synthesized speech."""
    masked_phone = mask_phone_number(user_phone)
    try:
        result = await send_audio_to_voice_engine(
            audio_bytes=audio_bytes,
            user_phone=user_phone,
            language=os.getenv("VOICE_LANGUAGE", "en"),
        )

        recognized_text = result.get("recognized_text", "")
        ai_response = result.get("ai_text_response", "")
        dpi_service = result.get("dpi_service")
        dpi_details = result.get("dpi_details")

        logger.info(
            "Recognized caller speech (chars=%d) for user %s: '%s'",
            len(recognized_text),
            masked_phone,
            recognized_text,
        )
        logger.info(
            "Received AI response (chars=%d) for user %s: '%s'",
            len(ai_response),
            masked_phone,
            ai_response,
        )

        # Dispatch DPI result to UI only if an agricultural service intent was identified
        if dpi_service and dpi_details:
            await send_dpi_result(
                room=room,
                service=dpi_service,
                details=dpi_details,
                query=recognized_text,
                response=ai_response,
            )

        output_audio = result.get("output_audio_base64", "")

        if output_audio:
            await play_audio_response(audio_source, output_audio)
        else:
            logger.warning("The voice engine did not return generated audio.")

    except httpx.HTTPStatusError as exc:
        logger.error("Voice engine returned HTTP %s: %s", exc.response.status_code, exc.response.text)
    except httpx.RequestError as exc:
        logger.error("Cannot connect to voice engine at %s: %s", VOICE_ENGINE_URL, exc)
    except asyncio.CancelledError:
        logger.info("Utterance processing cancelled for %s", masked_phone)
        raise
    except Exception:
        logger.exception("Failed to process caller audio for %s", masked_phone)


# --------------------------------------------------
# Read incoming LiveKit audio
# --------------------------------------------------

async def read_caller_audio(
    room: rtc.Room,
    track: rtc.Track,
    participant: rtc.RemoteParticipant,
    audio_source: rtc.AudioSource,
) -> None:
    """
    Collects incoming audio frames from participant track, runs silence-based VAD,
    and coordinates turn processing without overlapping responses.
    """
    # Resolve caller telephone number strictly from participant metadata or environment
    # Never pass participant identity (e.g. 'caller-z75pwn') to Voice Engine as user_phone
    caller_phone = ""
    if participant.metadata:
        try:
            meta = json.loads(participant.metadata)
            if isinstance(meta, dict) and meta.get("phone"):
                caller_phone = str(meta["phone"]).strip()
        except Exception:
            pass

    if not caller_phone:
        caller_phone = os.getenv("ALLOWED_CALLER_NUMBER", "").strip()

    cleaned_phone = re.sub(r"[\s\-()]", "", caller_phone or "")
    if re.match(r"^\+?[0-9]{3,15}$", cleaned_phone):
        user_phone = cleaned_phone
    else:
        logger.error(
            "Invalid or missing caller phone number (found '%s'). Participant identity '%s' rejected.",
            caller_phone or "None",
            participant.identity,
        )
        return

    masked_phone = mask_phone_number(user_phone)

    audio_stream = rtc.AudioStream(track)

    pre_speech_buffer = deque(maxlen=10)
    speech_frames = []
    silence_frames = 0
    speech_started = False
    processing_task = None

    logger.info("Started reading audio from participant %s", masked_phone)

    try:
        async for event in audio_stream:
            frame = event.frame
            samples = frame.data

            if not isinstance(samples, np.ndarray):
                samples = np.frombuffer(samples, dtype=np.int16)

            samples = np.asarray(samples).reshape(-1)
            if samples.size == 0:
                continue

            # Convert input samples to mono 16-bit PCM
            if samples.dtype != np.int16:
                samples = samples.astype(np.int16)

            input_rate = frame.sample_rate

            if input_rate != VOICE_SAMPLE_RATE:
                samples = resample_poly(
                    samples.astype(np.float32),
                    VOICE_SAMPLE_RATE,
                    input_rate,
                )
                samples = np.clip(samples, -32768, 32767).astype(np.int16)

            if not speech_started:
                pre_speech_buffer.append(samples.tobytes())

            # Calculate RMS energy
            rms = float(np.sqrt(np.mean(samples.astype(np.float32) ** 2)))

            if rms >= SILENCE_THRESHOLD:
                # If agent was speaking and caller interrupts, clear remaining playout queue
                if audio_source.queued_duration > 0.05:
                    audio_source.clear_queue()

                if not speech_started:
                    speech_started = True
                    speech_frames.extend(pre_speech_buffer)
                    pre_speech_buffer.clear()

                silence_frames = 0
                speech_frames.append(samples.tobytes())

            elif speech_started:
                speech_frames.append(samples.tobytes())
                silence_frames += 1

            # End speech after a period of silence or reaching max frame limit
            speech_finished = speech_started and silence_frames >= SILENCE_DURATION_FRAMES
            maximum_length_reached = len(speech_frames) >= MAX_SPEECH_FRAMES

            if speech_finished or maximum_length_reached:
                if len(speech_frames) >= MIN_SPEECH_FRAMES:
                    complete_audio = b"".join(speech_frames)

                    # Concurrency control: prevent duplicate processing of the same utterance
                    if processing_task is None or processing_task.done():
                        processing_task = asyncio.create_task(
                            process_caller_audio(
                                room,
                                audio_source,
                                complete_audio,
                                user_phone,
                            )
                        )
                    else:
                        logger.warning(
                            "Skipping speech clip for %s: previous utterance is still processing.",
                            masked_phone,
                        )

                # Reset utterance buffer for next turn
                speech_frames.clear()
                silence_frames = 0
                speech_started = False
                pre_speech_buffer.clear()

    except asyncio.CancelledError:
        logger.info("Reading audio cancelled for %s", masked_phone)
        if processing_task is not None and not processing_task.done():
            processing_task.cancel()
        raise

    except Exception:
        logger.exception("Error while reading caller audio from %s", masked_phone)

    finally:
        await audio_stream.aclose()
        if processing_task is not None and not processing_task.done():
            processing_task.cancel()
            await asyncio.gather(processing_task, return_exceptions=True)

        logger.info("Stopped reading audio from %s", masked_phone)


# --------------------------------------------------
# LiveKit agent entrypoint
# --------------------------------------------------

async def entrypoint(ctx: JobContext):
    room = ctx.room
    audio_tasks = {}

    logger.info("Job received for room '%s'", room.name)

    # Establish session-wide AudioSource and LocalAudioTrack published once
    audio_source = rtc.AudioSource(OUTPUT_SAMPLE_RATE, 1)
    audio_track = rtc.LocalAudioTrack.create_audio_track("awaaz-setu-ai-response", audio_source)

    publication = None

    @room.on("connection_state_changed")
    def on_state(state: rtc.ConnectionState):
        logger.info("Connection state -> %s", state)

    @room.on("participant_connected")
    def on_participant_connected(participant: rtc.RemoteParticipant):
        logger.info("Caller joined: identity=%s", mask_phone_number(participant.identity))

    @room.on("participant_disconnected")
    def on_participant_disconnected(participant: rtc.RemoteParticipant):
        logger.info("Caller left: identity=%s", mask_phone_number(participant.identity))
        # Clear playout queue immediately to prevent stale audio playing to empty room
        audio_source.clear_queue()
        for key, task in list(audio_tasks.items()):
            if key[0] == participant.identity:
                task.cancel()
                audio_tasks.pop(key, None)

    @room.on("track_subscribed")
    def on_track_subscribed(
        track: rtc.Track,
        publication: rtc.RemoteTrackPublication,
        participant: rtc.RemoteParticipant,
    ):
        logger.info(
            "Subscribed to %s track from %s",
            track.kind,
            mask_phone_number(participant.identity),
        )

        if track.kind == rtc.TrackKind.KIND_AUDIO:
            task = asyncio.create_task(
                read_caller_audio(
                    room,
                    track,
                    participant,
                    audio_source,
                )
            )
            audio_tasks[(participant.identity, publication.sid)] = task
            logger.info("Incoming caller audio connected to voice-processing pipeline.")

    @room.on("track_unsubscribed")
    def on_track_unsubscribed(
        track: rtc.Track,
        publication: rtc.RemoteTrackPublication,
        participant: rtc.RemoteParticipant,
    ):
        logger.info("Track unsubscribed from %s", mask_phone_number(participant.identity))
        key = (participant.identity, publication.sid)
        task = audio_tasks.pop(key, None)
        if task is not None:
            task.cancel()

    @room.on("disconnected")
    def on_disconnected(*_):
        logger.info("Agent disconnected from room.")
        audio_source.clear_queue()
        for task in audio_tasks.values():
            task.cancel()
        audio_tasks.clear()

    # Connect to room and auto-subscribe to caller's audio
    await ctx.connect(auto_subscribe=AutoSubscribe.AUDIO_ONLY)
    logger.info("Agent connected to room '%s'", room.name)

    # Publish agent output audio track once for the entire call session
    publication = await room.local_participant.publish_track(audio_track)
    logger.info("Published agent audio track for room session: %s", publication.sid)

    logger.info("Agent ready and actively listening for caller queries in room '%s'.", room.name)


# --------------------------------------------------
# Start agent
# --------------------------------------------------

if __name__ == "__main__":
    check_env()
    cli.run_app(WorkerOptions(entrypoint_fnc=entrypoint))
