"""
Terminal tester:   python -m app.rag.ask "How do I apply for Gruha Lakshmi?"
Shows the best similarity score so you can tune RAG_THRESHOLD.
"""
import asyncio
import sys

import httpx

from app.rag.retriever import get_rag_service


async def _run(q: str) -> None:
    svc = get_rag_service()
    if svc is None:
        raise SystemExit("RAG unavailable: set GEMINI_API_KEY and run `python -m app.rag.ingest` first.")
    try:
        hits = await svc.search(q)
    except httpx.HTTPStatusError as exc:
        code = exc.response.status_code
        hint = " (free-tier quota used up: wait a few minutes, or until the daily reset)" if code == 429 else ""
        raise SystemExit(f"Embedding request failed: HTTP {code}{hint}")
    except httpx.HTTPError as exc:
        raise SystemExit(f"Network problem while embedding the question: {exc.__class__.__name__}")
    for h in hits:
        print(f"  {h.score:.3f}  {h.chunk.url}")
    ans = await svc.answer(q)
    if ans is None:
        print("\nROUTE : out of scope -> would go to general Gemini")
    else:
        print(f"\nROUTE : rag (official Karnataka source)\nANSWER: {ans.text}")
        for u in ans.sources:
            print("SOURCE:", u)


if __name__ == "__main__":
    asyncio.run(_run(" ".join(sys.argv[1:]) or input("Question: ")))
