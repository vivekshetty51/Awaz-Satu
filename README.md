# Awaaz Setu

Voice-first, toll-free access layer to India's Digital Public Infrastructure.
A caller talks to an AI assistant over WebRTC (LiveKit); answers about Karnataka
government schemes come from official sources (RAG), everything else from Gemini.

## Architecture
```
Browser dialer (frontend/) --WebRTC--> LiveKit --> backend/agent.py
                                                      |  POST /process-voice-turn
                                                      v
   Voice Engine (app/main.py): ASR -> knowledge routing -> TTS
        knowledge routing: decision tree -> RAG (app/rag) -> Gemini -> offline fallback
```
See `architecture_log.md` (ADRs) and `docs/RAG.md`.

## Layout
| Path | Purpose |
|---|---|
| `app/` | Voice Engine (FastAPI): ASR, TTS, intent routing, Gemini bridge |
| `app/rag/` | RAG over Karnataka government sources |
| `backend/` | LiveKit agent worker + token server |
| `frontend/` | React + Vite virtual phone dialer |
| `data/rag_sources.json` | Crawler seed URLs |
| `tests/` | Offline unit tests |

Language: English only for now (`ENGLISH_ONLY=true`). Speech recognition: faster-whisper (`WHISPER_MODEL=base.en`) or Groq.

## Run (use Python 3.12)
```bash
pip install -r requirements.txt
cp backend/.env.example backend/.env      # fill in LiveKit + GEMINI_API_KEY (+ GROQ_API_KEY)
python -m app.rag.ingest                  # once: build the Karnataka knowledge index

# 4 terminals
uvicorn app.main:app --port 8000          # Voice Engine
cd backend && python agent.py dev         # LiveKit agent
cd backend && uvicorn token_server:app --port 8001
cd frontend && npm install && npm run dev # http://localhost:5173
```
Ports: Voice Engine 8000, token server 8001, frontend 5173.

## Tests
```bash
python -m unittest discover -s tests -v
```
Never commit `.env`. Secrets are read from environment variables only.
