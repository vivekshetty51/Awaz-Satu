"""
Offline tests for the English-only policy and the faster-whisper ASR wrapper.

Covers:
1. Language policy: English forced by default, regional languages when disabled.
2. English spoken replies (no Devanagari/Kannada) from the intent router.
3. LocalWhisperASR on faster-whisper: language forcing, segment joining, VAD options,
   missing-package error, and no temp-file audio retention.
4. Gemini voice prompt follows the language policy.
"""
import asyncio
import os
import re
import unittest
from types import SimpleNamespace
from unittest.mock import patch

import numpy as np

from app.core.language import english_only, resolve_language
from app.services import free_speech_service
from app.services.ai_agent import DEFAULT_MOCK_RESPONSE, build_voice_system_prompt
from app.services.free_speech_service import AGRICULTURAL_PROMPT, LocalWhisperASR
from app.services.intent_router import PM_KISAN_SPOKEN, classify_intent

INDIC = re.compile(r"[\u0900-\u097F\u0C80-\u0CFF]")


class FakeModel:
    """Stands in for faster_whisper.WhisperModel; transcribe() returns (generator, info)."""

    def __init__(self, texts):
        self.texts = texts
        self.kwargs = None

    def transcribe(self, audio, **kwargs):
        self.kwargs = kwargs
        return (SimpleNamespace(text=t) for t in self.texts), SimpleNamespace(language="en")


def make_asr(model_name="base.en", texts=(" hello ", "world ")):
    asr = LocalWhisperASR(model_name=model_name)
    asr._model = FakeModel(list(texts))
    return asr


class TestLanguagePolicy(unittest.TestCase):
    def test_english_forced_by_default(self):
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("ENGLISH_ONLY", None)
            self.assertTrue(english_only())
            for requested in ("hi", "kn", "auto", "", None, "EN"):
                self.assertEqual(resolve_language(requested), "en")

    def test_regional_languages_when_disabled(self):
        with patch.dict(os.environ, {"ENGLISH_ONLY": "false"}):
            self.assertFalse(english_only())
            self.assertEqual(resolve_language(" KN "), "kn")
            self.assertEqual(resolve_language(""), "en")


class TestEnglishReplies(unittest.TestCase):
    QUERIES = ["tomato price", "pm kisan installment", "cow vaccination",
               "weather tomorrow", "hello there", ""]

    def test_spoken_replies_are_english(self):
        for q in self.QUERIES:
            _service, _details, spoken = classify_intent(q)
            self.assertTrue(spoken.strip(), q)
            self.assertIsNone(INDIC.search(spoken), f"non-English reply for {q!r}: {spoken}")

    def test_offline_fallback_text_matches_default_response(self):
        self.assertEqual(DEFAULT_MOCK_RESPONSE, PM_KISAN_SPOKEN)
        self.assertIn("kisan samman nidhi", PM_KISAN_SPOKEN.lower())

    def test_no_invented_installment_date(self):
        self.assertNotRegex(PM_KISAN_SPOKEN, r"\b15\b")

    def test_voice_prompt_follows_policy(self):
        with patch.dict(os.environ, {"ENGLISH_ONLY": "true"}):
            self.assertIn("English only", build_voice_system_prompt())
        with patch.dict(os.environ, {"ENGLISH_ONLY": "false"}):
            self.assertIn("SAME language", build_voice_system_prompt())


class TestFasterWhisperASR(unittest.TestCase):
    def run_asr(self, asr, language):
        with patch.object(LocalWhisperASR, "_audio_bytes_to_np_array",
                          return_value=np.zeros(16000, dtype=np.float32)):
            return asyncio.run(asr.transcribe(b"fake-wav", language=language))

    def test_joins_segments_and_strips(self):
        self.assertEqual(self.run_asr(make_asr(), "en"), "hello world")

    def test_english_checkpoint_forces_english(self):
        asr = make_asr("base.en")
        self.run_asr(asr, "hi")
        self.assertEqual(asr._model.kwargs["language"], "en")

    def test_multilingual_model_respects_language_and_auto(self):
        asr = make_asr("base")
        self.run_asr(asr, "kn")
        self.assertEqual(asr._model.kwargs["language"], "kn")
        self.run_asr(asr, "auto")
        self.assertIsNone(asr._model.kwargs["language"])

    def test_low_latency_and_silence_options(self):
        asr = make_asr()
        self.run_asr(asr, "en")
        kw = asr._model.kwargs
        self.assertTrue(kw["vad_filter"])
        self.assertEqual(kw["beam_size"], 1)
        self.assertFalse(kw["condition_on_previous_text"])
        self.assertEqual(kw["initial_prompt"], AGRICULTURAL_PROMPT)

    def test_silence_returns_empty_string(self):
        self.assertEqual(self.run_asr(make_asr(texts=[]), "en"), "")

    def test_missing_package_gives_clear_error(self):
        asr = LocalWhisperASR(model_name="base.en")
        with patch.object(free_speech_service, "WhisperModel", None):
            with self.assertRaises(RuntimeError) as ctx:
                asyncio.run(asr.transcribe(b"x", language="en"))
        self.assertIn("faster-whisper is not installed", str(ctx.exception))

    def test_empty_audio_rejected(self):
        with self.assertRaises(ValueError):
            asyncio.run(make_asr().transcribe(b"", language="en"))

    def test_no_temp_file_audio_retention(self):
        self.assertFalse(hasattr(free_speech_service, "tempfile"))


if __name__ == "__main__":
    unittest.main()
