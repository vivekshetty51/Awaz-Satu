"""
Unit and Integration Tests for Caller Phone Validation & Whitelisting in Awaaz Setu.

Coverage:
1. Phone normalization rules (whitespace, hyphens, optional leading '+', non-partial match).
2. Authoritative pre-call validation endpoint (GET & POST /validate-phone).
3. LiveKit Token issuance enforcement (GET /token?phone=...).
4. Token server health check exposure of 'allowed_caller_configured' without leaking PII.
5. LiveKit Agent passing configured caller number to Voice Engine as user_phone.
"""

import asyncio
import os
import unittest
from unittest.mock import AsyncMock, patch, MagicMock

from fastapi.testclient import TestClient

from backend.token_server import (
    app as token_server_app,
    normalize_phone,
    is_caller_number_allowed,
)
from backend.agent import mask_phone_number, process_caller_audio, read_caller_audio


class TestPhoneValidation(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.client = TestClient(token_server_app)
        cls.mock_livekit_env = {
            "LIVEKIT_URL": "ws://127.0.0.1:7880",
            "LIVEKIT_API_KEY": "devkey",
            "LIVEKIT_API_SECRET": "secret",
            "ALLOWED_CALLER_NUMBER": "+919876543210",
        }

    # -------------------------------------------------------------------------
    # 1. Normalization & Strict Matching Logic
    # -------------------------------------------------------------------------
    def test_01_normalization_variations(self):
        """Verifies normalization handles whitespace, dashes, and optional '+' consistently."""
        self.assertEqual(normalize_phone("+919876543210"), "919876543210")
        self.assertEqual(normalize_phone("919876543210"), "919876543210")
        self.assertEqual(normalize_phone("  +91 9876-543-210  "), "919876543210")
        self.assertEqual(normalize_phone("+1 (555) 123-4567"), "15551234567")
        self.assertEqual(normalize_phone(""), "")
        self.assertEqual(normalize_phone(None), "")

    def test_02_strict_matching_no_partial(self):
        """Verifies is_caller_number_allowed prevents substring and partial matches."""
        with patch.dict(os.environ, {"ALLOWED_CALLER_NUMBER": "+919876543210"}):
            # Exact matches (with and without leading '+')
            self.assertTrue(is_caller_number_allowed("+919876543210"))
            self.assertTrue(is_caller_number_allowed("919876543210"))
            self.assertTrue(is_caller_number_allowed(" +91 9876 543 210 "))

            # Disallowed partials / prefixes / suffixes
            self.assertFalse(is_caller_number_allowed("9876543210"))       # Missing country code
            self.assertFalse(is_caller_number_allowed("+9198765"))          # Prefix truncated
            self.assertFalse(is_caller_number_allowed("543210"))            # Suffix only
            self.assertFalse(is_caller_number_allowed("+9198765432100"))    # Extra digit
            self.assertFalse(is_caller_number_allowed("+19876543210"))      # Wrong country code
            self.assertFalse(is_caller_number_allowed(""))                  # Empty string
            self.assertFalse(is_caller_number_allowed("   "))               # Whitespace only
            self.assertFalse(is_caller_number_allowed("random-string"))     # Invalid format

    def test_03_no_allowed_number_configured(self):
        """Verifies that if ALLOWED_CALLER_NUMBER is empty, all numbers are rejected."""
        with patch.dict(os.environ, {"ALLOWED_CALLER_NUMBER": ""}):
            self.assertFalse(is_caller_number_allowed("+919876543210"))
            self.assertFalse(is_caller_number_allowed("919876543210"))

    # -------------------------------------------------------------------------
    # 2. Pre-Call Validation Endpoint (/validate-phone)
    # -------------------------------------------------------------------------
    def test_04_validate_phone_endpoint_success(self):
        """Verifies /validate-phone returns 200 OK for configured permitted number."""
        with patch.dict(os.environ, self.mock_livekit_env):
            # GET with exact match
            res1 = self.client.get("/validate-phone?phone=%2B919876543210")
            self.assertEqual(res1.status_code, 200)
            self.assertTrue(res1.json()["valid"])

            # GET without '+'
            res2 = self.client.get("/validate-phone?phone=919876543210")
            self.assertEqual(res2.status_code, 200)
            self.assertTrue(res2.json()["valid"])

            # POST with JSON body
            res3 = self.client.post("/validate-phone", json={"phone": "+919876543210"})
            self.assertEqual(res3.status_code, 200)
            self.assertTrue(res3.json()["valid"])

    def test_05_validate_phone_endpoint_rejections(self):
        """Verifies /validate-phone returns 403 Forbidden with 'Invalid number' on mismatch."""
        with patch.dict(os.environ, self.mock_livekit_env):
            # Wrong number
            res1 = self.client.get("/validate-phone?phone=%2B910000000000")
            self.assertEqual(res1.status_code, 403)
            self.assertEqual(res1.json()["detail"], "Invalid number")

            # Partial match
            res2 = self.client.get("/validate-phone?phone=9876543210")
            self.assertEqual(res2.status_code, 403)
            self.assertEqual(res2.json()["detail"], "Invalid number")

            # Empty string
            res3 = self.client.get("/validate-phone?phone=")
            self.assertEqual(res3.status_code, 403)
            self.assertEqual(res3.json()["detail"], "Invalid number")

            # POST with wrong number
            res4 = self.client.post("/validate-phone", json={"phone": "+1234567890"})
            self.assertEqual(res4.status_code, 403)
            self.assertEqual(res4.json()["detail"], "Invalid number")

    # -------------------------------------------------------------------------
    # 3. LiveKit Token Issuance (/token) Phone Number Validation
    # -------------------------------------------------------------------------
    def test_06_token_issuance_with_matching_phone(self):
        """Verifies /token issues a JWT when valid phone number is supplied."""
        with patch.dict(os.environ, self.mock_livekit_env):
            res = self.client.get("/token?room=test-room&identity=caller1&phone=%2B919876543210")
            self.assertEqual(res.status_code, 200)
            data = res.json()
            self.assertIn("token", data)
            self.assertEqual(data["url"], "ws://127.0.0.1:7880")
            self.assertEqual(data["room"], "test-room")

    def test_07_token_issuance_rejects_mismatched_phone(self):
        """Verifies /token returns 403 Forbidden and denies token for non-whitelisted number."""
        with patch.dict(os.environ, self.mock_livekit_env):
            # Mismatched phone
            res1 = self.client.get("/token?room=test-room&identity=caller1&phone=%2B919999999999")
            self.assertEqual(res1.status_code, 403)
            self.assertEqual(res1.json()["detail"], "Invalid number")

            # Partial number
            res2 = self.client.get("/token?room=test-room&identity=caller1&phone=9876543210")
            self.assertEqual(res2.status_code, 403)
            self.assertEqual(res2.json()["detail"], "Invalid number")

            # Missing phone with non-matching identity
            res3 = self.client.get("/token?room=test-room&identity=caller1")
            self.assertEqual(res3.status_code, 403)
            self.assertEqual(res3.json()["detail"], "Invalid number")

    # -------------------------------------------------------------------------
    # 4. Token Server Health Probe Privacy Check
    # -------------------------------------------------------------------------
    def test_08_health_check_does_not_leak_phone(self):
        """Verifies /health reports caller configuration boolean without leaking secret phone number."""
        with patch.dict(os.environ, self.mock_livekit_env):
            res = self.client.get("/health")
            self.assertEqual(res.status_code, 200)
            data = res.json()
            self.assertTrue(data["allowed_caller_configured"])
            self.assertTrue(data["livekit_configured"])
            # Ensure the raw phone number is never in the health response
            self.assertNotIn("+919876543210", str(data))
            self.assertNotIn("ALLOWED_CALLER_NUMBER", str(data))

    # -------------------------------------------------------------------------
    # 5. LiveKit Agent Passes Validated Configured Number as user_phone
    # -------------------------------------------------------------------------
    def test_09_agent_passes_configured_phone_to_voice_engine(self):
        """Verifies the agent passes ALLOWED_CALLER_NUMBER as user_phone rather than random identity."""
        configured_number = "+919876543210"

        with patch.dict(os.environ, {"ALLOWED_CALLER_NUMBER": configured_number}):
            # Test in process_caller_audio
            with patch("backend.agent.send_audio_to_voice_engine", new_callable=AsyncMock) as mock_send:
                mock_send.return_value = {
                    "recognized_text": "namaste",
                    "ai_text_response": "kripya batayein",
                    "output_audio_base64": "",
                }
                dummy_room = MagicMock()
                dummy_source = MagicMock()

                # Call process_caller_audio with configured phone
                asyncio.run(
                    process_caller_audio(
                        room=dummy_room,
                        audio_source=dummy_source,
                        audio_bytes=b"dummy_pcm",
                        user_phone=configured_number,
                    )
                )

                # Verify send_audio_to_voice_engine was called with configured number
                mock_send.assert_called_once_with(
                    audio_bytes=b"dummy_pcm",
                    user_phone=configured_number,
                    language="en",
                )

    def test_10_agent_phone_masking(self):
        """Verifies phone number masking preserves privacy in agent logs."""
        self.assertEqual(mask_phone_number("+919876543210"), "+91XXXXXX3210")
        self.assertEqual(mask_phone_number("+15551234567"), "+15XXXXX4567")
        self.assertEqual(mask_phone_number("caller-z75pwn"), "calXXXXXX5pwn")
        self.assertEqual(mask_phone_number("unknown"), "caller-anon")
        self.assertEqual(mask_phone_number(""), "caller-anon")


if __name__ == "__main__":
    unittest.main()
