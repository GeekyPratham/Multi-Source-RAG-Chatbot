# 🔎 InsightAgent AI

**React + FastAPI full-stack app** — RAG Agentic Assistant + LLM Recommender.

Each user brings their own [Groq API key](https://console.groq.com) — entered in the UI, never stored server-side.

---

## Project Structure

```
insightagent/
│
├── backend/                     ← FastAPI Python backend
│   ├── main.py                  ← Entry point: uvicorn main:app
│   ├── requirements.txt
│   ├── Dockerfile
│   ├── .env.example
│   └── app/
│       ├── api/
│       │   ├── auth.py          ← POST /api/auth/validate
│       │   ├── chat.py          ← POST /api/chat
│       │   ├── recommend.py     ← POST /api/recommend
│       │   └── sources.py       ← POST /api/sources/url + /pdf
│       ├── core/
│       │   ├── models.py        ← Pydantic schemas
│       │   └── memory.py        ← Conversation history helpers
│       └── services/
│           ├── agent_service.py      ← LangChain agent runner
│           ├── recommender_service.py← LLM recommender logic
│           ├── embeddings.py         ← Singleton HuggingFace model
│           ├── vector_store.py       ← ChromaDB persistent store
│           ├── pdf_service.py        ← PDF loader + indexer
│           ├── url_service.py        ← URL loader + indexer
│           └── session_store.py      ← Per-user tool registry
│
├── frontend/                    ← React + Tailwind frontend
│   ├── src/
│   │   ├── App.jsx
│   │   ├── pages/
│   │   │   ├── ApiKeyGate.jsx   ← First screen — enter Groq key
│   │   │   ├── ChatPage.jsx     ← RAG assistant chat
│   │   │   └── RecommendPage.jsx← LLM recommender
│   │   ├── components/
│   │   │   ├── chat/            ← ChatMessage, ChatInput, SourcesPanel, ModelSelector
│   │   │   ├── recommender/     ← RecommendCard
│   │   │   └── layout/          ← Layout, sidebar nav
│   │   ├── hooks/
│   │   │   ├── useApiKey.js     ← Manages key in localStorage
│   │   │   └── useSession.js    ← Session ID per browser tab
│   │   └── services/api.js      ← All Axios API calls
│   ├── package.json
│   ├── vite.config.js           ← Dev proxy: /api → localhost:8000
│   ├── tailwind.config.js
│   ├── Dockerfile
│   └── nginx.conf
│
├── docker-compose.yml           ← Run both with one command
└── README.md
```

---

## ⚡ Run Locally (Recommended)

Run backend and frontend in **two separate terminals**.

### Terminal 1 — Backend

```bash
cd backend

# Create virtual environment
python -m venv .venv

# Activate it
# Windows:
.venv\Scripts\activate
# macOS/Linux:
source .venv/bin/activate

# Install dependencies (first run only — takes ~3 min)
pip install -r requirements.txt

# Copy env file (no changes needed for local dev)
cp .env.example .env

# Start backend
uvicorn main:app --reload --port 8000
```

Backend runs at: **http://localhost:8000**
API docs at: **http://localhost:8000/docs**

---

### Terminal 2 — Frontend

```bash
cd frontend

# Install Node dependencies (first run only)
npm install

# Copy env file (no changes needed — Vite proxy handles /api)
cp .env.example .env

# Start frontend dev server
npm run dev
```

Frontend runs at: **http://localhost:5173**

---

### First time you open the app

1. Open **http://localhost:5173**
2. You'll see the **API Key screen** — enter your Groq key (`gsk_...`)
3. Get a free key at https://console.groq.com
4. Click **Validate & Continue**
5. Your key is saved in your browser's localStorage — you won't need to enter it again

---

## 🐳 Docker (Both Together)

```bash
# From project root
docker compose up --build
```

- Frontend: **http://localhost:3000**
- Backend API: **http://localhost:8000**

---

## ☁️ Deploy to Cloud

### Option A — Streamlit Community Cloud is NOT applicable here.
Use one of the options below.

### Option B — Railway (easiest, free tier available)

**Backend:**
```bash
cd backend
railway init
railway up
# Set env var: ALLOWED_ORIGINS=https://your-frontend.vercel.app
```

**Frontend:**
```bash
cd frontend
# Create .env.production
echo "VITE_API_URL=https://your-railway-backend.up.railway.app" > .env.production
npm run build
# Deploy dist/ to Vercel or Netlify
```

### Option C — Vercel (frontend) + Render (backend)

**Backend on Render:**
1. New Web Service → connect GitHub repo
2. Root directory: `backend`
3. Build command: `pip install -r requirements.txt`
4. Start command: `uvicorn main:app --host 0.0.0.0 --port $PORT`
5. Add env var: `ALLOWED_ORIGINS=https://your-frontend.vercel.app`

**Frontend on Vercel:**
1. Import repo → set root directory to `frontend`
2. Add env var: `VITE_API_URL=https://your-render-backend.onrender.com`
3. Deploy

---

## 🔑 How API Keys Work

- Each user enters their own **Groq API key** in the browser UI
- The key is stored in **localStorage** (browser only, never on the server)
- Every request sends the key to the backend, which uses it for that request only
- The server has **no stored API keys** — users control their own access
- To change key: click **"Change API Key"** in the sidebar

---

## 🧠 Features

| Feature | Description |
|---|---|
| 🔎 RAG Chat | LangChain agent with DuckDuckGo, Arxiv, Wikipedia |
| 📕 PDF Chat | Upload PDFs, ask questions from them |
| 🌐 URL Knowledge | Add any webpage, query its content |
| 🧠 Memory | Follows up naturally ("what about them?") |
| 💾 Persistent Vectors | ChromaDB — PDFs/URLs embedded once, reused forever |
| ✨ LLM Recommender | Enter a task, get ranked free+paid LLM recommendations |
| 🔧 Tool Trace | Expandable view of every tool call the agent made |
| 🤖 Model Selector | Switch between Groq models in the chat header |

---

## 📋 Requirements

- Python 3.10+
- Node.js 18+
- Free Groq API key: https://console.groq.com
