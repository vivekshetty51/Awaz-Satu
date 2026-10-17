# Awaaz Setu

Voice-first access layer to India's DPI. A caller talks to an AI agent over WebRTC (LiveKit).

```
Awaz-Setu/
├── backend/    LiveKit agent (agent.py) + token server (token_server.py)
├── frontend/   React + Vite "Virtual Phone Dialer"
└── (mock_api/, llm/, speech/ added by teammates)
```

## Run (3 terminals)

```bash
# 1. Agent
cd backend
python -m venv venv && source venv/bin/activate   # Windows: venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env        # fill in LiveKit Cloud keys
python agent.py dev

# 2. Token server (same venv)
cd backend && uvicorn token_server:app --port 8001 --reload

# 3. Frontend
cd frontend
npm install
npm run dev                 # open the URL Vite prints, press Call Agent
```

Ports: token server 8001, mock DPI API 8000, frontend 5173.
