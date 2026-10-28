"""
Free and Open-Source Speech Processing Services for Awaaz Setu.

Architectural Context:
- STRICT ZERO-COST MANDATE: Uses exclusively open-source and free community tools:
  * Speech-to-Text (ASR): `faster-whisper` (CTranslate2; local CPU inference, no API keys, no PyTorch).
  * Text-to-Speech (TTS): `edge-tts` (Microsoft Edge Free Neural Voice API).
- NON-BLOCKING EVENT LOOP: CPU-bound Whisper inference is offloaded via `asyncio.to_thread`.
- ZERO-DISK / IN-MEMORY BUFFERING: Audio streams are processed in-memory via `io.BytesIO()`.
"""

import asyncio
import base64
import io
import logging
import os
import shutil
import subprocess
import threading
from typing import Dict, Optional
import numpy as np

try:
    from faster_whisper import WhisperModel, decode_audio
except ImportError:
    WhisperModel = None  # Handled with graceful runtime error message if package missing
    decode_audio = None

try:
    import edge_tts
except ImportError:
    edge_tts = None

try:
    import imageio_ffmpeg
except ImportError:
    imageio_ffmpeg = None

from app.core.logger import get_logger
from app.services.speech_base import BaseASR, BaseTTS

logger = get_logger("awaaz_setu.services.speech")


def ensure_ffmpeg_on_path() -> Optional[str]:
    """
    Ensures FFmpeg executable is located and its directory is prepended to os.environ["PATH"].
    Eliminates [WinError 2] 'The system cannot find the file specified' on Windows runtimes
    by dynamically linking the imageio-ffmpeg standalone binary if available.

    Returns:
        Path to the resolved ffmpeg executable, or None if unavailable.
    """
    if imageio_ffmpeg is None:
        return None

    try:
        ffmpeg_exe = imageio_ffmpeg.get_ffmpeg_exe()
        if not ffmpeg_exe or not os.path.exists(ffmpeg_exe):
            return None

        ffmpeg_dir = os.path.dirname(ffmpeg_exe)

        # On Windows, Whisper and standard subprocesses look strictly for 'ffmpeg.exe'.
        # imageio_ffmpeg binary is often named 'ffmpeg-win-x86_64-vX.X.exe'.
        # Ensure a valid 'ffmpeg.exe' exists in the binaries directory.
        standard_name = "ffmpeg.exe" if os.name == "nt" else "ffmpeg"
        target_ffmpeg = os.path.join(ffmpeg_dir, standard_name)
        if not os.path.exists(target_ffmpeg):
            try:
                shutil.copyfile(ffmpeg_exe, target_ffmpeg)
            except Exception as copy_err:
                logger.debug(f"Could not copy ffmpeg binary to standard name: {copy_err}")

        # Prepend to os.environ["PATH"] so Whisper can execute 'ffmpeg' without WinError 2
        current_path = os.environ.get("PATH", "")
        if ffmpeg_dir not in current_path.split(os.pathsep):
            os.environ["PATH"] = ffmpeg_dir + os.pathsep + current_path
            logger.info("Configured FFmpeg path for LocalWhisperASR", extra={"ffmpeg_dir": ffmpeg_dir})

        return target_ffmpeg if os.path.exists(target_ffmpeg) else ffmpeg_exe
    except Exception as exc:
        logger.warning(f"Failed to auto-configure FFmpeg from imageio_ffmpeg: {exc}")
        return None


# Configure FFmpeg in PATH on module import
ensure_ffmpeg_on_path()


# Vocabulary hint that biases recognition toward the terms callers actually use (English).
AGRICULTURAL_PROMPT: str = (
    "Awaaz Setu. Karnataka government schemes: pension, Sandhya Suraksha, scholarship, "
    "Gruha Lakshmi, Anna Bhagya, Gruha Jyothi, Shakti, Yuva Nidhi, Seva Sindhu, "
    "PM-Kisan Samman Nidhi, e-NAM mandi prices, tomato, wheat, onion, potato, "
    "livestock, cow, buffalo, milk, weather, rain."
)


