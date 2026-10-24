"""
Automated Test Suite for Multilingual ASR, Gemini LLM, Caller Isolation, and Voice Routing.

Test Coverage:
1. Groq ASR provider initialization & transcription.
2. Groq ASR circuit-breaker fallback to LocalWhisperASR on HTTP 429, timeout, and missing key.
3. Google Gemini conversational LLM reasoning & clean speakable formatting (no markdown/bullets).
4. Google Gemini quota exhaustion (HTTP 429) and timeout fallback to offline domain router.
5. Strict caller session isolation across distinct telephone numbers.
6. Dynamic script language detection and neural Edge-TTS voice routing (Kannada, Hindi, English).
7. End-to-end Voice Engine turn with multilingual response preservation.
8. Text response preservation on TTS synthesis failure.
"""

import asyncio
import base64
import os
import unittest
from unittest.mock import AsyncMock, MagicMock, patch
import httpx
from fastapi.testclient import TestClient

from app.core.config import Settings
from app.main import app, detect_script_language, get_asr_service
from app.services.ai_agent import (
    CallerSessionManager,
    clean_voice_text,
    caller_sessions,
    query_ai_agent,
    query_gemini_llm,
)
from app.services.free_speech_service import EdgeTTSService, LocalWhisperASR
from app.services.groq_speech_service import GroqWhisperASR


