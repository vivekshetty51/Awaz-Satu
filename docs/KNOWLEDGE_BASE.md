# Verified knowledge base (the demo's in-scope answers)

## Answer order for every caller question
1. **Decision tree** (team plugin, optional) -> 2. **Verified KB** (instant, offline) -> 3. **RAG** over crawled/local official documents (Gemini writes the answer) -> 4. **Gemini** for everything else -> 5. offline fallback.

The Verified KB never calls an LLM: no delay, no quota, no 503 errors, and no invented amounts. The UI labels its answers "Karnataka Govt Source (Official)" and cites the official page.

## Fill it in (about 15 minutes for the 12 prepared slots)
1. Open `data/kb/verified_answers.json`.
2. For each entry whose answer starts with `TODO`: open the OFFICIAL page in your browser (the `source_url`), and write 1 to 3 short spoken sentences that say only what the page says. Replace `source_url` with the exact page. It must be on `karnataka.gov.in` or `kar.nic.in`, otherwise the entry is ignored.
3. Write numbers in words for speech. Add the questions people really ask, and spelling variants in `keywords` (for example `gruha laxmi`).
4. Do not copy amounts from news sites or blogs: sources disagree (for example, public articles quote very different Sandhya Suraksha amounts) and amounts change.

## Check it (instant, offline)
```
python -m app.rag.kb_check                           # validates, self-tests, and leak-tests
python -m app.rag.kb_check "how do I get a pension"  # shows how one question is answered
```
The file reloads automatically when saved; no restart is needed.

## How matching works
Word + character-piece TF-IDF, so ASR misspellings still match ("sandya suraksha", "gruha laxmi"). Generic words ("apply", "scheme") carry little weight. Questions naming other countries/states are rejected. The best entry must score at least 0.50 (`RAG_KB_THRESHOLD`) and beat the runner-up by 0.05, so similar schemes are never guessed. Measured on 22 in-scope and 15 out-of-scope sample questions; re-run `kb_check` after you add entries.

## Limits
- Only what the team verified is answered with certainty. Other questions go to RAG/Gemini.
- English only for now (ENGLISH_ONLY=true).
