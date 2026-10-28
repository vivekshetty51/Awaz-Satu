"""
Retrieval over official Karnataka Government sources.

Public API:
    get_kb_service()   -> verified, offline answers (no LLM)           [first choice]
    get_rag_service()  -> generative RAG over crawled/local documents  [second choice]
"""
from app.rag.kb import KbAnswer, KbService, get_kb_service
from app.rag.retriever import RagAnswer, RagService, get_rag_service

__all__ = ["KbAnswer", "KbService", "RagAnswer", "RagService", "get_kb_service", "get_rag_service"]