class TestMultilingualLLMPipeline(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.client = TestClient(app)
        cls.test_phone_a = "+919876543210"
        cls.test_phone_b = "+911234567891"

        # Generate a small 0.5s valid 16kHz mono WAV for audio payloads
        import io, wave
        wav_buf = io.BytesIO()
        with wave.open(wav_buf, "wb") as wf:
            wf.setnchannels(1)
            wf.setsampwidth(2)
            wf.setframerate(16000)
            wf.writeframes(b"\x00\x00" * 8000)
        cls.sample_wav_bytes = wav_buf.getvalue()
        cls.sample_wav_b64 = base64.b64encode(cls.sample_wav_bytes).decode("utf-8")

    def setUp(self):
        caller_sessions.reset_all()

    def tearDown(self):
        caller_sessions.reset_all()

    # -------------------------------------------------------------------------
    # 1. Groq ASR Provider Selection & Fallback Behavior
    # -------------------------------------------------------------------------
    def test_01_groq_asr_transcribe_success(self):
        """Verifies GroqWhisperASR sends audio to Groq API and parses transcription."""
        async def run_test():
            groq_asr = GroqWhisperASR(
                api_key="gsk_test_mock_key",
                model_name="whisper-large-v3-turbo",
            )

            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.json.return_value = {
                "text": "ಟೊಮ್ಯಾಟೊ ಬೆಳೆ ರೋಗ ನಿಯಂತ್ರಣ ಹೇಗೆ?",
            }

            with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
                mock_post.return_value = mock_response
                result = await groq_asr.transcribe(self.sample_wav_bytes, language="auto")
                self.assertEqual(result, "ಟೊಮ್ಯಾಟೊ ಬೆಳೆ ರೋಗ ನಿಯಂತ್ರಣ ಹೇಗೆ?")
                self.assertTrue(mock_post.called)
                _, kwargs = mock_post.call_args
                # Verify language is omitted for 'auto' so Groq detects language automatically
                self.assertNotIn("language", kwargs.get("data", {}))

        asyncio.run(run_test())

    def test_02_groq_asr_rate_limit_429_activates_local_fallback(self):
        """Verifies GroqWhisperASR automatically falls back to LocalWhisperASR on HTTP 429."""
        async def run_test():
            mock_fallback = MagicMock()
            mock_fallback.transcribe = AsyncMock(return_value="स्थानीय फॉलबैक प्रतिलेखन")

            groq_asr = GroqWhisperASR(
                api_key="gsk_test_key",
                fallback_asr=mock_fallback,
            )

            mock_response = MagicMock()
            mock_response.status_code = 429
            mock_response.text = "Rate limit reached"

            with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
                mock_post.return_value = mock_response
                result = await groq_asr.transcribe(self.sample_wav_bytes, language="hi")
                self.assertEqual(result, "स्थानीय फॉलबैक प्रतिलेखन")
                mock_fallback.transcribe.assert_awaited_once_with(self.sample_wav_bytes, "hi")

        asyncio.run(run_test())

    def test_03_groq_asr_timeout_activates_local_fallback(self):
        """Verifies GroqWhisperASR falls back to local Whisper when the request times out."""
        async def run_test():
            mock_fallback = MagicMock()
            mock_fallback.transcribe = AsyncMock(return_value="fallback on timeout")

            groq_asr = GroqWhisperASR(
                api_key="gsk_test_key",
                fallback_asr=mock_fallback,
            )

            with patch("httpx.AsyncClient.post", side_effect=httpx.TimeoutException("timeout")):
                result = await groq_asr.transcribe(self.sample_wav_bytes, language="en")
                self.assertEqual(result, "fallback on timeout")
                mock_fallback.transcribe.assert_awaited_once_with(self.sample_wav_bytes, "en")

        asyncio.run(run_test())

    def test_04_groq_asr_missing_key_activates_local_fallback(self):
        """Verifies GroqWhisperASR immediately uses fallback when no API key is configured."""
        async def run_test():
            mock_fallback = MagicMock()
            mock_fallback.transcribe = AsyncMock(return_value="fallback without key")

            groq_asr = GroqWhisperASR(
                api_key="",
                fallback_asr=mock_fallback,
            )

            result = await groq_asr.transcribe(self.sample_wav_bytes, language="kn")
            self.assertEqual(result, "fallback without key")
            mock_fallback.transcribe.assert_awaited_once_with(self.sample_wav_bytes, "kn")

        asyncio.run(run_test())

    # -------------------------------------------------------------------------
    # 2. Conversational LLM (Google Gemini) Reasoning & Output Cleaning
    # -------------------------------------------------------------------------
    def test_05_clean_voice_text_strips_markdown_and_bullets(self):
        """Verifies clean_voice_text purges markdown formatting, asterisks, and bullet points."""
        markdown_text = (
            "**Kisan Samman Nidhi:**\n"
            "* Installment release on 15th.\n"
            "# Check status at portal.\n"
            "• Keep e-KYC updated!"
        )
        cleaned = clean_voice_text(markdown_text)
        self.assertNotIn("*", cleaned)
        self.assertNotIn("#", cleaned)
        self.assertNotIn("•", cleaned)
        self.assertNotIn("\n", cleaned)
        self.assertIn("Kisan Samman Nidhi", cleaned)
        self.assertIn("Keep e-KYC updated", cleaned)

    def test_06_gemini_query_success_and_history_recording(self):
        """Verifies Gemini returns concise conversational answer and updates caller history."""
        async def run_test():
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.json.return_value = {
                "candidates": [
                    {
                        "content": {
                            "parts": [
                                {
                                    "text": "ಟೊಮ್ಯಾಟೊ ಎಲೆ ಸುರುಟು ರೋಗಕ್ಕೆ ಬೇವಿನ ಎಣ್ಣೆ ಸಿಂಪಡಿಸಿ. ಕೀಟನಾಶಕ ಬಳಸುವ ಮುನ್ನ ಕೃಷಿ ಅಧಿಕಾರಿಯನ್ನು ಸಂಪರ್ಕಿಸಿ."
                                }
                            ]
                        }
                    }
                ]
            }

            with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
                mock_post.return_value = mock_response
                reply = await query_gemini_llm(
                    text_query="ಟೊಮ್ಯಾಟೊ ರೋಗಕ್ಕೆ ಏನು ಮಾಡಬೇಕು?",
                    phone=self.test_phone_a,
                    api_key="gemini_mock_key",
                )

                self.assertIsNotNone(reply)
                self.assertIn("ಟೊಮ್ಯಾಟೊ", reply)

                # Check that caller history was recorded
                history = caller_sessions.get_history(self.test_phone_a)
                self.assertEqual(len(history), 2)
                self.assertEqual(history[0]["role"], "user")
                self.assertEqual(history[0]["text"], "ಟೊಮ್ಯಾಟೊ ರೋಗಕ್ಕೆ ಏನು ಮಾಡಬೇಕು?")
                self.assertEqual(history[1]["role"], "model")
                self.assertEqual(history[1]["text"], reply)

        asyncio.run(run_test())

    # -------------------------------------------------------------------------
    # 3. Caller Session Isolation (Privacy Mandate)
    # -------------------------------------------------------------------------
    def test_07_caller_session_isolation(self):
        """Verifies distinct phone numbers maintain isolated conversation contexts."""
        manager = CallerSessionManager(max_history_turns=6)

        manager.add_turn(self.test_phone_a, "user", "Phone A query 1")
        manager.add_turn(self.test_phone_a, "model", "Phone A response 1")

        manager.add_turn(self.test_phone_b, "user", "Phone B query 1")

        history_a = manager.get_history(self.test_phone_a)
        history_b = manager.get_history(self.test_phone_b)

        self.assertEqual(len(history_a), 2)
        self.assertEqual(len(history_b), 1)

        # Phone B must not see Phone A's data
        self.assertEqual(history_a[0]["text"], "Phone A query 1")
        self.assertEqual(history_b[0]["text"], "Phone B query 1")
        self.assertNotIn("Phone A", [t["text"] for t in history_b])

    def test_08_caller_session_sliding_window_bound(self):
        """Verifies caller session does not exceed max_history_turns."""
        manager = CallerSessionManager(max_history_turns=4)

        for i in range(10):
            manager.add_turn(self.test_phone_a, "user", f"Turn {i}")

        history = manager.get_history(self.test_phone_a)
        self.assertEqual(len(history), 4)
        self.assertEqual(history[-1]["text"], "Turn 9")
        self.assertEqual(history[0]["text"], "Turn 6")

    # -------------------------------------------------------------------------
    # 4. Gemini Quota Limit (429) & Failure Fallback to Intent Router
    # -------------------------------------------------------------------------
    def test_09_gemini_429_quota_exhaustion_falls_back_to_intent_router(self):
        """Verifies HTTP 429 from Gemini triggers graceful offline intent fallback."""
        async def run_test():
            mock_response = MagicMock()
            mock_response.status_code = 429
            mock_response.text = '{"error": {"code": 429, "message": "Resource exhausted"}}'

            with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
                mock_post.return_value = mock_response

                with patch.dict(os.environ, {"GEMINI_API_KEY": "fake_key", "LLM_PROVIDER": "gemini"}):
                    # Query about Kisan Samman Nidhi
                    reply = await query_ai_agent(
                        text_query="PM Kisan samman nidhi kist kab aayegi?",
                        phone=self.test_phone_a,
                    )
                    # Must fall back to deterministic domain response
                    self.assertIn("kisan samman nidhi", reply.lower())

        asyncio.run(run_test())

    # -------------------------------------------------------------------------
    # 5. Dynamic Script Detection & Neural TTS Voice Routing
    # -------------------------------------------------------------------------
    def test_10_detect_script_language_kannada(self):
        """Verifies Kannada Unicode text routes to 'kn'."""
        kannada_text = "ನಮಸ್ಕಾರ, ನಿಮ್ಮ ಪ್ರಶ್ನೆಗೆ ಇಲ್ಲಿದೆ ಮಾಹಿತಿ."
        self.assertEqual(detect_script_language(kannada_text), "kn")

    def test_11_detect_script_language_hindi(self):
        """Verifies Devanagari Unicode text routes to 'hi'."""
        hindi_text = "नमस्ते, आपकी फसल के लिए यह खाद उपयुक्त है।"
        self.assertEqual(detect_script_language(hindi_text), "hi")

    def test_12_detect_script_language_english(self):
        """Verifies Latin script text defaults to 'en'."""
        english_text = "Hello, tomato market prices are currently stable."
        self.assertEqual(detect_script_language(english_text), "en")

    def test_13_edge_tts_voice_mapping_kannada_hindi_english(self):
        """Verifies EdgeTTSService selects the appropriate neural voices."""
        tts = EdgeTTSService()
        self.assertEqual(tts.get_voice_for_language("kn"), "kn-IN-GaganNeural")
        self.assertEqual(tts.get_voice_for_language("hi"), "hi-IN-SwaraNeural")
        self.assertEqual(tts.get_voice_for_language("en"), "en-IN-NeerjaNeural")

    # -------------------------------------------------------------------------
    # 6. End-to-End Voice Turn Integration & TTS Failure Handling
    # -------------------------------------------------------------------------
    def test_14_end_to_end_voice_turn_with_groq_and_gemini_mocks(self):
        """Verifies /process-voice-turn handles mock Groq ASR and mock Gemini reasoning."""
        mock_asr = MagicMock()
        mock_asr.transcribe = AsyncMock(return_value="टमाटर का रोग कैसे ठीक करें?")

        mock_tts = MagicMock()
        mock_tts.synthesize = AsyncMock(return_value="b64synthesizedaudio==")

        with patch("app.main.get_asr_service", return_value=mock_asr):
            with patch("app.main.get_tts_service", return_value=mock_tts):
                with patch("app.main.query_ai_agent", new_callable=AsyncMock) as mock_ai:
                    mock_ai.return_value = "टमाटर में नीम का तेल छिड़कें और मिट्टी की नमी बनाए रखें।"

                    payload = {
                        "user_phone": self.test_phone_a,
                        "audio_base64": self.sample_wav_b64,
                        "language": "auto",
                        "sample_rate": 16000,
                    }

                    response = self.client.post("/process-voice-turn", json=payload)
                    self.assertEqual(response.status_code, 200)

                    data = response.json()
                    self.assertEqual(data["status"], "success")
                    self.assertEqual(data["recognized_text"], "टमाटर का रोग कैसे ठीक करें?")
                    self.assertIn("नीम का तेल", data["ai_text_response"])
                    self.assertEqual(data["output_audio_base64"], "b64synthesizedaudio==")
                    self.assertGreater(data["processing_time_ms"], 0)

    def test_15_tts_synthesis_failure_preserves_text_response(self):
        """Verifies that if Edge-TTS fails, the turn succeeds with 200 OK and preserves text."""
        mock_asr = MagicMock()
        mock_asr.transcribe = AsyncMock(return_value="मौसम कैसा रहेगा?")

        mock_tts = MagicMock()
        mock_tts.synthesize = AsyncMock(side_effect=RuntimeError("Edge-TTS network error"))

        with patch("app.main.get_asr_service", return_value=mock_asr):
            with patch("app.main.get_tts_service", return_value=mock_tts):
                with patch("app.main.query_ai_agent", new_callable=AsyncMock) as mock_ai:
                    mock_ai.return_value = "अगले दो दिनों तक मौसम साफ रहेगा।"

                    payload = {
                        "user_phone": self.test_phone_a,
                        "audio_base64": self.sample_wav_b64,
                        "language": "hi",
                        "sample_rate": 16000,
                    }

                    response = self.client.post("/process-voice-turn", json=payload)
                    self.assertEqual(response.status_code, 200)

                    data = response.json()
                    self.assertEqual(data["status"], "success")
                    self.assertEqual(data["recognized_text"], "मौसम कैसा रहेगा?")
                    self.assertEqual(data["ai_text_response"], "अगले दो दिनों तक मौसम साफ रहेगा।")
                    # Audio string must be empty when TTS fails, but turn must succeed
                    self.assertEqual(data["output_audio_base64"], "")


if __name__ == "__main__":
    unittest.main()
