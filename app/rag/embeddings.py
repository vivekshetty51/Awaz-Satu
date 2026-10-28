"""
Gemini embedding client (REST via httpx, same style as app/services/ai_agent.py).

The API key is sent in the `x-goog-api-key` header, never in the URL, so it
cannot leak into access logs or exception messages.
"""
from __future__ import annotations

import hashlib
import json
import time
from pathlib import Path
from typing import Protocol, Sequence

import httpx
import numpy as np

from app.core.logger import get_logger
from app.rag.config import RagSettings

logger = get_logger("awaaz_setu.rag.embeddings")

_BASE = "https://generativelanguage.googleapis.com/v1beta/models"


class Embedder(Protocol):
    """Anything that can turn texts into L2-normalised vectors."""

    async def embed_query(self, text: str) -> np.ndarray: ...

    def embed_documents(self, texts: Sequence[str], cache_path: Path | None = None) -> np.ndarray: ...


def _normalise(arr: np.ndarray) -> np.ndarray:
    arr = np.asarray(arr, dtype=np.float32)
    if arr.ndim == 1:
        arr = arr[None, :]
    return arr / (np.linalg.norm(arr, axis=1, keepdims=True) + 1e-9)


def _retry_wait(response, attempt: int) -> float:
    """Seconds to wait: the server's Retry-After if given, else 20s doubling up to 120s."""
    if response is not None:
        try:
            return min(float(response.headers.get("retry-after", "")), 180.0)
        except (TypeError, ValueError):
            pass
    return min(20.0 * 2 ** attempt, 120.0)


def _load_cache(path: Path | None) -> dict:
    if path and Path(path).exists():
        try:
            return json.loads(Path(path).read_text(encoding="utf-8"))
        except (OSError, ValueError):
            logger.warning("embedding cache unreadable; starting fresh")
    return {}


def _save_cache(path: Path | None, cache: dict) -> None:
    if path:
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        Path(path).write_text(json.dumps(cache), encoding="utf-8")


class GeminiEmbedder:
    def __init__(self, settings: RagSettings):
        self.s = settings
        self._headers = {
            "Content-Type": "application/json",
            "x-goog-api-key": settings.gemini_api_key,
        }

    def _request(self, text: str, task: str) -> dict:
        return {
            "model": f"models/{self.s.embed_model}",
            "content": {"parts": [{"text": text}]},
            "taskType": task,
            "outputDimensionality": self.s.embed_dim,
        }

    async def embed_query(self, text: str) -> np.ndarray:
        """Async: used on the live call path."""
        url = f"{_BASE}/{self.s.embed_model}:embedContent"
        timeout = httpx.Timeout(self.s.query_timeout_seconds, connect=2.0)
        async with httpx.AsyncClient(timeout=timeout) as client:
            r = await client.post(url, json=self._request(text, "RETRIEVAL_QUERY"),
                                  headers=self._headers)
            r.raise_for_status()
            return _normalise(np.array(r.json()["embedding"]["values"]))[0]

    def embed_documents(self, texts: Sequence[str], cache_path: Path | None = None) -> np.ndarray:
        """
        Sync, for the offline ingestion script only.

        Free-tier quotas are small, so: small batches, a pause between requests,
        Retry-After honoured, and a disk cache so an interrupted run resumes where it
        stopped instead of starting over.
        """
        url = f"{_BASE}/{self.s.embed_model}:batchEmbedContents"
        cache = _load_cache(cache_path)
        keys = [self._key(t) for t in texts]
        todo = [i for i, k in enumerate(keys) if k not in cache]
        logger.info("%d chunks: %d cached, %d to embed", len(texts), len(texts) - len(todo), len(todo))

        with httpx.Client(timeout=60.0) as client:
            for start in range(0, len(todo), self.s.embed_batch):
                idxs = todo[start:start + self.s.embed_batch]
                body = {"requests": [self._request(texts[i], "RETRIEVAL_DOCUMENT") for i in idxs]}
                vectors = self._post_with_retry(client, url, body)
                for i, vec in zip(idxs, vectors):
                    cache[keys[i]] = [round(float(x), 6) for x in vec]
                _save_cache(cache_path, cache)
                logger.info("embedded %d/%d", min(start + len(idxs), len(todo)), len(todo))
                if start + self.s.embed_batch < len(todo):
                    time.sleep(self.s.embed_pause_seconds)
        return _normalise(np.array([cache[k] for k in keys]))

    def cached_subset(self, texts: Sequence[str], cache_path: Path | None):
        """(indices, vectors) for the texts already embedded in the cache."""
        cache = _load_cache(cache_path)
        idxs = [i for i, t in enumerate(texts) if self._key(t) in cache]
        if not idxs:
            return [], np.zeros((0, self.s.embed_dim), dtype=np.float32)
        return idxs, _normalise(np.array([cache[self._key(texts[i])] for i in idxs]))

    def _key(self, text: str) -> str:
        raw = f"{self.s.embed_model}|{self.s.embed_dim}|{text}"
        return hashlib.sha1(raw.encode("utf-8")).hexdigest()

    def _post_with_retry(self, client, url: str, body: dict) -> list[list[float]]:
        for attempt in range(self.s.embed_max_retries):
            try:
                r = client.post(url, json=body, headers=self._headers)
                r.raise_for_status()
                return [e["values"] for e in r.json()["embeddings"]]
            except httpx.HTTPStatusError as exc:
                status = exc.response.status_code
                if status in (400, 401, 403, 404):       # a retry cannot fix these
                    raise RuntimeError(
                        f"Embedding request rejected (HTTP {status}). Check GEMINI_API_KEY and RAG_EMBED_MODEL."
                    ) from exc
                wait = _retry_wait(exc.response, attempt)
                logger.warning("embed HTTP %s; retry %d/%d in %ss", status, attempt + 1,
                               self.s.embed_max_retries, wait)
                time.sleep(wait)
            except httpx.HTTPError as exc:
                wait = _retry_wait(None, attempt)
                logger.warning("embed network error (%s); retry in %ss", exc.__class__.__name__, wait)
                time.sleep(wait)
        raise RuntimeError(
            "Embedding failed after retries (quota). Run the same command again later: "
            "progress is cached and will resume."
        )
