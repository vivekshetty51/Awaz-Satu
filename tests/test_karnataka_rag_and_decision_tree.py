"""
Comprehensive Test Suite for Karnataka Government RAG & Decision Tree Routing.

Coverage:
1. Decision Tree Routing:
   - Explicit Karnataka Guarantee Schemes -> RAG (Gruha Lakshmi, Gruha Jyothi, Yuva Nidhi, Anna Bhagya, Shakti).
   - Karnataka Land & Property Records -> RAG (Bhoomi, RTC/Pahani, e-Swathu Form 9/11).
   - Karnataka Agriculture & Irrigation Welfare -> RAG (Ganga Kalyana borewell, Raitha Siri, Pashu Bhagya).
   - Karnataka Citizen Portals & Certificates -> RAG (Seva Sindhu, Nada Kacheri, Kutumba, SSP).
   - General / Out-of-Range Questions -> GEMINI (Science, coding, world trivia, non-Karnataka queries).
   - Greetings & Conversational Queries -> GEMINI.
   - Decision path and explanation trace integrity.
2. Karnataka Government Knowledge Base & Hybrid Retriever:
   - Total indexed official documents count and metadata validation.
   - High-precision vector + keyword similarity scoring.
   - Official Karnataka Government URL citation.
3. Karnataka RAG Engine Synthesis:
   - Factual English voice responses grounded in official government data.
   - Structured DPI payload generation for frontend UI.
4. FastAPI Endpoints:
   - POST /api/decision-tree/evaluate
   - POST /api/rag/query
   - GET /api/decision-tree/diagram
   - GET /api/rag/documents
"""

import asyncio
import os
import unittest
from unittest.mock import AsyncMock, patch

from fastapi.testclient import TestClient

from app.main import app as voice_engine_app
from app.decision_tree.tree_nodes import RoutingTarget, DecisionTrace
from app.decision_tree.decision_tree_engine import DecisionTreeRouter, FeatureExtractor
from app.rag.karnataka_knowledge import (
    KARNATAKA_GOVERNMENT_DOCUMENTS,
    get_all_karnataka_documents,
    get_document_by_id,
)
from app.rag.retriever import KarnatakaRAGRetriever
from app.rag.rag_engine import KarnatakaRAGEngine, karnataka_rag_engine
from app.services.ai_agent import query_ai_agent_with_routing, query_ai_agent


