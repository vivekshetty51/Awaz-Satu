"""
AI Agent Communication Bridge for Awaaz Setu.

Architectural Context:
- Non-blocking HTTP integration: Uses asynchronous `httpx.AsyncClient` with a strict timeout SLA.
- Multi-tier conversational AI pipeline:
  1. Google Gemini Conversational LLM (free tier: gemini-1.5-flash / gemini-2.0-flash) with
     per-caller session history isolation and agricultural voice prompt grounding.
  2. Legacy / Custom HTTP agent backend (if AI_SERVICE_URL or custom endpoint is specified).
  3. Offline deterministic domain intent fallback (classify_intent) when offline, timed out, or quota exhausted (429).
- Privacy & PII protection: Caller phone numbers are strictly masked before logging.
- Caller session isolation: Caller A's multi-turn conversation memory cannot bleed into Caller B.
- Zero-cost: Free-tier API integration with zero paid service dependency.
"""

from collections import defaultdict
import os
import re
import threading
from typing import Any, Dict, List, Optional
import httpx

from app.core.logger import get_logger
from app.services.intent_router import classify_intent

logger = get_logger("awaaz_setu.services.ai_agent")

# Default mock response for graceful degradation when downstream agent is unreachable
DEFAULT_MOCK_RESPONSE: str = (
    "Aapka kisan samman nidhi ka agla kist 15 tarikh ko aayega."
)

DEFAULT_TIMEOUT_SECONDS: float = 3.0

# Dynamic service URL defaulting to port 8003 to prevent collision with Token Server (port 8001)
DEFAULT_AI_AGENT_URL: str = os.getenv(
    "AI_SERVICE_URL",
    "http://localhost:8003/api/chat",
)

VOICE_SYSTEM_PROMPT: str = (
    "You are Awaaz Setu, an empathetic, concise, and knowledgeable voice-based AI assistant for "
    "Indian farmers, rural communities, and livestock keepers.\n"
    "Mandatory Voice Guidelines:\n"
    "1. Keep responses short and speakable: 1 to 3 short sentences maximum.\n"
    "2. Never use markdown formatting, bullet points, asterisks (*), numbered lists, emojis, or URLs, "
    "as they cannot be spoken naturally by text-to-speech engines.\n"
    "3. Always respond in the SAME language or dialect the user asked in (Kannada, Hindi, English, "
    "Hinglish, or Kanglish). If the user asks in Kannada, respond in conversational Kannada. "
    "If the user asks in Hindi, respond in conversational Hindi.\n"
    "4. Ground all answers in practical agricultural, crop health, weather advisory, and livestock care knowledge.\n"
    "5. Strict anti-hallucination constraint: Never fabricate live APMC/mandi commodity prices or unverified "
    "scheme disbursement dates. If asked for real-time mandi prices or dates, state that they should consult "
    "their local APMC market or official portal."
)


def mask_phone_number(phone: str) -> str:
    """
    Masks telephone identifier to comply with zero-retention and PII logging guidelines.
    Preserves prefix and final 4 digits (e.g., +91XXXXXX3210).
    """
    if not phone:
        return "UNKNOWN"
    cleaned = phone.strip()
    if len(cleaned) <= 4:
        return "****"
    if len(cleaned) > 7:
        prefix = cleaned[:3]
        suffix = cleaned[-4:]
        mask_len = len(cleaned) - 7
        return f"{prefix}{'X' * mask_len}{suffix}"
    return f"***{cleaned[-4:]}"


def clean_voice_text(text: str) -> str:
    """Removes markdown symbols, bullets, asterisks, and extra whitespace for natural TTS reading."""
    if not text:
        return ""
    # Strip markdown headers, bold, italics, bullets, code marks
    cleaned = re.sub(r"[*_#`~>•]", " ", text)
    cleaned = re.sub(r"^\s*[-+*]\s+", "", cleaned, flags=re.MULTILINE)
    cleaned = re.sub(r"\n+", " ", cleaned)
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    return cleaned


