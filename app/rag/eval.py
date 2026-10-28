"""
Tune RAG_THRESHOLD with evidence:   python -m app.rag.eval

Reads data/rag_eval.json (questions the index SHOULD answer, and ones it should NOT),
prints each best similarity score and recommends a threshold. It only embeds the
questions (one request each); it does not call the answer model.
"""
import asyncio
import json
from pathlib import Path

from app.rag.config import PROJECT_ROOT
from app.rag.retriever import get_rag_service


def recommend_threshold(in_scope: list[float], out_of_scope: list[float]):
    """(threshold, message). The midpoint of the gap when the two groups separate."""
    if not in_scope or not out_of_scope:
        return None, "Need at least one in-scope and one out-of-scope question."
    lowest_in, highest_out = min(in_scope), max(out_of_scope)
    if lowest_in > highest_out:
        return round((lowest_in + highest_out) / 2, 3), (
            f"Clean separation: lowest in-scope {lowest_in:.3f} > highest out-of-scope {highest_out:.3f}.")
    return None, (
        f"Overlap: lowest in-scope {lowest_in:.3f} <= highest out-of-scope {highest_out:.3f}. "
        "A threshold cannot fix this. Add official text for the weak topics (data/rag_docs/) "
        "or remove in-scope questions the index has no content for.")


async def _run(path: Path) -> None:
    svc = get_rag_service()
    if svc is None:
        raise SystemExit("RAG unavailable: set GEMINI_API_KEY and run `python -m app.rag.ingest` first.")
    data = json.loads(path.read_text(encoding="utf-8"))
    scores = {"in_scope": [], "out_of_scope": []}
    for group in scores:
        print(f"\n{group.replace('_', ' ').upper()}")
        for q in data.get(group, []):
            hits = await svc.search(q)
            best = hits[0] if hits else None
            score = best.score if best else 0.0
            scores[group].append(score)
            print(f"  {score:.3f}  {q}  ->  {best.chunk.url if best else '-'}")
            await asyncio.sleep(1.0)                      # stay inside the free-tier rate limit
    threshold, message = recommend_threshold(scores["in_scope"], scores["out_of_scope"])
    print(f"\n{message}")
    if threshold is not None:
        print(f"Suggested: RAG_THRESHOLD={threshold}   (current: {svc.s.similarity_threshold})")


if __name__ == "__main__":
    asyncio.run(_run(PROJECT_ROOT / "data" / "rag_eval.json"))
