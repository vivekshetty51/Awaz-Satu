"""
AI Agent Communication Bridge for Awaaz Setu.

Architectural Context:
- Non-blocking HTTP integration: Uses asynchronous `httpx.AsyncClient` with a strict 3-second timeout SLA.
- Circuit resilience & graceful degradation: Telephony systems cannot tolerate hangs or unhandled crashes.
  If the downstream conversational AI backend is offline, timing out, or returns a non-200 status,
  the bridge seamlessly intercepts the failure, emits a structured telemetry warning, and serves an immediate
  localized mock response.
- Zero-cost: Pure Python standard patterns and open-source `httpx`.
"""

from typing import Any, Dict, Optional
import httpx

from app.core.logger import get_logger

logger = get_logger("awaaz_setu.services.ai_agent")

# Default mock response for graceful degradation when downstream agent is unreachable
DEFAULT_MOCK_RESPONSE: str = (
    "Aapka kisan samman nidhi ka agla kist 15 tarikh ko aayega."
)

DEFAULT_TIMEOUT_SECONDS: float = 3.0
DEFAULT_AI_AGENT_URL: str = "http://localhost:8001/api/chat"


async def query_ai_agent(
    text_query: str,
    phone: str,
    backend_url: str = DEFAULT_AI_AGENT_URL,
) -> str:
    """
    Dispatches a transcribed user query and phone number to the conversational AI Agent backend.

    Guarantees non-blocking execution and never raises an unhandled exception to caller.
    If the remote backend is unavailable, times out (>3.0s), or returns an invalid status,
    it falls back to a deterministic, domain-appropriate mock response.

    Args:
        text_query: Clean transcribed user speech input.
        phone: Caller phone number or telephony identifier.
        backend_url: HTTP endpoint of the conversational AI agent service.

    Returns:
        The AI response text (either from the remote agent or fallback mock string).
    """
    request_payload: Dict[str, Any] = {
        "phone_number": phone,
        "message": text_query,
    }

    client_timeout = httpx.Timeout(DEFAULT_TIMEOUT_SECONDS, connect=1.5)

    try:
        async with httpx.AsyncClient(timeout=client_timeout) as client:
            logger.debug(
                "Dispatching request to AI Agent backend",
                extra={
                    "backend_url": backend_url,
                    "phone": phone,
                    "timeout_seconds": DEFAULT_TIMEOUT_SECONDS,
                },
            )

            response = await client.post(
                backend_url,
                json=request_payload,
                headers={"Content-Type": "application/json", "Accept": "application/json"},
            )

            # Success path (HTTP 200)
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
                        "phone": phone,
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
                "phone": phone,
            },
        )
    except (httpx.ConnectError, httpx.NetworkError) as exc:
        logger.warning(
            "AI Agent backend is unreachable or offline; activating fallback response",
            extra={
                "backend_url": backend_url,
                "error_type": exc.__class__.__name__,
                "phone": phone,
            },
        )
    except httpx.HTTPError as exc:
        logger.warning(
            "HTTP protocol error communicating with AI Agent backend; activating fallback response",
            extra={
                "backend_url": backend_url,
                "error": str(exc),
                "error_type": exc.__class__.__name__,
                "phone": phone,
            },
        )
    except Exception as exc:
        logger.warning(
            "Unexpected error querying AI Agent backend; activating fallback response",
            extra={
                "backend_url": backend_url,
                "error": str(exc),
                "error_type": exc.__class__.__name__,
                "phone": phone,
            },
            exc_info=True,
        )

    # Safe deterministic fallback response
    return DEFAULT_MOCK_RESPONSE
