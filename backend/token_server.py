"""
Token server: the browser "Virtual Phone Dialer" calls this to get a
LiveKit access token before joining a room.

Run:  uvicorn token_server:app --port 8001 --reload
Test: http://localhost:8001/token?room=awaaz-demo&identity=caller1
"""
import json
import os
from pathlib import Path
import re
from typing import Dict, Any, Optional

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Query, status
from fastapi.middleware.cors import CORSMiddleware
from livekit import api
from pydantic import BaseModel

# Explicitly load backend/.env relative to this file's directory to ensure reliable
# environment configuration regardless of the active current working directory (CWD)
ENV_PATH = Path(__file__).resolve().parent / ".env"
if ENV_PATH.is_file():
    load_dotenv(dotenv_path=ENV_PATH)
else:
    load_dotenv()

app = FastAPI(title="Awaaz Setu Token Server")

# Allow configurable CORS origins for browser security
cors_origins_env = os.getenv("CORS_ORIGINS", "*")
allowed_origins = [o.strip() for o in cors_origins_env.split(",") if o.strip()]

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins if allowed_origins else ["*"],
    allow_credentials=True,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["*"],
)


class PhoneValidationRequest(BaseModel):
    phone: str = ""


def normalize_phone(phone: str) -> str:
    """
    Normalizes a telephone number for strict comparison:
    - Trims leading and trailing whitespace
    - Removes internal whitespace, hyphens, parentheses, and dots
    - Consistently strips an optional leading '+'
    Does not allow partial or substring matching.
    """
    if not phone:
        return ""
    cleaned = phone.strip()
    cleaned = re.sub(r"[\s\-\(\)\.]+", "", cleaned)
    if cleaned.startswith("+"):
        cleaned = cleaned[1:]
    return cleaned


def is_caller_number_allowed(phone: str) -> bool:
    """
    Authoritative server-side caller number validation.
    Checks normalized entered number against ALLOWED_CALLER_NUMBER environment variable.
    Requires strict exact equality; rejects partial or substring matches.
    If ALLOWED_CALLER_NUMBER is empty or not set, rejects all incoming numbers.
    """
    allowed = os.getenv("ALLOWED_CALLER_NUMBER", "").strip()
    if not allowed:
        return False
    norm_phone = normalize_phone(phone)
    norm_allowed = normalize_phone(allowed)
    if not norm_phone or not norm_allowed:
        return False
    return norm_phone == norm_allowed


@app.get("/health", status_code=status.HTTP_200_OK)
def health_check() -> Dict[str, Any]:
    """
    Health check probe for the Token Server.
    Reports operational status and presence of LiveKit and caller credentials without leaking secrets.
    """
    livekit_configured = bool(
        os.getenv("LIVEKIT_URL")
        and os.getenv("LIVEKIT_API_KEY")
        and os.getenv("LIVEKIT_API_SECRET")
    )
    allowed_caller_configured = bool(os.getenv("ALLOWED_CALLER_NUMBER", "").strip())
    return {
        "status": "healthy",
        "service": "token_server",
        "livekit_configured": livekit_configured,
        "allowed_caller_configured": allowed_caller_configured,
    }


@app.get("/validate-phone")
def validate_phone_get(
    phone: str = Query(
        default="",
        description="Caller phone number to validate against permitted caller configuration.",
    ),
):
    """
    Pre-call validation probe: verifies whether the entered caller number matches the permitted configuration.
    Returns 200 OK if allowed, otherwise raises 403 Forbidden with 'Invalid number'.
    """
    if not phone or not is_caller_number_allowed(phone):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Invalid number",
        )
    return {"valid": True, "message": "Phone number validated."}


@app.post("/validate-phone")
def validate_phone_post(
    req: Optional[PhoneValidationRequest] = None,
    phone: str = Query(default=""),
):
    """
    POST variant for pre-call phone validation. Accepts JSON body or query parameter.
    """
    number_to_check = (req.phone if req and req.phone else phone)
    if not number_to_check or not is_caller_number_allowed(number_to_check):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Invalid number",
        )
    return {"valid": True, "message": "Phone number validated."}


@app.get("/token")
def get_token(
    room: str = Query(
        default="awaaz-demo",
        min_length=1,
        max_length=64,
        description="LiveKit room name (alphanumeric, hyphens, underscores).",
    ),
    identity: str = Query(
        default="caller",
        min_length=1,
        max_length=64,
        description="Participant caller identifier or sanitized phone number.",
    ),
    phone: str = Query(
        default="",
        description="Caller phone number to validate against permitted caller configuration.",
    ),
):
    """
    Issues a validated, short-lived JWT token for joining a LiveKit room.
    Validates parameter structure to prevent injection or malformed sessions.
    Authoritatively checks caller phone number against ALLOWED_CALLER_NUMBER when configured.
    """
    # Sanitize and validate room name and identity
    if not re.match(r"^[a-zA-Z0-9_\-\.]+$", room):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid room name. Must contain only alphanumeric, hyphens, underscores, or periods.",
        )

    if not re.match(r"^\+?[a-zA-Z0-9_\-\.]+$", identity):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid identity. Must contain only alphanumeric, hyphens, underscores, or phone prefixes.",
        )

    # Authoritative caller validation:
    allowed_caller = os.getenv("ALLOWED_CALLER_NUMBER", "").strip()
    if allowed_caller:
        # If ALLOWED_CALLER_NUMBER is set, caller must provide a valid matching number
        caller_number = phone if phone else identity
        if not is_caller_number_allowed(caller_number):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Invalid number",
            )
    elif phone:
        # If phone query parameter was provided but ALLOWED_CALLER_NUMBER is not configured, reject
        if not is_caller_number_allowed(phone):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Invalid number",
            )

    api_key = os.getenv("LIVEKIT_API_KEY")
    api_secret = os.getenv("LIVEKIT_API_SECRET")
    livekit_url = os.getenv("LIVEKIT_URL")

    if not (api_key and api_secret and livekit_url):
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="LiveKit credentials not configured on token server.",
        )

    # Embed validated caller telephone number in token metadata for downstream agent
    caller_phone_num = phone if phone else (caller_number if 'caller_number' in locals() and is_caller_number_allowed(caller_number) else "")
    metadata_payload = json.dumps({"phone": caller_phone_num}) if caller_phone_num else ""

    token_builder = (
        api.AccessToken(api_key, api_secret)
        .with_identity(identity)
        .with_grants(api.VideoGrants(room_join=True, room=room))
    )
    if metadata_payload:
        token_builder = token_builder.with_metadata(metadata_payload)

    token = token_builder.to_jwt()
    return {"token": token, "url": livekit_url, "room": room}
