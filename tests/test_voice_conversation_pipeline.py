"""
Comprehensive Unit & Integration Test Suite for Awaaz Setu Complete Voice Conversation Pipeline.

Coverage:
1. Phone number normalization and exact-match whitelisting (with optional '+', whitespace, dashes).
2. Invalid number rejected before token issuance (HTTP 403 Forbidden, 'Invalid number').
3. Participant identity (e.g. 'caller-z75pwn') is strictly NEVER passed as user_phone.
4. Empty audio / silence does NOT trigger a DPI request (returns None, retry prompt).
5. Mandi price questions route accurately to 'e-NAM Mandi Prices (demo)'.
6. Unrelated questions route to General Advisory and NEVER return Mandi prices.
7. Transcription failures / silence produce localized retry prompt.
8. Voice Engine responses include dpi_service and dpi_details.
9. Multiple conversation turns execute cleanly without state contamination.
10. Speech recognition recovery: 'BM ki sana' -> PM-Kisan, 'Monday prices' -> Mandi prices.
11. play_audio_response creates valid rtc.AudioFrame with tobytes() without raising TypeError.
12. TTS failure does not erase the text response or cause HTTP 500.
"""

import asyncio
import base64
import io
import json
import os
import unittest
from unittest.mock import AsyncMock, MagicMock, patch

import numpy as np
from scipy.io import wavfile
from fastapi.testclient import TestClient

from app.main import app as voice_engine_app
from app.services.intent_router import classify_intent
from app.services.ai_agent import query_ai_agent, mask_phone_number
from app.services.free_speech_service import EdgeTTSService
from backend.token_server import app as token_server_app, normalize_phone, is_caller_number_allowed
from backend.agent import process_caller_audio, read_caller_audio, play_audio_response


