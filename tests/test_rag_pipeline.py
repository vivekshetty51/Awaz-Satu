"""
Offline tests for the RAG layer and knowledge routing (no network, no API keys).

Covers:
1. Crawler allow-list (rejects look-alike / non-government domains).
2. Chunking and vector store save/load/search.
3. RagService: in-scope answer, weak match, NOT_FOUND, embed/generation failure.
4. Knowledge router order: decision tree -> RAG -> None (caller uses Gemini).
"""
import tempfile
import unittest
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import numpy as np

from app.rag.config import RagSettings
from app.rag.ingest import chunk_text, clean_text, is_allowed_domain
from app.rag.retriever import RagService
from app.rag.vector_store import Chunk, VectorStore
from app.services import knowledge_router
from app.services.knowledge_router import answer_from_knowledge

ALLOWED = ("karnataka.gov.in", "kar.nic.in")


def unit(*v):
    a = np.array(v, dtype=np.float32)
    return a / np.linalg.norm(a)


class FakeEmbedder:
    """'pension' questions point along axis 0, everything else along axis 2."""

    async def embed_query(self, text: str):
        return unit(1, 0, 0) if "pension" in text.lower() else unit(0, 0, 1)

    def embed_documents(self, texts):
        raise NotImplementedError


def make_store() -> VectorStore:
    chunks = [
        Chunk("Sandhya Suraksha pension is given to senior citizens.", "https://sevasindhu.karnataka.gov.in/p", "Pension"),
        Chunk("Scholarship details for students.", "https://karnataka.gov.in/s", "Scholarship"),
    ]
    return VectorStore(np.stack([unit(1, 0, 0), unit(0, 1, 0)]), chunks)


class TestDomainAllowList(unittest.TestCase):
    def test_allows_gov_and_subdomains(self):
        for u in ("https://karnataka.gov.in/", "https://sevasindhu.karnataka.gov.in/x",
                  "http://ahara.kar.nic.in/a.pdf"):
            self.assertTrue(is_allowed_domain(u, ALLOWED), u)

    def test_rejects_lookalikes_and_other_sites(self):
        for u in ("https://karnataka.gov.in.evil.com/", "https://evilkarnataka.gov.in/",
                  "https://example.com/", "https://pmkisan.gov.in/",
                  "ftp://karnataka.gov.in/", "javascript:alert(1)", ""):
            self.assertFalse(is_allowed_domain(u, ALLOWED), u)


class TestChunking(unittest.TestCase):
    def test_chunks_respect_size_and_drop_noise(self):
        text = clean_text(("Pension scheme paragraph about eligibility. " * 8 + "\n\n") * 6 + "tiny\n\n")
        chunks = chunk_text(text, 500, 80)
        self.assertTrue(chunks)
        self.assertTrue(all(80 < len(c) <= 1100 for c in chunks))
        self.assertFalse(any(c.strip() == "tiny" for c in chunks))


class TestVectorStore(unittest.TestCase):
    def test_search_orders_by_similarity(self):
        hits = make_store().search(unit(1, 0.1, 0), 2)
        self.assertEqual(hits[0].chunk.title, "Pension")
        self.assertGreater(hits[0].score, hits[1].score)

    def test_save_and_load_roundtrip(self):
        with tempfile.TemporaryDirectory() as d:
            make_store().save(Path(d))
            loaded = VectorStore.load(Path(d))
            self.assertEqual(len(loaded), 2)
            self.assertEqual(loaded.chunks[0].url, "https://sevasindhu.karnataka.gov.in/p")
        self.assertIsNone(VectorStore.load(Path("/nonexistent-dir")))


