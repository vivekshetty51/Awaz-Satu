"""
Verified-answer knowledge base: instant, offline answers to in-scope questions.

Why this exists
  Calling an LLM for every in-scope question is slow (3-12 s), fails when the API is overloaded
  or out of quota, and can invent scheme amounts. For questions the team has verified against an
  official Karnataka government page, the spoken answer is stored in data/kb/verified_answers.json
  and returned as written, with its official source. No network, no quota, no hallucination.

How a question is matched (pure Python, no API)
  TF-IDF cosine over whole words plus 3/4-letter character pieces, so speech-recognition
  misspellings such as "sandya suraksha" or "gruha laxmi" still match. Generic words
  ("apply", "scheme", ...) carry little weight, questions about other countries/states are
  rejected, and the best entry must clearly beat the runner-up.
"""
from __future__ import annotations

import json
import math
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from app.core.logger import get_logger
from app.rag.config import RagSettings
from app.rag.ingest import is_allowed_domain

logger = get_logger("awaaz_setu.rag.kb")

STOPWORDS = frozenset("""a an the of for to in on at is are was be am do does did i me my we you your it its this that these
those what which who whom how when where why can could should would will shall may might please tell about give get kindly
and or but if then so with from by as into out up not no yes there here have has had been being""".split())

# Words that appear in almost every government question; they must not decide a match alone.
GENERIC = frozenset("apply application scheme yojana yojane online status check money benefit portal service help need want know".split())

# A question that names another country or Indian state is not about Karnataka.
OTHER_REGIONS = frozenset("""usa america uk england britain germany france japan china russia canada australia pakistan bangladesh
nepal lanka dubai uae singapore europe italy spain brazil mexico maharashtra tamil nadu kerala andhra telangana gujarat rajasthan
punjab haryana delhi bihar odisha bengal assam goa jharkhand uttarakhand chhattisgarh pradesh uttar madhya mumbai chennai
hyderabad kolkata pune jaipur lucknow patna bhopal""".split())

_SPOKEN_MIN_CHARS = 20


def _tokens(text: str) -> list[str]:
    return re.sub(r"[^a-z0-9]+", " ", text.lower()).split()


def _stem(tok: str) -> str:
    if len(tok) > 4 and tok.endswith("ies"):
        return tok[:-3] + "y"
    if len(tok) > 4 and tok.endswith("ing"):
        return tok[:-3]
    if len(tok) > 3 and tok.endswith("s") and not tok.endswith("ss"):
        return tok[:-1]
    return tok


def _features(text: str) -> dict[str, float]:
    feats: dict[str, float] = {}
    for tok in _tokens(text):
        if tok in STOPWORDS:
            continue
        tok = _stem(tok)
        if tok in GENERIC:
            feats["w:" + tok] = feats.get("w:" + tok, 0.0) + 0.25
            continue
        feats["w:" + tok] = feats.get("w:" + tok, 0.0) + 1.0
        padded = f"_{tok}_"
        for n in (3, 4):
            for i in range(len(padded) - n + 1):
                key = "c:" + padded[i:i + n]
                feats[key] = feats.get(key, 0.0) + 0.5
    return feats


@dataclass(frozen=True)
class KbEntry:
    id: str
    title: str
    questions: tuple[str, ...]
    keywords: tuple[str, ...]
    answer: str
    source_url: str


@dataclass(frozen=True)
class KbAnswer:
    text: str
    source_url: str
    entry_id: str
    score: float


def load_entries(path: Path, allowed_domains: tuple[str, ...]) -> tuple[list[KbEntry], list[tuple[str, str]]]:
    """(valid entries, [(entry id, reason it was skipped)])."""
    if not Path(path).exists():
        return [], []
    raw = json.loads(Path(path).read_text(encoding="utf-8"))
    entries: list[KbEntry] = []
    skipped: list[tuple[str, str]] = []
    seen: set[str] = set()
    for i, e in enumerate(raw.get("entries", [])):
        eid = str(e.get("id") or f"entry_{i}")
        answer = str(e.get("answer", "")).strip()
        questions = tuple(q.strip() for q in e.get("questions", []) if str(q).strip())
        source = str(e.get("source_url", "")).strip()
        if eid in seen:
            skipped.append((eid, "duplicate id")); continue
        if not answer or answer.upper().startswith("TODO"):
            skipped.append((eid, "answer not filled in yet (TODO)")); continue
        if len(answer) < _SPOKEN_MIN_CHARS:
            skipped.append((eid, "answer too short")); continue
        if not questions:
            skipped.append((eid, "no questions")); continue
        if not is_allowed_domain(source, allowed_domains):
            skipped.append((eid, f"source_url must be on {', '.join(allowed_domains)}")); continue
        seen.add(eid)
        entries.append(KbEntry(eid, str(e.get("title", eid)), questions,
                               tuple(str(k) for k in e.get("keywords", [])), answer, source))
    return entries, skipped