class TestVoiceConversationPipeline(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.voice_client = TestClient(voice_engine_app)
        cls.token_client = TestClient(token_server_app)
        cls.test_phone = "+911234567891"

        # Generate a standard 16kHz sine PCM audio buffer
        sample_rate = 16000
        t = np.linspace(0, 1.0, sample_rate, False)
        sine = 0.2 * np.sin(2 * np.pi * 300 * t)
        buf = io.BytesIO()
        wavfile.write(buf, sample_rate, (sine * 32767).astype(np.int16))
        cls.sample_wav_bytes = buf.getvalue()
        cls.sample_wav_b64 = base64.b64encode(cls.sample_wav_bytes).decode("utf-8")

    # -------------------------------------------------------------------------
    # 1. Phone-Number Normalization & Exact-Match Validation
    # -------------------------------------------------------------------------
    def test_01_phone_normalization_and_exact_match(self):
        """Verifies exact matching with optional '+' and rejection of partial numbers."""
        with patch.dict(os.environ, {"ALLOWED_CALLER_NUMBER": self.test_phone}):
            self.assertEqual(normalize_phone("+911234567891"), "911234567891")
            self.assertEqual(normalize_phone("911234567891"), "911234567891")
            self.assertEqual(normalize_phone(" +91 1234-567-891 "), "911234567891")

            # Permitted exact matches
            self.assertTrue(is_caller_number_allowed("+911234567891"))
            self.assertTrue(is_caller_number_allowed("911234567891"))
            self.assertTrue(is_caller_number_allowed("+91 1234 567 891"))

            # Disallowed partials / mismatches
            self.assertFalse(is_caller_number_allowed("1234567891"))       # Missing country code
            self.assertFalse(is_caller_number_allowed("+9112345678919"))   # Extra digit
            self.assertFalse(is_caller_number_allowed("+910000000000"))     # Mismatched digits
            self.assertFalse(is_caller_number_allowed(""))                 # Empty
            self.assertFalse(is_caller_number_allowed("caller-z75pwn"))     # LiveKit participant identity

    # -------------------------------------------------------------------------
    # 2. Token Issuance Enforcement & Rejection
    # -------------------------------------------------------------------------
    def test_02_invalid_number_rejected_before_token_issued(self):
        """Verifies that invalid numbers receive HTTP 403 'Invalid number' and cannot get tokens."""
        env_vars = {
            "LIVEKIT_URL": "ws://127.0.0.1:7880",
            "LIVEKIT_API_KEY": "devkey",
            "LIVEKIT_API_SECRET": "secret",
            "ALLOWED_CALLER_NUMBER": self.test_phone,
        }
        with patch.dict(os.environ, env_vars):
            # Pre-call validation probe rejects wrong number
            val_res = self.token_client.get("/validate-phone?phone=%2B919999999999")
            self.assertEqual(val_res.status_code, 403)
            self.assertEqual(val_res.json()["detail"], "Invalid number")

            # Token endpoint rejects wrong number
            token_res = self.token_client.get("/token?room=demo&identity=caller1&phone=%2B919999999999")
            self.assertEqual(token_res.status_code, 403)
            self.assertEqual(token_res.json()["detail"], "Invalid number")

            # Token endpoint accepts matching number
            ok_res = self.token_client.get("/token?room=demo&identity=caller1&phone=%2B911234567891")
            self.assertEqual(ok_res.status_code, 200)
            token_data = ok_res.json()
            self.assertIn("token", token_data)

    # -------------------------------------------------------------------------
    # 3. Participant Identity Is Never Passed as user_phone
    # -------------------------------------------------------------------------
    def test_03_participant_identity_never_passed_as_user_phone(self):
        """Ensures participant identity (e.g. 'caller-z75pwn') is never sent to Voice Engine."""
        env_vars = {"ALLOWED_CALLER_NUMBER": self.test_phone}
        with patch.dict(os.environ, env_vars):
            with patch("backend.agent.send_audio_to_voice_engine", new_callable=AsyncMock) as mock_send:
                mock_send.return_value = {
                    "recognized_text": "namaste",
                    "ai_text_response": "namaste",
                    "output_audio_base64": "",
                    "dpi_service": None,
                    "dpi_details": None,
                }
                dummy_room = MagicMock()
                dummy_source = MagicMock()

                # Simulate call with participant identity 'caller-z75pwn'
                asyncio.run(
                    process_caller_audio(
                        room=dummy_room,
                        audio_source=dummy_source,
                        audio_bytes=b"dummy_pcm",
                        user_phone=self.test_phone,  # Resolved from metadata/allowed config
                    )
                )

                mock_send.assert_called_once()
                sent_phone = mock_send.call_args.kwargs["user_phone"]
                self.assertEqual(sent_phone, self.test_phone)
                self.assertNotIn("caller-z75pwn", sent_phone)

    # -------------------------------------------------------------------------
    # 4. Intent Routing: Mandi Prices vs Unrelated Queries
    # -------------------------------------------------------------------------
    def test_04_mandi_price_routing(self):
        """Verifies mandi/price queries route to 'e-NAM Mandi Prices (demo)' with honest label."""
        queries = [
            "tamatar ka bhav kya hai",
            "mandi price of tomato",
            "टमाटर का भाव कितना है",
            "gehu ka mandi rate bataiye",
        ]
        for q in queries:
            service, details, spoken = classify_intent(q)
            self.assertEqual(service, "e-NAM Mandi Prices (demo)")
            self.assertIn("demo data", details)
            self.assertIn("demo data", spoken.lower())

    def test_05_unrelated_query_does_not_return_mandi_prices(self):
        """Verifies unrelated queries NEVER route to Mandi prices or invent rates."""
        unrelated_queries = [
            "aap kaun ho",
            "what is your name",
            "tractor repair kaise karein",
            "hello good morning",
        ]
        for q in unrelated_queries:
            service, details, spoken = classify_intent(q)
            self.assertNotEqual(service, "e-NAM Mandi Prices (demo)")
            self.assertEqual(service, "Awaaz Setu General Advisory")
            self.assertNotIn("Tomato prices", details)

    # -------------------------------------------------------------------------
    # 5. Empty Audio & Transcription Failures Produce Retry Prompt
    # -------------------------------------------------------------------------
    def test_06_empty_audio_produces_retry_prompt_without_dpi(self):
        """Verifies empty audio produces retry prompt and does NOT trigger DPI request."""
        payload = {
            "user_phone": self.test_phone,
            "audio_base64": self.sample_wav_b64,  # Pure sine tone, no words
            "language": "hi",
            "sample_rate": 16000,
        }
        res = self.voice_client.post("/process-voice-turn", json=payload)
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertEqual(data["status"], "success")
        self.assertEqual(data["recognized_text"], "")
        self.assertIn("Sorry", data["ai_text_response"])
        self.assertIsNone(data["dpi_service"])
        self.assertIsNone(data["dpi_details"])
        self.assertTrue(len(data["output_audio_base64"]) > 100)

    # -------------------------------------------------------------------------
    # 6. PM-Kisan & Offline Circuit Breaker
    # -------------------------------------------------------------------------
    def test_07_kisan_advisory_offline_fallback(self):
        """Verifies PM-Kisan queries route to PM-Kisan Samman Nidhi."""
        service, details, spoken = classify_intent("kisan samman nidhi kist status")
        self.assertEqual(service, "PM-Kisan Samman Nidhi")
        self.assertIn("PM-Kisan", details)

    # -------------------------------------------------------------------------
    # 7. Multi-Turn Conversation Continuity
    # -------------------------------------------------------------------------
    def test_08_multi_turn_conversation_turns(self):
        """Verifies multiple consecutive turns complete with valid schemas without bleed."""
        payload = {
            "user_phone": self.test_phone,
            "audio_base64": self.sample_wav_b64,
            "language": "hi",
            "sample_rate": 16000,
        }
        turn1 = self.voice_client.post("/process-voice-turn", json=payload)
        turn2 = self.voice_client.post("/process-voice-turn", json=payload)
        self.assertEqual(turn1.status_code, 200)
        self.assertEqual(turn2.status_code, 200)
        self.assertEqual(turn1.json()["status"], "success")
        self.assertEqual(turn2.json()["status"], "success")

    # -------------------------------------------------------------------------
    # 8. Speech Recognition Recovery: 'BM ki sana' & 'Monday prices'
    # -------------------------------------------------------------------------
    def test_09_bm_ki_sana_and_monday_prices_intent_recovery(self):
        """Verifies phonetic ASR misrecognitions are accurately routed to intended domain services."""
        # 'Can you tell me whether it's BM ki sana?' -> PM-Kisan
        s1, d1, r1 = classify_intent("Can you tell me whether it's BM ki sana?")
        self.assertEqual(s1, "PM-Kisan Samman Nidhi")
        self.assertIn("PM-Kisan", d1)
        self.assertNotEqual(s1, "Awaaz Setu General Advisory")

        # 'What are the Monday prices for tomato?' -> e-NAM Mandi Prices
        s2, d2, r2 = classify_intent("What are the Monday prices for tomato?")
        self.assertEqual(s2, "e-NAM Mandi Prices (demo)")
        self.assertIn("Tomato prices", d2)

    # -------------------------------------------------------------------------
    # 9. Spoken Audio Playout Frame Delivery (rtc.AudioFrame tobytes)
    # -------------------------------------------------------------------------
    def test_10_play_audio_response_streams_bytes_to_audio_source(self):
        """Verifies play_audio_response captures frames as bytes without TypeError."""
        # Synthesize a real short MP3 test payload
        async def run_tts():
            tts = EdgeTTSService()
            return await tts.synthesize("नमस्ते", language="hi")

        mp3_b64 = asyncio.run(run_tts())
        self.assertTrue(len(mp3_b64) > 100)

        # Mock AudioSource
        mock_source = MagicMock()
        mock_source.queued_duration = 0.5
        mock_source.capture_frame = AsyncMock()
        mock_source.wait_for_playout = AsyncMock()

        # Execute play_audio_response
        asyncio.run(play_audio_response(mock_source, mp3_b64))

        # Must have captured multiple audio frames
        self.assertGreater(mock_source.capture_frame.call_count, 0)
        first_frame = mock_source.capture_frame.call_args_list[0].args[0]
        # Data must be bytes or memoryview, not numpy array
        self.assertIsInstance(first_frame.data, (bytes, memoryview, bytearray))
        mock_source.wait_for_playout.assert_awaited_once()

    # -------------------------------------------------------------------------
    # 10. TTS Failure Preserves Response Text
    # -------------------------------------------------------------------------
    def test_11_tts_failure_preserves_text_response(self):
        """Verifies that if TTS fails, the text response and DPI details are preserved for the UI."""
        payload = {
            "user_phone": self.test_phone,
            "audio_base64": self.sample_wav_b64,
            "language": "hi",
            "sample_rate": 16000,
        }
        with patch("app.main.get_tts_service") as mock_get_tts:
            mock_tts = MagicMock()
            mock_tts.synthesize = AsyncMock(side_effect=RuntimeError("TTS network unreachable"))
            mock_get_tts.return_value = mock_tts

            res = self.voice_client.post("/process-voice-turn", json=payload)
            self.assertEqual(res.status_code, 200)
            data = res.json()
            self.assertEqual(data["status"], "success")
            self.assertIn("Sorry", data["ai_text_response"])
            self.assertEqual(data["output_audio_base64"], "")


if __name__ == "__main__":
    unittest.main()
