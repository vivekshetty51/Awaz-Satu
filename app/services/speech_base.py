"""
Abstract Base Classes for Speech Processing Services in Awaaz Setu.

Architectural Context:
- Strict decoupling: Defines pluggable interfaces for Speech-to-Text (ASR)
  and Text-to-Speech (TTS) engines.
- Asynchronous API contracts: Guarantees non-blocking event-loop integration
  for high-concurrency telephony workloads.
- Zero vendor lock-in: Allows seamless switching between free local models
  (e.g., Whisper, Piper) and cloud-agnostic open pipelines without impacting domain logic.
"""

from abc import ABC, abstractmethod


class BaseASR(ABC):
    """
    Abstract Base Class for Automated Speech Recognition (ASR / STT).
    Implementations must process raw audio bytes and return transcribed text.
    """

    @abstractmethod
    async def transcribe(self, audio_bytes: bytes, language: str) -> str:
        """
        Transcribes speech from raw audio bytes into text asynchronously.

        Args:
            audio_bytes: Raw binary audio payload (WAV, PCM, MP3, etc.).
            language: Target ISO-639-1 language code (e.g., 'hi', 'kn', 'en').

        Returns:
            Transcribed text as a clean string.

        Raises:
            Exception: If transcription fails or audio is malformed.
        """
        pass


class BaseTTS(ABC):
    """
    Abstract Base Class for Text-to-Speech synthesis (TTS).
    Implementations must synthesize text into Base64-encoded audio.
    """

    @abstractmethod
    async def synthesize(self, text: str, language: str) -> str:
        """
        Synthesizes speech from text asynchronously.

        Args:
            text: The text string to be synthesized.
            language: Target ISO-639-1 language code (e.g., 'hi', 'kn', 'en').

        Returns:
            Base64-encoded audio string ready for network transmission or telephony streaming.

        Raises:
            Exception: If speech synthesis fails or input text is invalid.
        """
        pass