class CallerSessionManager:
    """
    Manages bounded multi-turn conversation history isolated per caller telephone identifier.
    Guarantees strict privacy isolation: Caller A's session context is inaccessible to Caller B.
    """

    def __init__(self, max_history_turns: int = 6):
        self.max_history_turns = max_history_turns
        self._sessions: Dict[str, List[Dict[str, str]]] = defaultdict(list)
        self._lock = threading.Lock()

    def get_history(self, phone: str) -> List[Dict[str, str]]:
        """Returns a copy of conversation history for the specified phone number."""
        norm_phone = (phone or "").strip()
        with self._lock:
            return list(self._sessions[norm_phone])

    def add_turn(self, phone: str, role: str, text: str) -> None:
        """Appends a turn to the caller's history, bounding length to max_history_turns."""
        norm_phone = (phone or "").strip()
        if not norm_phone or not text:
            return
        with self._lock:
            history = self._sessions[norm_phone]
            history.append({"role": role, "text": text})
            if len(history) > self.max_history_turns:
                self._sessions[norm_phone] = history[-self.max_history_turns:]

    def clear(self, phone: str) -> None:
        """Clears the session history for a specific telephone number."""
        norm_phone = (phone or "").strip()
        with self._lock:
            self._sessions.pop(norm_phone, None)

    def reset_all(self) -> None:
        """Resets all active caller sessions (used in test teardown)."""
        with self._lock:
            self._sessions.clear()


# Global singleton caller session manager
caller_sessions = CallerSessionManager()


async def query_gemini_llm(
    text_query: str,
    phone: str,
    api_key: Optional[str] = None,
    model_name: Optional[str] = None,
    timeout_seconds: float = 4.0,
) -> Optional[str]:
    """
    Dispatches prompt and caller history to Google Gemini API (v1beta REST endpoint).
    Isolates conversation context per telephone identifier.
    Returns speakable response text or None on failure/quota limit (HTTP 429).
    """
    key = (api_key or os.getenv("GEMINI_API_KEY", "")).strip()
    if not key:
        return None

    model = (model_name or os.getenv("GEMINI_MODEL", "gemini-1.5-flash")).strip()
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={key}"
    masked_phone = mask_phone_number(phone)

    # Retrieve prior turns from caller's isolated session
    history = caller_sessions.get_history(phone)

    # Format Gemini contents array: roles must alternate between "user" and "model"
    contents: List[Dict[str, Any]] = []
    for turn in history:
        gemini_role = "user" if turn["role"] == "user" else "model"
        contents.append({
            "role": gemini_role,
            "parts": [{"text": turn["text"]}],
        })

    # Ensure alternating roles and starting with "user" if history had orphan turns
    if contents and contents[0]["role"] != "user":
        contents = contents[1:]

    # Append current turn as user query
    contents.append({
        "role": "user",
        "parts": [{"text": text_query}],
    })

    payload = {
        "system_instruction": {
            "parts": [{"text": VOICE_SYSTEM_PROMPT}]
        },
        "contents": contents,
        "generationConfig": {
            "temperature": 0.3,
            "maxOutputTokens": 200,
        },
    }

    try:
        client_timeout = httpx.Timeout(timeout_seconds, connect=2.0)
        async with httpx.AsyncClient(timeout=client_timeout) as client:
            response = await client.post(
                url,
                json=payload,
                headers={"Content-Type": "application/json"},
            )

            if response.status_code == 200:
                data = response.json()
                candidates = data.get("candidates", [])
                if candidates:
                    parts = candidates[0].get("content", {}).get("parts", [])
                    if parts and "text" in parts[0]:
                        raw_reply = parts[0]["text"]
                        reply = clean_voice_text(raw_reply)
                        if reply:
                            # Update caller session history with both caller turn and assistant response
                            caller_sessions.add_turn(phone, "user", text_query)
                            caller_sessions.add_turn(phone, "model", reply)
                            logger.info(
                                "Gemini LLM response generated successfully",
                                extra={"phone": masked_phone, "chars": len(reply), "model": model},
                            )
                            return reply

                logger.warning(
                    "Gemini API returned 200 OK but candidates/parts text was missing",
                    extra={"phone": masked_phone, "response_snippet": str(data)[:200]},
                )
                return None

            elif response.status_code == 429:
                logger.warning(
                    "Gemini API free-tier quota/rate limit reached (HTTP 429). Activating offline fallback.",
                    extra={"phone": masked_phone, "model": model},
                )
                return None

            else:
                logger.warning(
                    f"Gemini API returned HTTP {response.status_code}: {response.text[:200]}",
                    extra={"phone": masked_phone, "status_code": response.status_code},
                )
                return None

    except httpx.TimeoutException:
        logger.warning(
            f"Gemini API request timed out (>{timeout_seconds}s). Activating offline fallback.",
            extra={"phone": masked_phone},
        )
        return None
    except Exception as exc:
        logger.warning(
            f"Gemini API communication error: {exc}. Activating offline fallback.",
            extra={"phone": masked_phone},
        )
        return None