class TestRagService(unittest.IsolatedAsyncioTestCase):
    def service(self, reply="Senior citizens receive a monthly pension.", threshold=0.6):
        s = RagSettings(similarity_threshold=threshold)
        gen = AsyncMock(return_value=reply)
        return RagService(s, make_store(), FakeEmbedder(), gen), gen

    async def test_in_scope_answers_from_context_with_source(self):
        svc, gen = self.service()
        ans = await svc.answer("What is the pension scheme?")
        self.assertEqual(ans.text, "Senior citizens receive a monthly pension.")
        self.assertEqual(ans.sources[0], "https://sevasindhu.karnataka.gov.in/p")
        self.assertIn("CONTEXT:", gen.call_args.args[1])   # grounded prompt

    async def test_weak_match_is_out_of_scope_and_skips_llm(self):
        svc, gen = self.service()
        self.assertIsNone(await svc.answer("Who won the cricket match?"))
        gen.assert_not_called()

    async def test_not_found_reply_is_out_of_scope(self):
        svc, _ = self.service(reply="NOT_FOUND")
        self.assertIsNone(await svc.answer("pension for astronauts"))

    async def test_markdown_is_stripped_for_speech(self):
        svc, _ = self.service(reply="**Pension** is paid\n- monthly")
        self.assertNotIn("*", (await svc.answer("pension?")).text)

    async def test_embedding_failure_returns_none(self):
        svc, _ = self.service()
        svc.embedder.embed_query = AsyncMock(side_effect=RuntimeError("boom"))
        self.assertIsNone(await svc.answer("pension?"))

    async def test_generation_failure_returns_none(self):
        svc, gen = self.service()
        gen.side_effect = RuntimeError("quota")
        self.assertIsNone(await svc.answer("pension?"))


class TestKnowledgeRouter(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        knowledge_router._load_decision_tree.cache_clear()

    async def test_decision_tree_has_priority_over_rag(self):
        tree = MagicMock()
        tree.resolve = MagicMock(return_value="Tree answer")
        rag = MagicMock()
        rag.answer = AsyncMock()
        with patch.object(knowledge_router, "_load_decision_tree", return_value=tree), \
             patch.object(knowledge_router, "get_rag_service", return_value=rag):
            res = await answer_from_knowledge("pension", "+919999999999")
        self.assertEqual((res.route, res.text), ("decision_tree", "Tree answer"))
        rag.answer.assert_not_called()

    async def test_async_tree_supported_and_no_match_falls_to_rag(self):
        tree = MagicMock()
        tree.resolve = AsyncMock(return_value=None)
        from app.rag.retriever import RagAnswer
        rag = MagicMock()
        rag.answer = AsyncMock(return_value=RagAnswer("RAG answer", ["https://karnataka.gov.in/x"], 0.8))
        with patch.object(knowledge_router, "_load_decision_tree", return_value=tree), \
             patch.object(knowledge_router, "get_rag_service", return_value=rag):
            res = await answer_from_knowledge("scholarship", "+919999999999")
        self.assertEqual((res.route, res.text), ("rag", "RAG answer"))
        self.assertEqual(res.sources, ["https://karnataka.gov.in/x"])

    async def test_tree_crash_does_not_break_call(self):
        tree = MagicMock()
        tree.resolve = MagicMock(side_effect=ValueError("bug"))
        with patch.object(knowledge_router, "_load_decision_tree", return_value=tree), \
             patch.object(knowledge_router, "get_rag_service", return_value=None):
            self.assertIsNone(await answer_from_knowledge("pension", "+919999999999"))

    async def test_out_of_scope_returns_none_for_gemini_fallback(self):
        rag = MagicMock()
        rag.answer = AsyncMock(return_value=None)
        with patch.object(knowledge_router, "_load_decision_tree", return_value=None), \
             patch.object(knowledge_router, "get_rag_service", return_value=rag):
            self.assertIsNone(await answer_from_knowledge("who wrote the constitution", "+919999999999"))

    async def test_empty_query_returns_none(self):
        self.assertIsNone(await answer_from_knowledge("   ", "+919999999999"))


if __name__ == "__main__":
    unittest.main()
