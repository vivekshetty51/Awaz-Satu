"""
Hosted Groq Speech Recognition Service (Groq Whisper on LPUs).

Architectural Context:
- Uses Groq's high-speed hosted Whisper models (whisper-large-v3-turbo, whisper-large-v3).
- Strictly enabled only when configured via environment variables (ASR_PROVIDER='groq' and GROQ_API_KEY).
- Free-tier rate limits and quotas are respected; automatically falls back to LocalWhisperASR on 429, timeout, or error.
- Operates on complete memory-buffered WAV utterances from VAD; does not stream tiny frames to HTTP endpoints.
- Supports Kannada ('kn'), Hindi ('hi'), English ('en'), and automatic language detection / code-switching.
"""

import os
from typing import Optional
import httpx

from app.core.logger import get_logger
from app.services.speech_base import BaseASR
from app.services.free_speech_service import AGRICULTURAL_PROMPT, LocalWhisperASR

logger = get_logger("awaaz_setu.services.groq_asr")

GROQ_TRANSCRIPTION_URL = "https://api.groq.com/openai/v1/audio/transcriptions"
DEFAULT_GROQ_MODEL = "whisper-large-v3-turbo"


class GroqWhisperASR(BaseASR):
    """
    Hosted Groq ASR implementation leveraging whisper-large-v3-turbo on Groq LPUs.
    Provides sub-300ms transcription for complete audio utterances with automatic
    fallback to LocalWhisperASR on rate limits or network issues.
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        model_name: Optional[str] = None,
        fallback_asr: Optional[BaseASR] = None,
        timeout_seconds: float = 6.0,
    ):
        self.api_key = (api_key or os.getenv("GROQ_API_KEY", "")).strip()
        self.model_name = (model_name or os.getenv("GROQ_ASR_MODEL", DEFAULT_GROQ_MODEL)).strip()
        self.fallback_asr = fallback_asr or LocalWhisperASR(model_name="tiny")
        self.timeout_seconds = timeout_seconds

        logger.info(
            "GroqWhisperASR initialized",
            extra={"model": self.model_name, "has_api_key": bool(self.api_key)},
        )

    async def transcribe(self, audio_bytes: bytes, language: str = "auto") -> str:
        """
        Transcribes speech audio via Groq Whisper API.
        Falls back to local Whisper on 429, timeout, network error, or missing key.
        """
        if not audio_bytes:
            raise ValueError("Input audio_bytes cannot be empty.")

        # If API key is not configured, seamlessly execute local fallback
        if not self.api_key:
            logger.warning("GROQ_API_KEY is not configured. Falling back to local Whisper ASR.")
            return await self.fallback_asr.transcribe(audio_bytes, language)

        # Prepare multipart/form-data payload with in-memory WAV bytes
        files = {
            "file": ("audio.wav", audio_bytes, "audio/wav"),
        }
        data = {
            "model": self.model_name,
            "prompt": AGRICULTURAL_PROMPT,
            "response_format": "json",
            "temperature": "0.0",
        }

        # Handle language: only pass explicit language code if reliably known (e.g. 'hi', 'kn', 'en')
        # Otherwise omit to let Groq Whisper auto-detect the language and code-switch
        norm_lang = (language or "").strip().lower()
        if norm_lang and norm_lang not in ("auto", "multilingual", "detect", "any"):
            data["language"] = norm_lang

        headers = {
            "Authorization": f"Bearer {self.api_key}",
        }

        try:
            client_timeout = httpx.Timeout(self.timeout_seconds, connect=2.0)
            async with httpx.AsyncClient(timeout=client_timeout) as client:
                response = await client.post(
                    GROQ_TRANSCRIPTION_URL,
                    files=files,
                    data=data,
                    headers=headers,
                )

                if response.status_code == 200:
                    result_json = response.json()
                    transcribed = result_json.get("text", "").strip()
                    logger.info(
                        "Groq ASR transcription succeeded",
                        extra={"model": self.model_name, "chars": len(transcribed)},
                    )
                    return transcribed

                elif response.status_code == 429:
                    logger.warning(
                        "Groq ASR rate limit reached (HTTP 429). Activating local Whisper fallback.",
                    )
                    return await self.fallback_asr.transcribe(audio_bytes, language)

                else:
                    logger.warning(
                        f"Groq ASR returned HTTP {response.status_code}: {response.text[:150]}. Activating fallback.",
                    )
                    return await self.fallback_asr.transcribe(audio_bytes, language)

        except httpx.TimeoutException:
            logger.warning(
                f"Groq ASR request timed out (>{self.timeout_seconds}s). Activating local Whisper fallback.",
            )
            return await self.fallback_asr.transcribe(audio_bytes, language)

        except Exception as exc:
            logger.warning(
                f"Groq ASR connection failed: {exc}. Activating local Whisper fallback.",
                exc_info=False,
            )
            return await self.fallback_asr.transcribe(audio_bytes, language)
