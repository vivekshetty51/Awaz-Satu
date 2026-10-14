"""
Main Application and Voice Pipeline Orchestrator for Awaaz Setu.

Architectural Context:
- Low-latency voice interface orchestrating:
  Inbound Audio (Base64) -> ASR (Local Whisper) -> AI Agent (Downstream HTTP) -> TTS (Edge-TTS) -> Outbound Audio (Base64).
- Production-grade lifecycle management using FastAPI's modern lifespan handler.
- Strict zero-cost constraint: 100% open-source components with non-blocking event-loop execution.
- Precise millisecond-level telemetry and structured JSON logging.
"""

from contextlib import asynccontextmanager
import base64
import time
from typing import Dict

from fastapi import FastAPI, HTTPException, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.core.config import settings
from app.core.logger import get_logger, setup_logging
from app.schemas.voice import IncomingAudioPayload, VoiceResponsePayload
from app.services.ai_agent import query_ai_agent
from app.services.free_speech_service import EdgeTTSService, LocalWhisperASR

# Initialize structured logging
setup_logging(settings.LOG_LEVEL)
logger = get_logger("awaaz_setu.main")


# Global or state-managed speech service accessors
def get_asr_service() -> LocalWhisperASR:
    """Returns the singleton Whisper ASR service from app state or initializes lazily."""
    if not hasattr(app.state, "asr_service") or app.state.asr_service is None:
        logger.info("Initializing LocalWhisperASR lazily...")
        app.state.asr_service = LocalWhisperASR(model_name="tiny")
    return app.state.asr_service


