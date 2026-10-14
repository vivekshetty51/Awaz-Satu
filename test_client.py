"""
Standalone Client Testing Utility for Awaaz Setu.

Architectural Context:
- Simulates inbound telephony gateway requests by packaging local audio (WAV) into Base64,
  invoking the FastAPI `/process-voice-turn` endpoint, and saving synthesized response audio.
- Zero external dependencies: Uses standard library and open-source `httpx` (or `requests`).
- Emits structured latency telemetry for SLA and performance profiling.
"""

import base64
import os
from pathlib import Path
import sys
import time
from typing import Dict, Any

# Ensure standard output can display multi-lingual Indic characters cleanly on Windows
if sys.platform == "win32" and hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

try:
    import httpx
except ImportError:
    httpx = None

try:
    import requests
except ImportError:
    requests = None


# 1. Fallback Base64 Audio (Minimal valid 16kHz PCM WAV with 0.5s audio data)
# Used automatically if no local 'sample.wav' file is present.
FALLBACK_BASE64_WAV = (
    "UklGRigBAABXQVZFZm10IBAAAAABAAEAQB8AAEAfAAABAAgAZGF0YQABAAAA"
    "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA"
    "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA"
    "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA"
    "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA"
    "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA"
    "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA"
)

ENDPOINT_URL = "http://127.0.0.1:8000/process-voice-turn"
DEFAULT_PHONE = "+919876543210"
DEFAULT_LANGUAGE = "hi"
DEFAULT_AUDIO_FILENAME = "sample.wav"
OUTPUT_AUDIO_FILENAME = "response_output.mp3"


def load_audio_base64(file_path: Path) -> str:
    """
    Loads raw binary audio bytes from file and encodes to a Base64 string.
    Falls back to embedded Base64 payload if file is not found.
    """
    if file_path.is_file():
        file_size_kb = file_path.stat().st_size / 1024.0
        print(f"[Client] Found local audio file: '{file_path.name}' ({file_size_kb:.2f} KB)")
        with open(file_path, "rb") as audio_file:
            raw_bytes = audio_file.read()
            return base64.b64encode(raw_bytes).decode("utf-8")
    else:
        print(f"[Client] Notice: '{file_path.name}' not found. Using default embedded Base64 audio fallback.")
        return FALLBACK_BASE64_WAV


def execute_voice_turn_test(
    endpoint_url: str = ENDPOINT_URL,
    phone: str = DEFAULT_PHONE,
    language: str = DEFAULT_LANGUAGE,
    audio_path: str = DEFAULT_AUDIO_FILENAME,
    output_filename: str = OUTPUT_AUDIO_FILENAME,
) -> bool:
    """
    Dispatches a simulated voice turn to the Awaaz Setu backend, prints telemetry,
    and persists synthesized audio.
    """
    target_audio_file = Path(audio_path)
    audio_b64 = load_audio_base64(target_audio_file)

    payload: Dict[str, Any] = {
        "user_phone": phone,
        "audio_base64": audio_b64,
        "language": language,
    }

    print("\n" + "=" * 60)
    print("      AWAAZ SETU — VOICE INTERFACE TEST CLIENT")
    print("=" * 60)
    print(f"Endpoint Target   : {endpoint_url}")
    print(f"Caller Phone      : {phone}")
    print(f"Language Code     : {language}")
    print(f"Payload Base64 Len: {len(audio_b64):,} chars")
    print("-" * 60)
    print("[Client] Sending request to backend...")

    client_start_time = time.perf_counter()

    try:
        if httpx is not None:
            # High-performance non-blocking client with 30s timeout for cold model loads
            with httpx.Client(timeout=30.0) as client:
                response = client.post(endpoint_url, json=payload)
                status_code = response.status_code
                response_json = response.json()
        elif requests is not None:
            response = requests.post(endpoint_url, json=payload, timeout=30.0)
            status_code = response.status_code
            response_json = response.json()
        else:
            raise RuntimeError("Neither 'httpx' nor 'requests' is installed. Please run 'pip install httpx'.")

    except Exception as net_err:
        print(f"\n[Client Error] Failed to connect to server at {endpoint_url}:")
        print(f"               {net_err}")
        print("\nPlease ensure the Awaaz Setu FastAPI server is running with:")
        print("    uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload\n")
        return False

    client_rtt_ms = round((time.perf_counter() - client_start_time) * 1000, 2)

    # Validate response status
    if status_code != 200:
        print(f"\n[Client Error] Server returned HTTP {status_code}:")
        print(f"               {response_json}")
        return False

    # Extract response fields
    recognized_text = response_json.get("recognized_text", "")
    ai_text_response = response_json.get("ai_text_response", "")
    server_processing_ms = response_json.get("processing_time_ms", 0.0)
    provider_used = response_json.get("provider_used", "Unknown")
    output_audio_b64 = response_json.get("output_audio_base64", "")

    # Output structured test telemetry
    print("\n[Client] Response Received Successfully!")
    print("-" * 60)
    print(f"HTTP Status Code     : {status_code} OK")
    print(f"Recognized Text (STT): {recognized_text}")
    print(f"AI Response (LLM)    : {ai_text_response}")
    print(f"Server Processing    : {server_processing_ms:.2f} ms")
    print(f"Total Client RTT     : {client_rtt_ms:.2f} ms")
    print(f"Provider Used        : {provider_used}")
    print("-" * 60)

    # Decode and save synthesized response audio to local disk
    if output_audio_b64:
        try:
            output_audio_bytes = base64.b64decode(output_audio_b64)
            output_file_path = Path(output_filename).resolve()

            with open(output_file_path, "wb") as out_file:
                out_file.write(output_audio_bytes)

            file_size_kb = len(output_audio_bytes) / 1024.0
            print(f"[Client] Output audio successfully decoded and saved ({file_size_kb:.2f} KB):")
            print(f"         ==> {output_file_path}")
        except Exception as save_err:
            print(f"[Client Error] Failed to save output audio file: {save_err}")
            return False
    else:
        print("[Client Warning] Response did not contain 'output_audio_base64' payload.")

    print("=" * 60 + "\n")
    return True


if __name__ == "__main__":
    execute_voice_turn_test()
