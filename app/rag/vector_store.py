"""Tiny persistent numpy vector store (cosine similarity). No database needed."""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

import numpy as np


@dataclass(frozen=True)
class Chunk:
    text: str
    url: str
    title: str


@dataclass(frozen=True)
class Hit:
    chunk: Chunk
    score: float


class VectorStore:
    def __init__(self, vectors: np.ndarray, chunks: list[Chunk]):
        if len(vectors) != len(chunks):
            raise ValueError("vectors and chunks must have the same length")
        self.vectors = vectors.astype(np.float32)
        self.chunks = chunks

    def __len__(self) -> int:
        return len(self.chunks)

    def search(self, query_vec: np.ndarray, k: int) -> list[Hit]:
        if not len(self):
            return []
        scores = self.vectors @ query_vec.astype(np.float32)
        top = np.argsort(-scores)[:k]
        return [Hit(self.chunks[i], float(scores[i])) for i in top]

    def save(self, directory: Path) -> None:
        directory.mkdir(parents=True, exist_ok=True)
        np.save(directory / "vectors.npy", self.vectors)
        (directory / "chunks.json").write_text(
            json.dumps([c.__dict__ for c in self.chunks], ensure_ascii=False),
            encoding="utf-8",
        )

    @classmethod
    def load(cls, directory: Path) -> "VectorStore | None":
        vp, cp = directory / "vectors.npy", directory / "chunks.json"
        if not (vp.exists() and cp.exists()):
            return None
        chunks = [Chunk(**c) for c in json.loads(cp.read_text(encoding="utf-8"))]
        return cls(np.load(vp), chunks)
