"""
Check and test the verified knowledge base (instant, offline, no API calls).

    python -m app.rag.kb_check                      # validate entries + self-test + leak test
    python -m app.rag.kb_check "your question"      # see how a question would be answered
"""
import json
import sys

from app.rag.config import PROJECT_ROOT, RagSettings
from app.rag.kb import KnowledgeBase, load_entries


def main() -> None:
    s = RagSettings.from_env()
    entries, skipped = load_entries(s.kb_file, s.allowed_domains)
    kb = KnowledgeBase(entries, s.kb_min_score, s.kb_min_margin)

    if len(sys.argv) > 1:                                       # one question
        q = " ".join(sys.argv[1:])
        hit = kb.answer(q)
        for e, score in kb.rank(q)[:3]:
            print(f"  {score:.3f}  {e.id}")
        print("\nANSWER:", hit.text if hit else "none -> would continue to RAG / general Gemini")
        if hit:
            print("SOURCE:", hit.source_url)
        return

    print(f"Knowledge file: {s.kb_file}")
    print(f"\nACTIVE ENTRIES ({len(entries)})")
    for e in entries:
        print(f"  ok   {e.id:22s} {len(e.questions)} questions  <- {e.source_url}")
    print(f"\nNOT ACTIVE YET ({len(skipped)})")
    for eid, reason in skipped:
        print(f"  --   {eid:22s} {reason}")

    problems = 0
    print("\nSELF-TEST: every stored question must return its own entry")
    for e in entries:
        for q in e.questions:
            hit = kb.answer(q)
            if hit is None or hit.entry_id != e.id:
                problems += 1
                got = hit.entry_id if hit else "no confident match"
                print(f"  FAIL  [{e.id}] \"{q}\" -> {got}  (add keywords/questions, or merge similar entries)")
    if not problems:
        print("  all passed")

    eval_file = PROJECT_ROOT / "data" / "rag_eval.json"
    if eval_file.exists() and entries:
        out = json.loads(eval_file.read_text(encoding="utf-8")).get("out_of_scope", [])
        print("\nLEAK TEST: out-of-scope questions must NOT get a verified answer")
        leaks = 0
        for q in out:
            hit = kb.answer(q)
            if hit:
                leaks += 1
                print(f"  LEAK  \"{q}\" -> {hit.entry_id} ({hit.score:.2f})")
        print("  none leaked" if not leaks else f"  {leaks} leaked: raise RAG_KB_THRESHOLD or tighten keywords")
        problems += leaks
    print("\nRESULT:", "OK" if not problems else f"{problems} problem(s) to fix")


if __name__ == "__main__":
    main()
