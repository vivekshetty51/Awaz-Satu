"""
Offline tests for the crawler filters and the quota-safe embedding client
(no network, no API keys, no sleeping).
"""
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import httpx
import numpy as np

from app.rag import embeddings
from app.rag.config import RagSettings
from app.rag.embeddings import GeminiEmbedder
from app.rag import retriever
from app.rag.eval import recommend_threshold
from app.rag.ingest import indic_ratio, load_local_docs, same_site, should_skip_url


class TestCrawlFilters(unittest.TestCase):
    def test_indic_ratio(self):
        self.assertEqual(indic_ratio("Old age pension for senior citizens"), 0.0)
        self.assertGreater(indic_ratio("ಸಂಧ್ಯಾ ಸುರಕ್ಷಾ ಯೋಜನೆ pension"), 0.5)
        self.assertGreater(indic_ratio("वृद्धावस्था पेंशन"), 0.9)
        self.assertEqual(indic_ratio("12345 !!!"), 0.0)

    def test_skip_binaries_and_login_pages(self):
        for u in ("https://x.karnataka.gov.in/setup.exe", "https://x.karnataka.gov.in/a.JPG",
                  "https://ahara.karnataka.gov.in/FCSOFFICE_BSERVER/login.aspx",
                  "https://s.karnataka.gov.in/directApply.do?serviceId=1"):
            self.assertTrue(should_skip_url(u), u)
        for u in ("https://ssp.karnataka.gov.in/", "https://x.karnataka.gov.in/scheme.pdf"):
            self.assertFalse(should_skip_url(u), u)

    def test_same_site_ignores_www_but_not_other_hosts(self):
        seed = "https://www.karnataka.gov.in/"
        self.assertTrue(same_site("https://karnataka.gov.in/department/kn", seed))
        self.assertFalse(same_site("https://cm.karnataka.gov.in/", seed))


class TestLocalOfficialDocs(unittest.TestCase):
    PARA = ("Sandhya Suraksha pension is paid monthly to eligible senior citizens of Karnataka. "
            "Applicants apply through the Tahsildar office or the Seva Sindhu portal.")

    def settings(self, d):
        return RagSettings(local_docs_dir=Path(d))

    def test_valid_doc_is_chunked_with_its_source_url(self):
        with tempfile.TemporaryDirectory() as d:
            (Path(d) / "pension.txt").write_text(
                "Source: https://dssp.karnataka.gov.in/dssp/home_page.aspx\n\n" + self.PARA, encoding="utf-8")
            chunks = load_local_docs(self.settings(d))
        self.assertEqual(len(chunks), 1)
        self.assertEqual(chunks[0].url, "https://dssp.karnataka.gov.in/dssp/home_page.aspx")
        self.assertIn("Sandhya Suraksha", chunks[0].text)

    def test_non_government_source_is_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            (Path(d) / "blog.txt").write_text("Source: https://example.com/post\n\n" + self.PARA, encoding="utf-8")
            (Path(d) / "lookalike.txt").write_text(
                "Source: https://karnataka.gov.in.evil.com/x\n\n" + self.PARA, encoding="utf-8")
            self.assertEqual(load_local_docs(self.settings(d)), [])

    def test_missing_source_line_underscore_and_other_types_are_skipped(self):
        with tempfile.TemporaryDirectory() as d:
            (Path(d) / "nosource.txt").write_text(self.PARA, encoding="utf-8")
            (Path(d) / "_template.txt").write_text(
                "Source: https://karnataka.gov.in/\n\n" + self.PARA, encoding="utf-8")
            (Path(d) / "page.pdf").write_bytes(b"%PDF")
            self.assertEqual(load_local_docs(self.settings(d)), [])

    def test_missing_folder_is_fine(self):
        self.assertEqual(load_local_docs(RagSettings(local_docs_dir=Path("/nonexistent-rag-docs"))), [])


class GenResponse:
    def __init__(self, status=200, text="ok"):
        self.status_code = status
        self._text = text

    def raise_for_status(self):
        if self.status_code >= 400:
            raise httpx.HTTPStatusError("err", request=None, response=self)

    def json(self):
        return {"candidates": [{"content": {"parts": [{"text": self._text}]}}]} if self._text is not None else {}


class FakeAsyncClient:
    script: list = []
    urls: list = []

    def __init__(self, *a, **k):
        pass

    async def __aenter__(self):
        return self

    async def __aexit__(self, *a):
        return False

    async def post(self, url, json=None, headers=None):
        type(self).urls.append(url)
        return type(self).script.pop(0)


def run_generate(script, **settings):
    import asyncio
    real_sleep = asyncio.sleep                      # keep a handle: patching replaces the global
    FakeAsyncClient.script, FakeAsyncClient.urls = list(script), []
    s = RagSettings(gemini_api_key="k", generation_model="primary-model",
                    fallback_models=("fallback-model",), **settings)
    with patch.object(retriever.httpx, "AsyncClient", FakeAsyncClient), \
         patch.object(retriever.asyncio, "sleep", new=lambda *_: real_sleep(0)):
        return asyncio.run(retriever.GeminiGenerator(s)("sys", "prompt"))


