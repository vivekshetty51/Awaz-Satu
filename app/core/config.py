"""
Core Configuration Module for Awaaz Setu.

Architectural Context:
- Strict zero-cost constraint: relies purely on open-source 'pydantic-settings'.
- Provides centralized, validated environment configuration with deterministic defaults.
- Supports 12-factor application design, reading settings from environment variables
  and an optional `.env` file for local development without hardcoded secrets.
"""

from functools import lru_cache
from typing import Literal
from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """
    Application Settings schema and environment loader.

    Attributes:
        APP_NAME: Human-readable application identifier.
        HOST: Network interface address to bind the HTTP/WebSocket server.
        PORT: Port number on which the server listens.
        PRIMARY_LANGUAGE: Primary default ISO-639 language code for voice processing (e.g., 'hi' for Hindi).
        MAX_AUDIO_SIZE_BYTES: Upper threshold for raw or decoded incoming audio payloads (default 5MB).
    """

    # 1. Core Server & Application Configurations
    APP_NAME: str = Field(
        default="Awaaz Setu",
        description="Application name used in service banners, metadata, and telemetry.",
    )
    HOST: str = Field(
        default="0.0.0.0",
        description="Bind host for the non-blocking ASGI server (e.g., Uvicorn).",
    )
    PORT: int = Field(
        default=8000,
        ge=1,
        le=65535,
        description="TCP port for inbound HTTP and WebSocket connections.",
    )

    # 2. Audio & Language Processing Defaults
    PRIMARY_LANGUAGE: str = Field(
        default="hi",
        min_length=2,
        max_length=10,
        description="Default target language code (e.g., 'hi' for Hindi, 'en' for English).",
    )
    MAX_AUDIO_SIZE_BYTES: int = Field(
        default=5 * 1024 * 1024,  # 5 Megabytes = 5,242,880 bytes
        gt=0,
        description="Maximum permitted audio payload size in bytes to prevent memory exhaustion.",
    )

    # 3. Environment & Logging Settings
    ENVIRONMENT: Literal["development", "staging", "production", "test"] = Field(
        default="development",
        description="Deployment environment name.",
    )
    LOG_LEVEL: str = Field(
        default="INFO",
        description="Standard logging severity level (DEBUG, INFO, WARNING, ERROR, CRITICAL).",
    )

    # 4. Multilingual Speech Recognition (ASR) Configurations
    ASR_PROVIDER: str = Field(
        default="local",
        description="ASR provider: 'local' (LocalWhisperASR) or 'groq' (Groq Whisper LPU).",
    )
    GROQ_API_KEY: str = Field(
        default="",
        description="Groq API key for hosted Whisper transcription (free tier).",
    )
    GROQ_ASR_MODEL: str = Field(
        default="whisper-large-v3-turbo",
        description="Groq Whisper model ('whisper-large-v3-turbo' or 'whisper-large-v3').",
    )

    # 5. General-Purpose Conversational LLM Configurations
    LLM_PROVIDER: str = Field(
        default="gemini",
        description="LLM provider: 'gemini' (Google Gemini API) or 'offline' (deterministic intent fallback).",
    )
    GEMINI_API_KEY: str = Field(
        default="",
        description="Google Gemini API key for free-tier natural language generation.",
    )
    GEMINI_MODEL: str = Field(
        default="gemini-1.5-flash",
        description="Gemini model identifier (e.g., 'gemini-1.5-flash' or 'gemini-2.0-flash').",
    )

    # Pydantic Settings Configuration
    model_config = SettingsConfigDict(
        env_file=(".env", "backend/.env"),
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    @field_validator("PRIMARY_LANGUAGE", mode="before")
    @classmethod
    def normalize_language_code(cls, value: str) -> str:
        """Sanitizes and normalizes language codes to lower-case trimmed strings."""
        if isinstance(value, str):
            return value.strip().lower()
        return value

    @field_validator("LOG_LEVEL", mode="before")
    @classmethod
    def normalize_log_level(cls, value: str) -> str:
        """Ensures log level strings are uppercase and valid."""
        if isinstance(value, str):
            normalized = value.strip().upper()
            valid_levels = {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}
            if normalized not in valid_levels:
                raise ValueError(
                    f"Invalid LOG_LEVEL '{value}'. Expected one of: {sorted(valid_levels)}"
                )
            return normalized
        return value


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """
    Returns a cached singleton instance of application settings.
    Ensures zero I/O overhead on repeated calls across asynchronous request handlers.
    """
    return Settings()


# Export default settings instance for direct import convenience
settings: Settings = get_settings()
