"""
Knowledge routing for in-scope Karnataka questions.

Order of resolution:
  1. Decision tree  - OPTIONAL plugin module `app/services/decision_tree.py`
                      exposing  resolve(text_query: str, phone: str) -> str | None
                      (sync or async). Return None when no node matches.
  2. Verified KB    - instant, offline answers the team verified against official pages
                      (data/kb/verified_answers.json). No LLM involved.
  3. RAG            - generative answers from crawled/local official documents.
  4. (caller)       - if this returns None the question is out of scope and the
                      caller falls through to general Gemini.
"""
from __future__ import annotations

import importlib
import inspect
from dataclasses import dataclass, field
from functools import lru_cache
from typing import Optional

from app.core.logger import get_logger
from app.rag import get_kb_service, get_rag_service

logger = get_logger("awaaz_setu.services.knowledge_router")

_TREE_MODULE = "app.services.decision_tree"


@dataclass(frozen=True)
class KnowledgeAnswer:
    text: str
    route: str                      # "decision_tree" | "rag"
    sources: list[str] = field(default_factory=list)


@lru_cache(maxsize=1)
def _load_decision_tree():
    """Import the decision-tree plugin if it exists; errors INSIDE it still surface."""
    try:
        return importlib.import_module(_TREE_MODULE)
    except ModuleNotFoundError as exc:
        if exc.name == _TREE_MODULE:
            logger.info("No decision tree installed (%s); using RAG only.", _TREE_MODULE)
            return None
        raise


async def answer_from_knowledge(text_query: str, phone: str) -> Optional[KnowledgeAnswer]:
    query = (text_query or "").strip()
    if not query:
        return None

    # 1) Decision tree
    tree = _load_decision_tree()
    if tree is not None and hasattr(tree, "resolve"):
        try:
            result = tree.resolve(query, phone)
            if inspect.isawaitable(result):
                result = await result
            if isinstance(result, str) and result.strip():
                return KnowledgeAnswer(result.strip(), "decision_tree")
        except Exception as exc:  # noqa: BLE001 - a tree bug must not drop the call
            logger.warning("Decision tree failed: %s", exc.__class__.__name__)

    # 2) Verified answers (instant, offline, no LLM)
    kb = get_kb_service()
    if kb is not None:
        hit = kb.answer(query)
        if hit is not None:
            logger.info("Verified KB answer: %s (score %.2f)", hit.entry_id, hit.score)
            return KnowledgeAnswer(hit.text, "rag", [hit.source_url])

    # 3) RAG over crawled / local official documents
    service = get_rag_service()
    if service is not None:
        rag = await service.answer(query)
        if rag is not None:
            return KnowledgeAnswer(rag.text, "rag", rag.sources)

    return None
