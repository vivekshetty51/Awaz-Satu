# RAG over official Karnataka Government sources

## What it does
A caller's question is answered in this order (`app/services/ai_agent.py::query_ai_agent`):

See also docs/KNOWLEDGE_BASE.md: a verified-answer layer now sits between the decision tree and generative RAG.

| # | Layer | Handles | Source of truth |
|---|-------|---------|-----------------|
| 1 | Decision tree (optional plugin) | Designed flows: pension, scholarship... | Team-authored tree |
| 2 | RAG (`app/rag`) | Other Karnataka government questions | Crawled `karnataka.gov.in` / `kar.nic.in` pages |
| 3 | Gemini | Everything else (general questions) | Gemini, labelled as a general answer |
| 4 | Offline fallback | Gemini down or quota hit | `classify_intent` |

The UI card shows **Karnataka Govt Source (Official)** for layer 2, **Karnataka Govt Scheme Guide** for layer 1.

## How RAG decides "in scope"
Two gates, both must pass:
1. **Retrieval gate**: best cosine similarity >= `RAG_THRESHOLD` (default 0.60).
2. **Grounding gate**: Gemini is told to answer ONLY from the retrieved text, else reply `NOT_FOUND`.
Failing either gate (or any error) returns `None`, and the question moves on to Gemini.

## Decision-tree contract (for the teammate building it)
Create `app/services/decision_tree.py` exposing:
```python
def resolve(text_query: str, phone: str) -> str | None:   # may also be `async def`
    """Return the spoken answer, or None if no node matches."""
```
No other wiring is needed; it is picked up automatically.

## Setup
```bash
pip install -r requirements.txt
# backend/.env  ->  GEMINI_API_KEY=...
python -m app.rag.ingest            # crawl + embed (once, and when pages change)
python -m app.rag.ask "How do I apply for Gruha Lakshmi?"
```
Edit `data/rag_sources.json` to add scheme pages. Only domains in `RAG_ALLOWED_DOMAINS`
(default `karnataka.gov.in`, `kar.nic.in`) are fetched; look-alike domains are rejected and `robots.txt` is honoured.

## Tuning
`python -m app.rag.ask` prints the similarity score of each retrieved chunk.
In-scope questions routed to Gemini -> lower `RAG_THRESHOLD`. Unrelated questions answered as official -> raise it.

## Safety notes
- Answers about amounts/dates come only from retrieved official text; the prompt forbids inventing them.
- Crawled text is treated as data: the prompt tells the model to ignore instructions inside it.
- The Gemini API key is sent in a header (never in a URL) by all RAG code.
- The index (`data/rag_index/`) is generated and git-ignored.

## Languages
The system currently runs **English only** (`ENGLISH_ONLY=true`): ASR, replies and TTS are all English.
Embeddings are multilingual and the index is English, so when regional languages are added later (`ENGLISH_ONLY=false`),
evaluate Kannada/Hindi retrieval quality before claiming support.
