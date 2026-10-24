"""
Free and Open-Source Speech Processing Services for Awaaz Setu.

Architectural Context:
- STRICT ZERO-COST MANDATE: Uses exclusively open-source and free community tools:
  * Speech-to-Text (ASR): `openai-whisper` (local inference, no API keys or paid tiers).
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
import tempfile
import threading
from typing import Dict, Optional
import numpy as np

try:
    import whisper
except ImportError:
    whisper = None  # Handled with graceful runtime error message if package missing

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


AGRICULTURAL_PROMPT: str = (
    "Awaaz Setu: PM-Kisan Samman Nidhi, e-NAM Mandi prices, bhav, rate, "
    "tamatar tomato, gehu wheat, pyaz onion, potato aalu, pashupalan livestock, "
    "cow gay, buffalo bhains, milk doodh, weather mausam, barish rain."
)


class LocalWhisperASR(BaseASR):
    """
    Local Automated Speech Recognition using OpenAI Whisper.
    Performs speech transcription in memory without blocking the FastAPI event loop.
    """

    def __init__(self, model_name: str = "base", device: str = "cpu"):
        """
        Initializes the Whisper ASR engine.

        Args:
            model_name: Whisper model size ('tiny', 'base', 'small', 'medium').
                        'tiny' or 'base' are recommended for ultra-low latency CPU telephony.
            device: Compute device ('cpu', 'cuda').
        """
        # Ensure ffmpeg is discovered and registered in PATH
        ensure_ffmpeg_on_path()
        self.model_name = model_name
        self.device = device
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
                    if whisper is None:
                        raise RuntimeError(
                            "openai-whisper is not installed. Please install it using 'pip install openai-whisper'."
                        )
                    logger.info(f"Loading Whisper model '{self.model_name}' on {self.device}...")
                    self._model = whisper.load_model(self.model_name, device=self.device)
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

        # Strategy 3: Safe fallback using temporary file if input format is arbitrary
        with tempfile.NamedTemporaryFile(suffix=".audio", delete=False) as tmp_file:
            tmp_path = tmp_file.name
            tmp_file.write(audio_bytes)

        try:
            return whisper.load_audio(tmp_path)
        finally:
            if os.path.exists(tmp_path):
                try:
                    os.remove(tmp_path)
                except OSError:
                    pass

    def _transcribe_sync(self, audio_bytes: bytes, language: str) -> str:
        """
        Synchronous, CPU-bound transcription worker. Executed inside a thread pool.
        """
        self._ensure_model_loaded()
        audio_data = self._audio_bytes_to_np_array(audio_bytes)

        lang_code = language.strip().lower() if language else "hi"
        options = {
            "fp16": False,  # Safe CPU execution
            "task": "transcribe",
            "initial_prompt": AGRICULTURAL_PROMPT,
        }

        # If 'auto' or 'multilingual', allow Whisper to auto-detect language
        if lang_code in ("auto", "multilingual", "detect", "any", ""):
            options["language"] = None
        else:
            options["language"] = lang_code

        result = self._model.transcribe(audio_data, **options)
        transcribed_text = result.get("text", "").strip()
        return transcribed_text

    async def transcribe(self, audio_bytes: bytes, language: str = "hi") -> str:
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

    DEFAULT_VOICE = "hi-IN-SwaraNeural"

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
        Defaults to 'hi-IN-SwaraNeural' if not matched.
        """
        normalized_lang = language.strip().lower() if language else "hi"
        return self.voices.get(normalized_lang, self.DEFAULT_VOICE)

    async def synthesize(self, text: str, language: str = "hi") -> str:
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
