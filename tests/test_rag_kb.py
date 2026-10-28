"""Offline tests for the verified-answer knowledge base and its place in the routing order."""
import json
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

from app.rag.config import RagSettings
from app.rag.kb import KbService, KnowledgeBase, load_entries
from app.services import knowledge_router
from app.services.knowledge_router import answer_from_knowledge

ALLOWED = ("karnataka.gov.in", "kar.nic.in")


def entry(eid, title, questions, keywords, answer="Spoken answer that is long enough to be valid.",
          source="https://sevasindhu.karnataka.gov.in/x"):
    return {"id": eid, "title": title, "questions": questions, "keywords": keywords,
            "answer": answer, "source_url": source}


SAMPLE = [
    entry("pension", "Sandhya Suraksha pension",
          ["What is the Sandhya Suraksha pension?", "How do I apply for old age pension?",
           "How can senior citizens get pension?"],
          ["sandhya suraksha", "old age pension", "senior citizen pension"], "Pension answer, spoken form."),
    entry("lakshmi", "Gruha Lakshmi scheme",
          ["What is the Gruha Lakshmi scheme?", "How do I apply for Gruha Lakshmi?"],
          ["gruha lakshmi", "griha lakshmi", "gruha laxmi"], "Lakshmi answer, spoken form."),
    entry("anna", "Anna Bhagya scheme",
          ["What is the Anna Bhagya scheme?", "How do I apply for a ration card?"],
          ["anna bhagya", "ration card", "free rice"], "Anna answer, spoken form."),
    entry("scholarship", "State Scholarship Portal",
          ["How can I apply for a scholarship?", "How do I check my scholarship status?"],
          ["scholarship", "post matric", "student scholarship"], "Scholarship answer, spoken form."),
    entry("sevasindhu", "Seva Sindhu portal",
          ["What is Seva Sindhu?", "How do I track my application on Seva Sindhu?"],
          ["sevasindhu", "seva sindhu", "application status"], "Seva Sindhu answer, spoken form."),
]


def write_kb(directory, entries):
    path = Path(directory) / "kb.json"
    path.write_text(json.dumps({"entries": entries}), encoding="utf-8")
    return path


def build(entries=SAMPLE):
    with tempfile.TemporaryDirectory() as d:
        loaded, skipped = load_entries(write_kb(d, entries), ALLOWED)
    return KnowledgeBase(loaded), skipped


class TestMatching(unittest.TestCase):
    def setUp(self):
        self.kb, _ = build()

    def check(self, question, expected):
        hit = self.kb.answer(question)
        self.assertIsNotNone(hit, f"no answer for: {question}")
        self.assertEqual(hit.entry_id, expected, question)

    def test_natural_phrasings(self):
        self.check("tell me about old age pension", "pension")
        self.check("i am 70 years old how do i get pension", "pension")
        self.check("how to apply for gruha lakshmi", "lakshmi")
        self.check("how do i get a ration card", "anna")
        self.check("scholarship for students", "scholarship")
        self.check("what is sevasindhu", "sevasindhu")

    def test_speech_recognition_misspellings(self):
        self.check("sandya suraksha yojana", "pension")
        self.check("sandhya suraksha pention", "pension")
        self.check("gruhalakshmi scheme", "lakshmi")
        self.check("gruha laxmi", "lakshmi")
        self.check("anna bagya", "anna")
        self.check("seva sindu portal", "sevasindhu")

    def test_out_of_scope_questions_are_not_answered(self):
        for q in ["who wrote the indian constitution", "who won the cricket world cup", "what is the capital of france",
                  "how do i cook biryani", "what is photosynthesis", "tell me a joke", "what is the weather today",
                  "who is the prime minister of japan", "how do i apply for a us visa", "best phone under 20000",
                  "explain machine learning", "how to lose weight"]:
            self.assertIsNone(self.kb.answer(q), q)

    def test_other_countries_and_states_are_rejected(self):
        self.assertIsNone(self.kb.answer("what is the pension age in germany"))
        self.assertIsNone(self.kb.answer("old age pension in tamil nadu"))
        self.assertIsNotNone(self.kb.answer("old age pension in karnataka"))

    def test_ambiguous_question_is_not_guessed(self):
        kb, _ = build([
            entry("a", "Pension scheme one", ["pension eligibility"], ["pension"]),
            entry("b", "Pension scheme two", ["pension eligibility"], ["pension"]),
        ])
        self.assertIsNone(kb.answer("pension eligibility"))

    def test_answer_is_returned_exactly_as_written_with_source(self):
        hit = self.kb.answer("what is seva sindhu")
        self.assertEqual(hit.text, "Seva Sindhu answer, spoken form.")
        self.assertEqual(hit.source_url, "https://sevasindhu.karnataka.gov.in/x")


