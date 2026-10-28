"""
RAG configuration (12-factor: every value can be overridden by an env var).

Kept dependency-free (stdlib dataclass) so the ingestion script and unit tests
do not need the full web stack.
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]


def _load_env_files() -> None:
    """Export values from .env / backend/.env into os.environ (real env vars win).

    pydantic-settings reads these files but does not export them, while the
    Gemini bridge and RAG read os.environ, so we load them once here.
    """
    try:
        from dotenv import load_dotenv
    except ImportError:  # python-dotenv is optional at import time
        return
    for candidate in (PROJECT_ROOT / ".env", PROJECT_ROOT / "backend" / ".env"):
        if candidate.exists():
            load_dotenv(candidate, override=False)


_load_env_files()

# ONLY these domains (and their subdomains) are ever crawled or cited.
DEFAULT_ALLOWED_DOMAINS = ("karnataka.gov.in", "kar.nic.in")


def _env_float(name: str, default: float) -> float:
    try:
        return float(os.getenv(name, default))
    except ValueError:
        return default


def _env_int(name: str, default: int) -> int:
    try:
        return int(os.getenv(name, default))
    except ValueError:
        return default


@dataclass(frozen=True)
class RagSettings:
    enabled: bool = True
    gemini_api_key: str = ""
    embed_model: str = "gemini-embedding-001"
    embed_dim: int = 768
    generation_model: str = "gemini-flash-latest"
    # Tried in order when the primary model answers 503 (high demand), 429 (quota) or 404 (retired).
    # Each Gemini model has its own free-tier counters, so a second model keeps answers flowing.
    fallback_models: tuple[str, ...] = ("gemini-flash-lite-latest",)
    index_dir: Path = PROJECT_ROOT / "data" / "rag_index"
    sources_file: Path = PROJECT_ROOT / "data" / "rag_sources.json"
    local_docs_dir: Path = PROJECT_ROOT / "data" / "rag_docs"
    kb_file: Path = PROJECT_ROOT / "data" / "kb" / "verified_answers.json"
    # Verified-answer matching: minimum similarity, and the lead the best entry must have over the
    # runner-up (so two similar schemes are never confused). Measured on sample questions.
    kb_min_score: float = 0.50
    kb_min_margin: float = 0.05
    top_k: int = 4
    # Minimum cosine similarity of the BEST chunk before we try to answer from
    # the official sources. Tune with `python -m app.rag.ask "question"`.
    similarity_threshold: float = 0.60
    query_timeout_seconds: float = 4.0        # embedding of the caller's question
    generation_timeout_seconds: float = 12.0  # Gemini answer; flash-latest can take several seconds
    allowed_domains: tuple[str, ...] = field(default=DEFAULT_ALLOWED_DOMAINS)
    max_pages_per_seed: int = 25
    crawl_depth: int = 2            # seed page = depth 0
    same_host_only: bool = True     # follow links only on the seed's own site
    english_only: bool = True       # drop Kannada/Hindi chunks while the system is English-only
    crawl_delay_seconds: float = 1.0
    # Free-tier embedding quotas are small: send few texts per request and pause between requests.
    embed_batch: int = 20
    embed_pause_seconds: float = 12.0
    embed_max_retries: int = 8
    chunk_chars: int = 900
    chunk_overlap: int = 150
    user_agent: str = "AwaazSetuBot/1.0 (hackathon; reads public government pages)"

    @classmethod
    def from_env(cls) -> "RagSettings":
        domains = os.getenv("RAG_ALLOWED_DOMAINS", "")
        parsed = tuple(d.strip().lower() for d in domains.split(",") if d.strip())
        return cls(
            enabled=os.getenv("RAG_ENABLED", "true").strip().lower() not in ("0", "false", "no"),
            gemini_api_key=(os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY") or "").strip(),
            embed_model=os.getenv("RAG_EMBED_MODEL", cls.embed_model),
            generation_model=os.getenv("GEMINI_MODEL", cls.generation_model),
            fallback_models=tuple(m.strip() for m in os.getenv(
                "RAG_FALLBACK_MODELS", ",".join(cls.fallback_models)).split(",") if m.strip()),
            index_dir=Path(os.getenv("RAG_INDEX_DIR", str(cls.index_dir))),
            sources_file=Path(os.getenv("RAG_SOURCES_FILE", str(cls.sources_file))),
            top_k=_env_int("RAG_TOP_K", cls.top_k),
            kb_file=Path(os.getenv("RAG_KB_FILE", str(cls.kb_file))),
            kb_min_score=_env_float("RAG_KB_THRESHOLD", cls.kb_min_score),
            generation_timeout_seconds=_env_float("RAG_GEN_TIMEOUT", cls.generation_timeout_seconds),
            embed_batch=_env_int("RAG_EMBED_BATCH", cls.embed_batch),
            embed_pause_seconds=_env_float("RAG_EMBED_PAUSE", cls.embed_pause_seconds),
            embed_max_retries=_env_int("RAG_EMBED_RETRIES", cls.embed_max_retries),
            max_pages_per_seed=_env_int("RAG_MAX_PAGES", cls.max_pages_per_seed),
            crawl_depth=_env_int("RAG_CRAWL_DEPTH", cls.crawl_depth),
            english_only=os.getenv("ENGLISH_ONLY", "true").strip().lower() not in ("0", "false", "no"),
            similarity_threshold=_env_float("RAG_THRESHOLD", cls.similarity_threshold),
            allowed_domains=parsed or DEFAULT_ALLOWED_DOMAINS,
        )
