"""
Language policy for Awaaz Setu.

ENGLISH_ONLY=true (default): the whole call is English. ASR is forced to English,
TTS uses the Indian-English voice and the LLM prompts demand English replies.
Set ENGLISH_ONLY=false when regional languages are added.
"""
import os

from app.core.config import settings


def english_only() -> bool:
    raw = os.getenv("ENGLISH_ONLY")
    if raw is not None:
        return raw.strip().lower() not in ("0", "false", "no")
    return bool(settings.ENGLISH_ONLY)


def resolve_language(requested: str | None) -> str:
    """Language code to actually use for ASR/TTS, given what the client asked for."""
    if english_only():
        return "en"
    return (requested or "").strip().lower() or "en"