def get_tts_service() -> EdgeTTSService:
    """Returns the singleton Edge TTS service from app state or initializes lazily."""
    if not hasattr(app.state, "tts_service") or app.state.tts_service is None:
        logger.info("Initializing EdgeTTSService lazily...")
        app.state.tts_service = EdgeTTSService()
    return app.state.tts_service


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Application Lifespan context manager.
    Handles startup model initialization and clean shutdown of resource pools.
    """
    logger.info(
        "Initiating Awaaz Setu application startup...",
        extra={"app_name": settings.APP_NAME, "env": settings.ENVIRONMENT},
    )

    # Instantiate speech engines once on startup (warm-up)
    # Using 'tiny' or 'base' for ultra-low latency voice processing
    app.state.asr_service = get_asr_service()
    app.state.tts_service = get_tts_service()

    # Pre-warm Whisper model on startup to eliminate cold-start penalty for the first caller
    try:
        app.state.asr_service._ensure_model_loaded()
        logger.info("Speech engines pre-warmed and ready for inference.")
    except Exception as warm_err:
        logger.warning(
            f"Speech engine pre-warm warning (will retry on first turn): {warm_err}",
            exc_info=True,
        )

    yield

    # Graceful shutdown lifecycle
    logger.info("Shutting down Awaaz Setu application and releasing resources.")
    app.state.asr_service = None
    app.state.tts_service = None


# FastAPI Application instance
app = FastAPI(
    title=settings.APP_NAME,
    description="Low-Latency Open-Source Voice Interface Orchestration Backend for Awaaz Setu",
    version="1.0.0",
    lifespan=lifespan,
)

# CORS Middleware allowing high-throughput cross-origin integrations
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health", status_code=status.HTTP_200_OK, tags=["System Health"])
async def health_check() -> Dict[str, str]:
    """
    Liveness and readiness health probe for load balancers and orchestrators.
    """
    return {"status": "healthy"}


@app.post(
    "/process-voice-turn",
    response_model=VoiceResponsePayload,
    status_code=status.HTTP_200_OK,
    tags=["Voice Processing"],
)
async def process_voice_turn(payload: IncomingAudioPayload) -> VoiceResponsePayload:
    """
    Orchestrates an end-to-end multi-modal voice turn:
    1. Base64 audio decoding and size validation.
    2. Speech-to-Text transcription via local Whisper ASR (non-blocking).
    3. Conversational AI reasoning via the AI Agent communication bridge.
    4. Text-to-Speech synthesis via Edge-TTS neural voices (non-blocking, in-memory).
    5. Latency profiling and structured response return.
    """
    start_time = time.perf_counter()

    logger.info(
        "Received voice turn request",
        extra={
            "user_phone": payload.user_phone,
            "language": payload.language,
            "sample_rate": payload.sample_rate,
            "payload_base64_len": len(payload.audio_base64),
        },
    )

    # Step 1 & 2: Decode Base64 audio with size constraint enforcement
    try:
        audio_bytes = base64.b64decode(payload.audio_base64, validate=True)
    except Exception as decode_err:
        logger.error(
            "Base64 audio decoding failure",
            extra={"error": str(decode_err), "user_phone": payload.user_phone},
        )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid Base64 audio payload: {decode_err}",
        )

    if len(audio_bytes) > settings.MAX_AUDIO_SIZE_BYTES:
        logger.warning(
            "Audio payload exceeds maximum permitted size",
            extra={
                "size_bytes": len(audio_bytes),
                "max_size_bytes": settings.MAX_AUDIO_SIZE_BYTES,
                "user_phone": payload.user_phone,
            },
        )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Audio payload size ({len(audio_bytes)} bytes) exceeds the {settings.MAX_AUDIO_SIZE_BYTES} bytes limit.",
        )

    try:
        asr_service: LocalWhisperASR = get_asr_service()
        tts_service: EdgeTTSService = get_tts_service()

        # Step 3: Automated Speech Recognition (ASR)
        recognized_text = await asr_service.transcribe(
            audio_bytes=audio_bytes,
            language=payload.language,
        )

        # Handle empty speech / silence input gracefully
        if not recognized_text.strip():
            logger.info(
                "Speech recognition returned empty string (silence or ambient noise). Applying conversational prompt.",
                extra={"user_phone": payload.user_phone},
            )
            recognized_text = "नमस्ते"

        logger.info(
            "Speech recognition completed",
            extra={"recognized_text": recognized_text, "user_phone": payload.user_phone},
        )

        # Step 4: Conversational AI Reasoning
        ai_text_response = await query_ai_agent(
            text_query=recognized_text,
            phone=payload.user_phone,
        )

        logger.info(
            "AI Agent reasoning completed",
            extra={"ai_text_response": ai_text_response, "user_phone": payload.user_phone},
        )

        # Step 5: Text-to-Speech Synthesis (TTS)
        output_audio_base64 = await tts_service.synthesize(
            text=ai_text_response,
            language=payload.language,
        )

        # Step 6: Calculate total elapsed turn latency
        elapsed_ms = round((time.perf_counter() - start_time) * 1000, 2)

        logger.info(
            "Voice turn completed successfully",
            extra={
                "user_phone": payload.user_phone,
                "processing_time_ms": elapsed_ms,
                "output_audio_len": len(output_audio_base64),
            },
        )

        # Step 7: Return structured response
        return VoiceResponsePayload(
            status="success",
            recognized_text=recognized_text,
            ai_text_response=ai_text_response,
            output_audio_base64=output_audio_base64,
            processing_time_ms=elapsed_ms,
            provider_used="OpenSource-Local-Stack",
        )

    except HTTPException:
        raise
    except Exception as pipeline_err:
        elapsed_ms = round((time.perf_counter() - start_time) * 1000, 2)
        logger.error(
            "Voice pipeline execution failed",
            extra={
                "error": str(pipeline_err),
                "user_phone": payload.user_phone,
                "processing_time_ms": elapsed_ms,
            },
            exc_info=True,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Voice processing pipeline error: {str(pipeline_err)}",
        )


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "app.main:app",
        host=settings.HOST,
        port=settings.PORT,
        reload=True,
    )