async def _query_legacy_http_backend(
    text_query: str,
    phone: str,
    backend_url: str,
) -> str:
    """
    Dispatches request to a remote conversational HTTP AI backend (e.g. mock server or external endpoint).
    Falls back to classify_intent on failure.
    """
    masked_phone = mask_phone_number(phone)
    request_payload: Dict[str, Any] = {
        "phone_number": phone,
        "message": text_query,
    }

    client_timeout = httpx.Timeout(DEFAULT_TIMEOUT_SECONDS, connect=1.5)

    try:
        async with httpx.AsyncClient(timeout=client_timeout) as client:
            logger.debug(
                "Dispatching request to legacy AI Agent backend",
                extra={
                    "backend_url": backend_url,
                    "phone": masked_phone,
                    "timeout_seconds": DEFAULT_TIMEOUT_SECONDS,
                },
            )

            response = await client.post(
                backend_url,
                json=request_payload,
                headers={"Content-Type": "application/json", "Accept": "application/json"},
            )

            if response.status_code == 200:
                try:
                    data = response.json()
                    ai_reply = data.get("response")
                    if isinstance(ai_reply, str) and ai_reply.strip():
                        return ai_reply.strip()
                    else:
                        logger.warning(
                            "AI Agent returned 200 OK but payload missing valid 'response' key",
                            extra={"response_payload": str(data), "backend_url": backend_url},
                        )
                except ValueError as json_err:
                    logger.warning(
                        "AI Agent response was not valid JSON",
                        extra={"raw_text": response.text[:200], "error": str(json_err)},
                    )
            else:
                logger.warning(
                    f"AI Agent backend returned non-200 HTTP status: {response.status_code}",
                    extra={
                        "status_code": response.status_code,
                        "backend_url": backend_url,
                        "phone": masked_phone,
                        "response_snippet": response.text[:200],
                    },
                )

    except httpx.TimeoutException as exc:
        logger.warning(
            "AI Agent backend request timed out; activating fallback response",
            extra={
                "backend_url": backend_url,
                "timeout_threshold_seconds": DEFAULT_TIMEOUT_SECONDS,
                "error_type": exc.__class__.__name__,
                "phone": masked_phone,
            },
        )
    except (httpx.ConnectError, httpx.NetworkError) as exc:
        logger.warning(
            "AI Agent backend is unreachable or offline; activating fallback response",
            extra={
                "backend_url": backend_url,
                "error_type": exc.__class__.__name__,
                "phone": masked_phone,
            },
        )
    except httpx.HTTPError as exc:
        logger.warning(
            "HTTP protocol error communicating with AI Agent backend; activating fallback response",
            extra={
                "backend_url": backend_url,
                "error": str(exc),
                "error_type": exc.__class__.__name__,
                "phone": masked_phone,
            },
        )
    except Exception as exc:
        logger.warning(
            "Unexpected error querying AI Agent backend; activating fallback response",
            extra={
                "backend_url": backend_url,
                "error": str(exc),
                "error_type": exc.__class__.__name__,
                "phone": masked_phone,
            },
            exc_info=True,
        )

    # Domain-aware deterministic fallback response resolving appropriate agricultural advice
    _, _, domain_fallback = classify_intent(text_query)
    return domain_fallback


async def query_ai_agent(
    text_query: str,
    phone: str,
    backend_url: Optional[str] = None,
) -> str:
    """
    Dispatches a transcribed user query and phone number to conversational AI.
    1. If a custom backend_url is provided (e.g. in test or custom deployment),
       dispatches to that downstream HTTP service.
    2. If Gemini API is configured (GEMINI_API_KEY present and LLM_PROVIDER != 'offline'),
       queries Google Gemini API with isolated per-caller conversation history.
    3. Falls back smoothly to domain intent classification on quota errors (429), timeouts,
       or offline connectivity, never failing the voice turn.
    """
    # Priority 1: Explicit custom backend_url provided (e.g. in test)
    if backend_url:
        return await _query_legacy_http_backend(text_query, phone, backend_url)

    # Priority 2: Google Gemini Conversational LLM
    gemini_key = (os.getenv("GEMINI_API_KEY", "")).strip()
    llm_provider = (os.getenv("LLM_PROVIDER", "gemini")).strip().lower()

    if gemini_key and llm_provider != "offline":
        model_name = os.getenv("GEMINI_MODEL", "gemini-1.5-flash")
        gemini_response = await query_gemini_llm(
            text_query=text_query,
            phone=phone,
            api_key=gemini_key,
            model_name=model_name,
        )
        if gemini_response:
            return gemini_response

    # Priority 3: Legacy AI_SERVICE_URL if explicitly configured in environment
    env_service_url = os.getenv("AI_SERVICE_URL", "").strip()
    if env_service_url:
        return await _query_legacy_http_backend(text_query, phone, env_service_url)

    # Priority 4: Offline domain intent fallback
    _, _, domain_fallback = classify_intent(text_query)
    return domain_fallback
