"""
Hybrid Vector & Keyword Retriever for Karnataka Government RAG.

Architectural Context:
- Uses scikit-learn's optimized TF-IDF vectorizer + cosine similarity for instant in-memory vector retrieval (< 5ms).
- Enriched with entity matching and domain keyword weighting.
- Grounds answers strictly in official Karnataka Government portals (sevasindhu, bhoomi, bescom, ksrtc, etc.).
- Never raises unhandled exceptions on unexpected input.
"""

from dataclasses import dataclass
import re
from typing import List, Optional, Tuple
import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

from app.core.logger import get_logger
from app.rag.karnataka_knowledge import (
    KarnatakaSchemeDocument,
    get_all_karnataka_documents,
)

logger = get_logger("awaaz_setu.rag.retriever")


@dataclass
class RetrievalResult:
    document: KarnatakaSchemeDocument
    score: float
    official_url: str
    official_portal: str
    scheme_name: str
    category: str
    chunk_text: str


class KarnatakaRAGRetriever:
    """
    High-performance, in-memory hybrid retriever indexing official
    Government of Karnataka schemes, portals, and welfare programs.
    """

    def __init__(self, documents: Optional[List[KarnatakaSchemeDocument]] = None):
        self.documents = documents if documents is not None else get_all_karnataka_documents()
        self._doc_texts: List[str] = [doc.to_chunk_text() for doc in self.documents]
        
        # Fit TF-IDF Vectorizer with unigrams and bigrams
        self.vectorizer = TfidfVectorizer(
            ngram_range=(1, 2),
            stop_words="english",
            strip_accents="unicode",
            sublinear_tf=True,
        )
        self.doc_vectors = self.vectorizer.fit_transform(self._doc_texts)
        logger.info("Karnataka RAG Retriever indexed %d official documents.", len(self.documents))

    def _calculate_keyword_boost(self, query: str, doc: KarnatakaSchemeDocument) -> float:
        """Calculates explicit keyword overlap boost for specific scheme names and entities."""
        q_lower = query.lower()
        boost = 0.0

        # Exact match on scheme name or ID
        if doc.scheme_name.lower() in q_lower or doc.id in q_lower:
            boost += 0.40

        # Check keyword matches
        for kw in doc.keywords:
            if kw in q_lower:
                boost += 0.15

        # Check official portal / URL reference
        if doc.official_portal.lower() in q_lower or doc.department.lower() in q_lower:
            boost += 0.20

        return min(boost, 0.60)

    def retrieve(
        self,
        query: str,
        top_k: int = 3,
        min_score: float = 0.10,
    ) -> List[RetrievalResult]:
        """
        Retrieves top relevant Karnataka Government documents for a given user query.
        Combines TF-IDF cosine similarity with keyword/entity priority boosting.
        """
        clean_q = (query or "").strip()
        if not clean_q:
            return []

        try:
            query_vector = self.vectorizer.transform([clean_q])
            similarities = cosine_similarity(query_vector, self.doc_vectors)[0]

            scored_results: List[Tuple[float, KarnatakaSchemeDocument]] = []
            for idx, base_score in enumerate(similarities):
                doc = self.documents[idx]
                boost = self._calculate_keyword_boost(clean_q, doc)
                combined_score = float(base_score) * 0.65 + boost * 0.35

                if combined_score >= min_score or boost > 0.10:
                    scored_results.append((combined_score, doc))

            # Sort descending by combined score
            scored_results.sort(key=lambda x: x[0], reverse=True)

            results: List[RetrievalResult] = []
            for score, doc in scored_results[:top_k]:
                results.append(
                    RetrievalResult(
                        document=doc,
                        score=round(score, 4),
                        official_url=doc.official_url,
                        official_portal=doc.official_portal,
                        scheme_name=doc.scheme_name,
                        category=doc.category,
                        chunk_text=doc.to_chunk_text(),
                    )
                )

            logger.debug(
                "Retrieved %d Karnataka documents for query '%s' (top score: %.3f)",
                len(results),
                clean_q[:50],
                results[0].score if results else 0.0,
            )
            return results

        except Exception as exc:
            logger.warning("Error during Karnataka RAG retrieval: %s", exc, exc_info=True)
            return []

    def get_best_match(self, query: str, threshold: float = 0.15) -> Optional[RetrievalResult]:
        """Returns the single highest-scoring Karnataka document, or None if below threshold."""
        results = self.retrieve(query=query, top_k=1, min_score=threshold)
        return results[0] if results else None
