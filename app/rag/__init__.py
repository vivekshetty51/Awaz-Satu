"""
Karnataka Government RAG (Retrieval-Augmented Generation) package.
"""

from app.rag.karnataka_knowledge import (
    KarnatakaSchemeDocument,
    KARNATAKA_GOVERNMENT_DOCUMENTS,
    get_all_karnataka_documents,
    get_document_by_id,
)
from app.rag.retriever import KarnatakaRAGRetriever, RetrievalResult
from app.rag.rag_engine import KarnatakaRAGEngine, RAGResponse, karnataka_rag_engine

__all__ = [
    "KarnatakaSchemeDocument",
    "KARNATAKA_GOVERNMENT_DOCUMENTS",
    "get_all_karnataka_documents",
    "get_document_by_id",
    "KarnatakaRAGRetriever",
    "RetrievalResult",
    "KarnatakaRAGEngine",
    "RAGResponse",
    "karnataka_rag_engine",
]