class KnowledgeBase:
    def __init__(self, entries: list[KbEntry], min_score: float = 0.50, min_margin: float = 0.05):
        self.entries = entries
        self.min_score = min_score
        self.min_margin = min_margin
        docs: list[tuple[int, dict[str, float]]] = []
        for idx, e in enumerate(entries):
            for text in (*e.questions, f"{e.title} {' '.join(e.keywords)}"):
                docs.append((idx, _features(text)))
        df: dict[str, int] = {}
        for _, feats in docs:
            for k in feats:
                df[k] = df.get(k, 0) + 1
        n = len(docs)
        self._idf = {k: math.log((1 + n) / (1 + d)) + 1.0 for k, d in df.items()}
        self._docs = [(idx, self._vector(feats)) for idx, feats in docs]

    def _vector(self, feats: dict[str, float]) -> dict[str, float]:
        vec = {k: tf * self._idf.get(k, 1.0) for k, tf in feats.items()}
        norm = math.sqrt(sum(v * v for v in vec.values())) or 1.0
        return {k: v / norm for k, v in vec.items()}

    def rank(self, question: str) -> list[tuple[KbEntry, float]]:
        """All entries with their best similarity, highest first."""
        qvec = self._vector(_features(question))
        best: dict[int, float] = {}
        for idx, dvec in self._docs:
            s = sum(w * dvec.get(k, 0.0) for k, w in qvec.items())
            if s > best.get(idx, 0.0):
                best[idx] = s
        return [(self.entries[i], s) for i, s in sorted(best.items(), key=lambda kv: -kv[1])]

    def answer(self, question: str) -> Optional[KbAnswer]:
        toks = set(_tokens(question))
        if toks & OTHER_REGIONS and "karnataka" not in toks:
            return None                       # about another country/state
        ranked = self.rank(question)
        if not ranked:
            return None
        top, top_score = ranked[0]
        runner_up = ranked[1][1] if len(ranked) > 1 else 0.0
        if top_score < self.min_score or (top_score - runner_up) < self.min_margin:
            return None
        return KbAnswer(top.answer, top.source_url, top.id, top_score)


class KbService:
    """Reloads the knowledge file automatically when it is edited (handy while preparing a demo)."""

    def __init__(self, settings: RagSettings):
        self.s = settings
        self._mtime: float | None = None
        self._kb: KnowledgeBase | None = None
        self.skipped: list[tuple[str, str]] = []

    def _ensure_loaded(self) -> Optional[KnowledgeBase]:
        path = Path(self.s.kb_file)
        if not path.exists():
            return None
        mtime = path.stat().st_mtime
        if self._kb is None or mtime != self._mtime:
            try:
                entries, self.skipped = load_entries(path, self.s.allowed_domains)
            except (OSError, ValueError) as exc:
                logger.error("Could not read %s: %s", path, exc)
                return self._kb
            self._kb = KnowledgeBase(entries, self.s.kb_min_score, self.s.kb_min_margin)
            self._mtime = mtime
            logger.info("Verified knowledge base loaded: %d active, %d skipped", len(entries), len(self.skipped))
        return self._kb

    def answer(self, question: str) -> Optional[KbAnswer]:
        kb = self._ensure_loaded()
        return kb.answer(question) if kb and kb.entries else None


_service: KbService | None = None


def get_kb_service() -> Optional[KbService]:
    global _service
    s = RagSettings.from_env()
    if not s.enabled:
        return None
    if _service is None or _service.s.kb_file != s.kb_file:
        _service = KbService(s)
    return _service