class TestGeneratorFailover(unittest.TestCase):
    def test_503_then_success_retries_same_model_once(self):
        out = run_generate([GenResponse(503), GenResponse(200, "answer")])
        self.assertEqual(out, "answer")
        self.assertTrue(all("primary-model" in u for u in FakeAsyncClient.urls))

    def test_persistent_503_switches_to_fallback_model(self):
        out = run_generate([GenResponse(503), GenResponse(503), GenResponse(200, "from fallback")])
        self.assertEqual(out, "from fallback")
        self.assertIn("fallback-model", FakeAsyncClient.urls[-1])

    def test_quota_429_switches_immediately_without_retry(self):
        out = run_generate([GenResponse(429), GenResponse(200, "from fallback")])
        self.assertEqual(out, "from fallback")
        self.assertEqual(len(FakeAsyncClient.urls), 2)

    def test_all_models_failing_raises(self):
        with self.assertRaises(RuntimeError) as ctx:
            run_generate([GenResponse(503)] * 4)
        self.assertIn("503", str(ctx.exception))

    def test_empty_reply_does_not_crash(self):
        self.assertEqual(run_generate([GenResponse(200, None)]), "")

    def test_bad_request_is_not_hidden(self):
        with self.assertRaises(httpx.HTTPStatusError):
            run_generate([GenResponse(400)])


class TestThresholdRecommendation(unittest.TestCase):
    def test_clean_separation_returns_midpoint(self):
        t, msg = recommend_threshold([0.70, 0.66, 0.72], [0.52, 0.58])
        self.assertEqual(t, 0.62)
        self.assertIn("Clean separation", msg)

    def test_overlap_gives_no_threshold(self):
        t, msg = recommend_threshold([0.62, 0.70], [0.60, 0.65])
        self.assertIsNone(t)
        self.assertIn("Overlap", msg)

    def test_needs_both_groups(self):
        self.assertIsNone(recommend_threshold([], [0.5])[0])


class FakeResponse:
    def __init__(self, status=200, n=0, headers=None):
        self.status_code, self.n, self.headers = status, n, headers or {}

    def raise_for_status(self):
        if self.status_code >= 400:
            raise httpx.HTTPStatusError("err", request=None, response=self)

    def json(self):
        return {"embeddings": [{"values": [1.0, 0.0, 0.0]} for _ in range(self.n)]}


class FakeClient:
    """Context-manager stand-in for httpx.Client that replays scripted statuses."""
    script: list = []
    calls = 0

    def __init__(self, *a, **k):
        pass

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    def post(self, url, json=None, headers=None):
        type(self).calls += 1
        status, hdrs = type(self).script.pop(0) if type(self).script else (200, {})
        return FakeResponse(status, len(json["requests"]), hdrs)


def run_embed(script, texts, cache_path, **overrides):
    FakeClient.script, FakeClient.calls = list(script), 0
    s = RagSettings(gemini_api_key="k", embed_batch=2, embed_pause_seconds=0.0, **overrides)
    with patch.object(embeddings.httpx, "Client", FakeClient), \
         patch.object(embeddings.time, "sleep") as sleep:
        vecs = GeminiEmbedder(s).embed_documents(texts, cache_path=cache_path)
    return vecs, sleep


class TestEmbeddingQuotaHandling(unittest.TestCase):
    def test_429_is_retried_with_retry_after_then_succeeds(self):
        with tempfile.TemporaryDirectory() as d:
            vecs, sleep = run_embed([(429, {"retry-after": "7"}), (200, {})], ["a", "b"], Path(d) / "c.json")
        self.assertEqual(vecs.shape, (2, 3))
        self.assertAlmostEqual(float(np.linalg.norm(vecs[0])), 1.0, places=4)
        self.assertEqual(FakeClient.calls, 2)
        sleep.assert_any_call(7.0)

    def test_progress_is_cached_and_resumed(self):
        with tempfile.TemporaryDirectory() as d:
            cache = Path(d) / "c.json"
            run_embed([], ["a", "b", "c"], cache)
            self.assertEqual(len(json.loads(cache.read_text())), 3)
            first_calls = FakeClient.calls
            run_embed([], ["a", "b", "c"], cache)           # nothing new to embed
            self.assertEqual(FakeClient.calls, 0)
            run_embed([], ["a", "b", "c", "d"], cache)      # only the new text is sent
            self.assertEqual(FakeClient.calls, 1)
        self.assertEqual(first_calls, 2)                    # 3 texts / batch of 2

    def test_bad_key_fails_fast_without_waiting(self):
        with tempfile.TemporaryDirectory() as d:
            with self.assertRaises(RuntimeError) as ctx:
                run_embed([(403, {})], ["a"], Path(d) / "c.json")
        self.assertIn("403", str(ctx.exception))
        self.assertEqual(FakeClient.calls, 1)

    def test_cached_subset_returns_only_embedded_texts(self):
        with tempfile.TemporaryDirectory() as d:
            cache = Path(d) / "c.json"
            run_embed([], ["a", "b"], cache)
            s = RagSettings(gemini_api_key="k")
            idxs, vecs = GeminiEmbedder(s).cached_subset(["a", "zzz", "b"], cache)
            self.assertEqual(idxs, [0, 2])
            self.assertEqual(vecs.shape, (2, 3))
            none_idx, none_vecs = GeminiEmbedder(s).cached_subset(["zzz"], cache)
            self.assertEqual(none_idx, [])
            self.assertEqual(len(none_vecs), 0)

    def test_gives_up_after_max_retries_with_resume_hint(self):
        with tempfile.TemporaryDirectory() as d:
            with self.assertRaises(RuntimeError) as ctx:
                run_embed([(429, {})] * 3, ["a"], Path(d) / "c.json", embed_max_retries=3)
        self.assertIn("cached", str(ctx.exception))
        self.assertEqual(FakeClient.calls, 3)


if __name__ == "__main__":
    unittest.main()