class TestKarnatakaRAGAndDecisionTree(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.client = TestClient(voice_engine_app)
        cls.router = DecisionTreeRouter()
        cls.retriever = KarnatakaRAGRetriever()
        cls.rag_engine = KarnatakaRAGEngine(retriever=cls.retriever)

    # -------------------------------------------------------------------------
    # 1. Decision Tree Routing: Karnataka Domain -> RAG
    # -------------------------------------------------------------------------
    def test_01_guarantee_schemes_route_to_rag(self):
        """Verifies that all 5 Karnataka Guarantee Schemes route to RAG with high confidence."""
        karnataka_queries = [
            ("What is the eligibility for Gruha Lakshmi Scheme in Karnataka?", "gruha lakshmi"),
            ("How to apply for 200 units free electricity under Gruha Jyothi?", "gruha jyothi"),
            ("How much money do unemployed graduates get under Yuva Nidhi?", "yuva nidhi"),
            ("When will Anna Bhagya 10 kg rice cash transfer be credited?", "anna bhagya"),
            ("Is BMTC and KSRTC bus free for women under Shakti Scheme?", "shakti"),
        ]

        for query, expected_match in karnataka_queries:
            trace = self.router.evaluate(query)
            self.assertEqual(
                trace.target,
                RoutingTarget.RAG,
                f"Query '{query}' should route to RAG but got {trace.target}",
            )
            self.assertGreaterEqual(trace.confidence, 0.90)
            self.assertTrue(len(trace.decision_path) >= 2)
            self.assertTrue(
                any(expected_match in r.lower() for r in trace.matched_rules),
                f"Expected '{expected_match}' in matched rules {trace.matched_rules}",
            )

    def test_02_land_and_revenue_route_to_rag(self):
        """Verifies Karnataka land records (Bhoomi, RTC/Pahani, e-Swathu) route to RAG."""
        queries = [
            "How do I download my land RTC Pahani online from Bhoomi portal?",
            "What is the procedure for land mutation status in Karnataka?",
            "How to get Form 9 and Form 11 from e-Swathu for rural property?",
        ]
        for query in queries:
            trace = self.router.evaluate(query)
            self.assertEqual(trace.target, RoutingTarget.RAG)
            self.assertGreaterEqual(trace.confidence, 0.88)

    def test_03_agriculture_and_irrigation_route_to_rag(self):
        """Verifies agriculture, borewell, and livestock queries route to RAG."""
        queries = [
            "How to apply for free borewell subsidy under Ganga Kalyana Scheme?",
            "What is the millet cultivation incentive under Raitha Siri?",
            "What is the subsidy for dairy cow farming loan under Pashu Bhagya?",
        ]
        for query in queries:
            trace = self.router.evaluate(query)
            self.assertEqual(trace.target, RoutingTarget.RAG)
            self.assertGreaterEqual(trace.confidence, 0.88)

    def test_04_citizen_portals_and_certificates_route_to_rag(self):
        """Verifies Seva Sindhu, Nada Kacheri, Kutumba, and SSP route to RAG."""
        queries = [
            "How do I apply for caste and income certificate on Nada Kacheri portal?",
            "What services are available on Seva Sindhu Karnataka?",
            "How to apply for post matric scholarship on SSP Karnataka?",
            "What is the family ID in Kutumba portal Karnataka?",
        ]
        for query in queries:
            trace = self.router.evaluate(query)
            self.assertEqual(trace.target, RoutingTarget.RAG)
            self.assertGreaterEqual(trace.confidence, 0.88)

    # -------------------------------------------------------------------------
    # 2. Decision Tree Routing: General / External Domain -> GEMINI
    # -------------------------------------------------------------------------
    def test_05_open_domain_questions_route_to_gemini(self):
        """Verifies questions outside Karnataka Government scope route to Google Gemini."""
        open_domain_queries = [
            "What is the capital of France?",
            "Explain the theory of general relativity by Albert Einstein.",
            "Write a Python function to sort a binary tree.",
            "Who was Napoleon Bonaparte?",
            "Tell me a funny joke about computers.",
            "What is the distance between the Earth and the Moon?",
            "What is quantum computing?",
        ]
        for query in open_domain_queries:
            trace = self.router.evaluate(query)
            self.assertEqual(
                trace.target,
                RoutingTarget.GEMINI,
                f"Query '{query}' should route to GEMINI but got {trace.target}",
            )
            self.assertGreaterEqual(trace.confidence, 0.80)

    def test_06_greetings_route_to_gemini(self):
        """Verifies greetings and conversational chitchat route to Google Gemini."""
        greetings = [
            "Hello",
            "Hi",
            "Good morning",
            "Who are you?",
            "What can you do?",
        ]
        for g in greetings:
            trace = self.router.evaluate(g)
            self.assertEqual(trace.target, RoutingTarget.GEMINI)

    # -------------------------------------------------------------------------
    # 3. Karnataka Government Knowledge Base & Hybrid Retriever
    # -------------------------------------------------------------------------
    def test_07_karnataka_documents_indexed(self):
        """Verifies all verified Karnataka Government documents are registered."""
        docs = get_all_karnataka_documents()
        self.assertGreaterEqual(len(docs), 16)

        # Check required fields for all documents
        for doc in docs:
            self.assertTrue(doc.id)
            self.assertTrue(doc.scheme_name)
            self.assertTrue(doc.official_url.startswith("http"))
            self.assertTrue(doc.official_portal)
            self.assertTrue(doc.benefits)
            self.assertTrue(doc.eligibility)
            self.assertTrue(doc.helpline)

    def test_08_retrieval_accuracy_and_urls(self):
        """Verifies hybrid retriever matches correct official URLs and data."""
        # Gruha Lakshmi
        res = self.retriever.get_best_match("tell me about gruha lakshmi 2000 rupees")
        self.assertIsNotNone(res)
        self.assertEqual(res.document.id, "gruha_lakshmi")
        self.assertEqual(res.official_url, "https://sevasindhu.karnataka.gov.in")
        self.assertIn("2,000", res.document.benefits)

        # Gruha Jyothi
        res = self.retriever.get_best_match("how to get 200 units free power in karnataka")
        self.assertIsNotNone(res)
        self.assertEqual(res.document.id, "gruha_jyothi")
        self.assertIn("200 units", res.document.benefits)

        # Bhoomi RTC
        res = self.retriever.get_best_match("view pahani rtc survey number bhoomi")
        self.assertIsNotNone(res)
        self.assertEqual(res.document.id, "bhoomi_portal")
        self.assertEqual(res.official_url, "https://bhoomi.karnataka.gov.in")

        # Ganga Kalyana
        res = self.retriever.get_best_match("free borewell drilling subsidy ganga kalyana")
        self.assertIsNotNone(res)
        self.assertEqual(res.document.id, "ganga_kalyana")
        self.assertEqual(res.official_url, "https://drbrambedkar.karnataka.gov.in")

    def test_09_unrelated_query_has_low_retrieval_score(self):
        """Verifies out-of-domain query scores below threshold."""
        results = self.retriever.retrieve("quantum physics speed of light photon", top_k=1, min_score=0.40)
        self.assertEqual(len(results), 0)

    # -------------------------------------------------------------------------
    # 4. Karnataka RAG Engine End-to-End Synthesis
    # -------------------------------------------------------------------------
    def test_10_rag_engine_synthesizes_grounded_answer(self):
        """Verifies RAG Engine synthesizes a speakable English answer with official details."""
        async def run_rag():
            res = await self.rag_engine.answer("How to apply for Gruha Lakshmi Scheme?")
            return res

        rag_res = asyncio.run(run_rag())
        self.assertIsNotNone(rag_res)
        self.assertIn("Gruha Lakshmi", rag_res.scheme_name)
        self.assertEqual(rag_res.official_url, "https://sevasindhu.karnataka.gov.in")
        self.assertIn("Seva Sindhu", rag_res.spoken_text)
        self.assertIn("2,000 rupees", rag_res.spoken_text)
        self.assertIn("Karnataka Gov", rag_res.dpi_service)
        self.assertIn("https://sevasindhu.karnataka.gov.in", rag_res.dpi_details)

    # -------------------------------------------------------------------------
    # 5. Integrated AI Agent Query with Decision Tree Routing
    # -------------------------------------------------------------------------
    def test_11_query_ai_agent_with_routing_karnataka(self):
        """Verifies query_ai_agent_with_routing routes Karnataka query to RAG with metadata."""
        async def run_agent():
            return await query_ai_agent_with_routing(
                text_query="What is the benefit of Yuva Nidhi scheme in Karnataka?",
                phone="+919876543210",
            )

        spoken, service, details, route, url, confidence = asyncio.run(run_agent())
        self.assertEqual(route, "RAG")
        self.assertIn("Yuva Nidhi", service)
        self.assertIn("3,000", spoken)
        self.assertEqual(url, "https://sevasindhu.karnataka.gov.in")
        self.assertGreaterEqual(confidence, 0.90)

    def test_12_query_ai_agent_with_routing_general(self):
        """Verifies query_ai_agent_with_routing routes general query to GEMINI."""
        async def run_agent():
            return await query_ai_agent_with_routing(
                text_query="What is the capital of France?",
                phone="+919876543210",
            )

        spoken, service, details, route, url, confidence = asyncio.run(run_agent())
        self.assertEqual(route, "GEMINI")
        self.assertIsNone(url)  # No Karnataka portal URL for general world queries

    # -------------------------------------------------------------------------
    # 6. REST API Endpoints Verification
    # -------------------------------------------------------------------------
    def test_13_api_decision_tree_evaluate_endpoint(self):
        """Tests POST /api/decision-tree/evaluate."""
        res = self.client.post("/api/decision-tree/evaluate", json={"query": "Gruha Jyothi electricity bill"})
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertEqual(data["target"], "RAG")
        self.assertGreaterEqual(data["confidence"], 0.90)
        self.assertTrue(len(data["decision_path"]) > 0)
        self.assertIn("explanation", data)

    def test_14_api_rag_query_endpoint(self):
        """Tests POST /api/rag/query."""
        res = self.client.post("/api/rag/query", json={"query": "How to get RTC on Bhoomi portal?"})
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertEqual(data["status"], "success")
        self.assertEqual(data["official_url"], "https://bhoomi.karnataka.gov.in")
        self.assertIn("bhoomi", data["spoken_text"].lower())

    def test_15_api_rag_documents_and_diagram_endpoints(self):
        """Tests GET /api/rag/documents and GET /api/decision-tree/diagram."""
        docs_res = self.client.get("/api/rag/documents")
        self.assertEqual(docs_res.status_code, 200)
        docs_data = docs_res.json()
        self.assertGreaterEqual(docs_data["total_documents"], 16)

        diag_res = self.client.get("/api/decision-tree/diagram")
        self.assertEqual(diag_res.status_code, 200)
        self.assertIn("AWAAZ SETU DECISION TREE ROUTER", diag_res.text)


if __name__ == "__main__":
    unittest.main()