class TestEntryValidation(unittest.TestCase):
    def reasons(self, entries):
        _, skipped = build(entries)
        return dict(skipped)

    def test_todo_short_nonofficial_and_incomplete_entries_are_skipped(self):
        r = self.reasons([
            entry("todo", "T", ["q"], [], answer="TODO: fill in"),
            entry("short", "S", ["q"], [], answer="Too short"),
            entry("blog", "B", ["q"], [], source="https://example.com/post"),
            entry("lookalike", "L", ["q"], [], source="https://karnataka.gov.in.evil.com/"),
            entry("noq", "N", [], []),
        ])
        self.assertEqual(set(r), {"todo", "short", "blog", "lookalike", "noq"})

    def test_duplicate_ids_are_skipped(self):
        r = self.reasons([entry("x", "One", ["q one"], []), entry("x", "Two", ["q two"], [])])
        self.assertEqual(r, {"x": "duplicate id"})

    def test_missing_file_is_fine(self):
        self.assertEqual(load_entries(Path("/nonexistent/kb.json"), ALLOWED), ([], []))

    def test_shipped_template_loads_and_activates_nothing_unverified(self):
        shipped = Path(__file__).resolve().parents[1] / "data" / "kb" / "verified_answers.json"
        entries, skipped = load_entries(shipped, ALLOWED)
        self.assertTrue(all(e.source_url.startswith("https://") for e in entries))
        self.assertTrue(any(reason.startswith("answer not filled") for _, reason in skipped))


class TestServiceReload(unittest.TestCase):
    def test_edits_are_picked_up_without_restart(self):
        with tempfile.TemporaryDirectory() as d:
            path = write_kb(d, SAMPLE[:1])
            svc = KbService(RagSettings(kb_file=path))
            self.assertIsNone(svc.answer("what is gruha lakshmi"))
            time.sleep(0.05)
            path.write_text(json.dumps({"entries": SAMPLE[:2]}), encoding="utf-8")
            import os
            os.utime(path, (time.time() + 5, time.time() + 5))
            self.assertEqual(svc.answer("what is gruha lakshmi").entry_id, "lakshmi")


class TestRoutingOrder(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        knowledge_router._load_decision_tree.cache_clear()

    async def test_verified_answer_beats_rag_and_skips_the_llm(self):
        kb_hit = MagicMock(text="Verified text", source_url="https://ssp.karnataka.gov.in/", entry_id="x", score=0.9)
        kb = MagicMock(); kb.answer = MagicMock(return_value=kb_hit)
        rag = MagicMock(); rag.answer = AsyncMock()
        with patch.object(knowledge_router, "_load_decision_tree", return_value=None), \
             patch.object(knowledge_router, "get_kb_service", return_value=kb), \
             patch.object(knowledge_router, "get_rag_service", return_value=rag):
            res = await answer_from_knowledge("scholarship", "+911234567891")
        self.assertEqual((res.route, res.text), ("rag", "Verified text"))
        self.assertEqual(res.sources, ["https://ssp.karnataka.gov.in/"])
        rag.answer.assert_not_called()

    async def test_decision_tree_still_comes_first(self):
        tree = MagicMock(); tree.resolve = MagicMock(return_value="Tree answer")
        kb = MagicMock(); kb.answer = MagicMock()
        with patch.object(knowledge_router, "_load_decision_tree", return_value=tree), \
             patch.object(knowledge_router, "get_kb_service", return_value=kb):
            res = await answer_from_knowledge("pension", "+911234567891")
        self.assertEqual(res.route, "decision_tree")
        kb.answer.assert_not_called()

    async def test_no_verified_match_falls_through_to_rag(self):
        from app.rag.retriever import RagAnswer
        kb = MagicMock(); kb.answer = MagicMock(return_value=None)
        rag = MagicMock(); rag.answer = AsyncMock(return_value=RagAnswer("RAG text", ["https://karnataka.gov.in/x"], 0.8))
        with patch.object(knowledge_router, "_load_decision_tree", return_value=None), \
             patch.object(knowledge_router, "get_kb_service", return_value=kb), \
             patch.object(knowledge_router, "get_rag_service", return_value=rag):
            res = await answer_from_knowledge("something else", "+911234567891")
        self.assertEqual(res.text, "RAG text")


if __name__ == "__main__":
    unittest.main()