class LocalWhisperASR(BaseASR):
    """
    Local Automated Speech Recognition using faster-whisper (CTranslate2).
    Performs speech transcription in memory without blocking the FastAPI event loop.
    """

    def __init__(self, model_name: str = "base.en", device: str = "cpu", compute_type: str = "int8"):
        """
        Initializes the Whisper ASR engine.

        Args:
            model_name: faster-whisper model ('tiny.en', 'base.en', 'small.en' for English;
                        'tiny', 'base', 'small' for multilingual).
            device: Compute device ('cpu', 'cuda').
            compute_type: CTranslate2 quantisation ('int8' recommended on CPU).
        """
        # Ensure ffmpeg is discovered and registered in PATH
        ensure_ffmpeg_on_path()
        self.model_name = model_name
        self.device = device
        self.compute_type = compute_type
        self._model = None
        self._lock = threading.Lock()
        logger.info(
            "LocalWhisperASR initialized",
            extra={"model_name": self.model_name, "device": self.device},
        )

    def _ensure_model_loaded(self):
        """Thread-safe lazy loader for the Whisper model."""
        ensure_ffmpeg_on_path()
        if self._model is None:
            with self._lock:
                if self._model is None:
                    if WhisperModel is None:
                        raise RuntimeError(
                            "faster-whisper is not installed. Please install it using 'pip install faster-whisper'."
                        )
                    logger.info(f"Loading faster-whisper model '{self.model_name}' on {self.device}...")
                    self._model = WhisperModel(
                        self.model_name, device=self.device, compute_type=self.compute_type
                    )
                    logger.info(f"Whisper model '{self.model_name}' loaded successfully.")

    def _audio_bytes_to_np_array(self, audio_bytes: bytes) -> np.ndarray:
        """
        Converts in-memory audio bytes directly into a float32 16kHz mono numpy array
        as required by Whisper, without writing to disk whenever possible.
        """
        # Ensure PATH contains ffmpeg before any conversion attempt
        ffmpeg_bin = ensure_ffmpeg_on_path() or "ffmpeg"

        # Strategy 1: Attempt direct WAV header parsing via scipy/wave in-memory
        try:
            from scipy.io import wavfile
            sr, data = wavfile.read(io.BytesIO(audio_bytes))

            # Convert integer audio to float32 normalized [-1.0, 1.0]
            if data.dtype == np.int16:
                audio = data.astype(np.float32) / 32768.0
            elif data.dtype == np.int32:
                audio = data.astype(np.float32) / 2147483648.0
            elif data.dtype == np.uint8:
                audio = (data.astype(np.float32) - 128.0) / 128.0
            elif data.dtype == np.float32:
                audio = data
            else:
                audio = data.astype(np.float32)

            # If multichannel (stereo), average across channels to mono
            if audio.ndim > 1:
                audio = np.mean(audio, axis=-1)

            # Resample to 16,000 Hz if necessary
            if sr != 16000:
                from scipy import signal
                num_samples = int(len(audio) * 16000 / sr)
                audio = signal.resample(audio, num_samples).astype(np.float32)

            return np.ascontiguousarray(audio)
        except Exception as wav_err:
            logger.debug(
                f"In-memory scipy WAV parser failed or non-WAV format ({wav_err}). Falling back to FFmpeg pipe."
            )

        # Strategy 2: In-memory FFmpeg pipe (reads from stdin, outputs raw 16kHz PCM to stdout)
        try:
            cmd = [
                ffmpeg_bin,
                "-nostdin",
                "-threads", "0",
                "-i", "pipe:0",
                "-f", "s16le",
                "-ac", "1",
                "-ar", "16000",
                "pipe:1",
            ]
            process = subprocess.Popen(
                cmd,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )
            out_pcm, _ = process.communicate(input=audio_bytes)
            if process.returncode == 0 and len(out_pcm) > 0:
                audio = np.frombuffer(out_pcm, dtype=np.int16).astype(np.float32) / 32768.0
                return np.ascontiguousarray(audio)
        except Exception as ffmpeg_pipe_err:
            logger.debug(f"FFmpeg in-memory pipe failed ({ffmpeg_pipe_err}). Falling back to temp buffer.")

        # Strategy 3: decode arbitrary formats in memory with PyAV (no temp files: zero audio retention)
        if decode_audio is None:
            raise RuntimeError(
                "faster-whisper is not installed. Please install it using 'pip install faster-whisper'."
            )
        return np.ascontiguousarray(
            decode_audio(io.BytesIO(audio_bytes), sampling_rate=16000), dtype=np.float32
        )

    def _transcribe_sync(self, audio_bytes: bytes, language: str) -> str:
        """
        Synchronous, CPU-bound transcription worker. Executed inside a thread pool.
        """
        self._ensure_model_loaded()
        audio_data = self._audio_bytes_to_np_array(audio_bytes)

        lang_code = language.strip().lower() if language else "en"
        # English-only checkpoints (*.en) cannot transcribe any other language.
        if self.model_name.endswith(".en"):
            lang_code = "en"

        # If 'auto' or 'multilingual', allow Whisper to auto-detect language
        auto_detect = lang_code in ("auto", "multilingual", "detect", "any", "")

        segments, _info = self._model.transcribe(
            audio_data,
            language=None if auto_detect else lang_code,
            task="transcribe",
            initial_prompt=AGRICULTURAL_PROMPT,
            beam_size=1,                       # lowest latency
            condition_on_previous_text=False,
            vad_filter=True,                   # silence/noise -> empty text -> retry prompt
        )
        # `segments` is a lazy generator: consume it here, inside the worker thread.
        return " ".join(seg.text.strip() for seg in segments).strip()

    async def transcribe(self, audio_bytes: bytes, language: str = "en") -> str:
        """
        Transcribes speech asynchronously by delegating CPU-heavy computation
        to a separate worker thread via asyncio.to_thread.
        """
        if not audio_bytes:
            raise ValueError("Input audio_bytes cannot be empty.")

        try:
            # Non-blocking invocation preserving the asyncio event loop
            text = await asyncio.to_thread(self._transcribe_sync, audio_bytes, language)
            return text
        except Exception as exc:
            logger.error(
                "Whisper transcription failed",
                extra={"error": str(exc), "language": language},
                exc_info=True,
            )
            raise RuntimeError(f"Speech-to-Text transcription error: {exc}") from exc


class EdgeTTSService(BaseTTS):
    """
    Asynchronous Text-to-Speech synthesis service powered by edge-tts
    (Microsoft Edge Free Neural Voice API).
    """

    # Comprehensive multi-lingual Indian and global neural voice registry
    VOICE_MAP: Dict[str, str] = {
        "hi": "hi-IN-SwaraNeural",       # Hindi (Female)
        "kn": "kn-IN-GaganNeural",       # Kannada (Male)
        "en": "en-IN-NeerjaNeural",      # Indian English (Female)
        "ta": "ta-IN-PallaviNeural",     # Tamil (Female)
        "te": "te-IN-MohanNeural",       # Telugu (Male)
        "mr": "mr-IN-AarohiNeural",      # Marathi (Female)
        "bn": "bn-IN-TanishaaNeural",    # Bengali (Female)
        "gu": "gu-IN-DhwaniNeural",      # Gujarati (Female)
        "ml": "ml-IN-SobhanaNeural",     # Malayalam (Female)
        "ur": "ur-IN-GulNeural",         # Urdu (Female)
    }

    DEFAULT_VOICE = "en-IN-NeerjaNeural"

    def __init__(self, voice_map: Optional[Dict[str, str]] = None):
        """
        Initializes the Edge TTS Service.

        Args:
            voice_map: Optional custom mapping of ISO-639 language codes to neural voices.
        """
        self.voices = voice_map or self.VOICE_MAP
        logger.info("EdgeTTSService initialized with neural voice mapping.")

    def get_voice_for_language(self, language: str) -> str:
        """
        Resolves the appropriate neural voice for a given language code.
        Defaults to the Indian-English voice if not matched.
        """
        normalized_lang = language.strip().lower() if language else "en"
        return self.voices.get(normalized_lang, self.DEFAULT_VOICE)

    async def synthesize(self, text: str, language: str = "en") -> str:
        """
        Synthesizes text into speech asynchronously in memory and returns a Base64 string.

        Args:
            text: Plain text content to synthesize.
            language: Target ISO-639 language code ('hi', 'kn', 'en', etc.).

        Returns:
            Base64-encoded audio string (MP3 format).
        """
        if not text or not text.strip():
            raise ValueError("Input text for synthesis cannot be empty.")

        if edge_tts is None:
            raise RuntimeError(
                "edge-tts is not installed. Please install it using 'pip install edge-tts'."
            )

        voice = self.get_voice_for_language(language)
        cleaned_text = text.strip()

        logger.debug(
            "Starting Edge-TTS synthesis",
            extra={"language": language, "voice": voice, "text_length": len(cleaned_text)},
        )

        try:
            # Memory-buffered audio accumulator (Zero disk writes)
            audio_buffer = io.BytesIO()
            communicate = edge_tts.Communicate(text=cleaned_text, voice=voice)

            # Asynchronous streaming consumption of audio chunks
            async for chunk in communicate.stream():
                if chunk["type"] == "audio":
                    audio_buffer.write(chunk["data"])

            raw_audio = audio_buffer.getvalue()
            if not raw_audio:
                raise RuntimeError("Edge-TTS returned empty audio stream.")

            # Base64 encode directly in memory
            encoded_audio = base64.b64encode(raw_audio).decode("utf-8")
            return encoded_audio

        except Exception as exc:
            logger.error(
                "Edge-TTS synthesis failed",
                extra={"error": str(exc), "language": language, "voice": voice},
                exc_info=True,
            )
            raise RuntimeError(f"Text-to-Speech synthesis error: {exc}") from exc
