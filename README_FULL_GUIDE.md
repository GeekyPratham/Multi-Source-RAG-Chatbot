# InsightAgent AI — Complete Development & Architecture Guide

## Project Overview

**InsightAgent AI** is a full-stack RAG (Retrieval-Augmented Generation) chatbot with:
- **Multi-provider LLM support** (Groq, OpenAI, Anthropic, DeepSeek, Mistral, Together, OpenRouter, Perplexity, Ollama, and any OpenAI-compatible API)
- **User authentication** with JWT access/refresh token rotation
- **Document management** (PDF uploads + URL scraping with RAG)
- **AI-powered research agent** with web search, academic papers (Arxiv), Wikipedia, and custom source tools
- **Session-based chat** with conversation memory
- **Rate limiting** via Redis/Upstash
- **API key encryption** at rest using Fernet

---

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────────────┐
│                        FRONTEND (React + Vite)                      │
│  ┌────────────┬───────────────┬──────────────┬──────────────────┐  │
│  │ Login/Signup│ Settings      │ Chat Page    │ Recommender      │  │
│  │ Pages      │ (API Key,     │ (Agent with  │ (LLM             │  │
│  │            │  Provider,    │  Tools,       │  Recommendation) │  │
│  │            │  Model Config)│  Sources)     │                  │  │
│  └──────┬─────┴───────┬───────┴──────┬───────┴────────┬─────────┘  │
│         │             │              │                │            │
│         └─────────────┴──────────────┴────────────────┘            │
│                         Axios HTTP Client                          │
│                     Auto-refresh on 401                            │
└─────────────────────────────────────────────────────────────────────┘
         │
         │ HTTP (localhost:5173 → localhost:8000 via Vite proxy)
         ▼
┌─────────────────────────────────────────────────────────────────────-┐
│                    BACKEND (FastAPI + Python 3.11)                   │
│                                                                      │
│  ┌──────────────────────────────────────────────────────────────-┐   │
│  │  API Routes                   │  Middleware                   │   │
│  │  ├─ /api/auth/*               │  ├─ JWT Auth (get_current_)   │   │
│  │  │  signup, login, logout,    │  ├─ Rate Limit (Redis)        │   │
│  │  │  refresh/v2, me            │  └─ CORS                      │   │
│  │  ├─ /api/settings             │                               │   │
│  │  │  GET (read), PUT (update), │                               │   │
│  │  │  POST /test (connection)   │                               │   │
│  │  ├─ /api/chat                 │                               │   │
│  │  │  POST (RAG agent)          │                               │   │
│  │  ├─ /api/sources/*            │                               │   │
│  │  │  URL, PDF, list, delete    │                               │   │
│  │  └─ /api/recommend            │                               │   │
│  │     POST (LLM recommendations)│                               │   │
│  └───────────────────────────────────────────────────────────────┘   │
│                                                                      │
│  ┌──────────────────────────────────────────────────────────────┐   │
│  │  Services Layer (Business Logic)                             │   │
│  │  ├─ auth_service.py     JWT, refresh tokens, passwords       │   │
│  │  ├─ agent_service.py    LangChain agent, tool orchestration  │   │
│  │  ├─ providers.py        LLM abstractions + tenacity retry    │   │
│  │  ├─ pdf_service.py      PDF → chunks → Chroma → tool         │   │
│  │  ├─ url_service.py      URL → scrape → chunks → Chroma→tool  │   │
│  │  ├─ session_store.py    In-memory per-session tool registry  │   │
│  │  ├─ vector_store.py     ChromaDB integration                 │   │
│  │  ├─ redis_service.py    Upstash/local Redis abstraction      │   │
│  │  └─ recommender_service.py  LLM recommendations              │   │
│  └──────────────────────────────────────────────────────────────┘   │
│                                                                      │
│  ┌──────────────────────────────────────────────────────────────┐   │
│  │  Core Layer (Models, DB, Schemas)                            │   │
│  │  ├─ models_db.py     SQLAlchemy ORM (User, Doc, Chunk, RT)  │   │
│  │  ├─ models.py        Pydantic request schemas               │   │
│  │  ├─ schemas.py       Pydantic response schemas              │   │
│  │  ├─ database.py      PostgreSQL async engine                 │   │
│  │  └─ memory.py        Conversation history formatting         │   │
│  └──────────────────────────────────────────────────────────────┘   │
│                                                                      │
│  ┌──────────────────────────────────────────────────────────────┐   │
│  │  External Integrations                                       │   │
│  │  ├─ LangChain (agent, tools, retrievers)                     │   │
│  │  ├─ 9+ LLM provider APIs via direct HTTP or SDK              │   │
│  │  ├─ ChromaDB (persistent vector store)                       │   │
│  │  ├─ DuckDuckGo, Arxiv, Wikipedia (built-in tools)            │   │
│  │  ├─ Upstash Redis (rate limiting, refresh tokens)            │   │
│  │  └─ sentence-transformers (embeddings)                       │   │
│  └──────────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────────┘
         │
         ▼
┌─────────────────────────────────────────────────────────────────────┐
│  DATABASES & STORAGE                                               │
│  ├─ PostgreSQL (Neon.tech) — users, documents, chunks, tokens     │
│  ├─ ChromaDB (local filesystem) — vector embeddings for RAG       │
│  └─ Upstash Redis — session state, rate limit counters, tokens    │
└─────────────────────────────────────────────────────────────────────┘
```

---

## Database Schema (PostgreSQL)

```sql
-- Users table — stores account + LLM configuration
users (
  id: UUID (PK, auto-gen),
  email: VARCHAR(255) (unique, indexed),
  password_hash: VARCHAR(255),
  display_name: VARCHAR(100),                  -- nullable
  llm_provider: VARCHAR(50),                   -- nullable, free-text (groq, openai, deepseek, etc.)
  llm_api_key_encrypted: TEXT,                 -- nullable, Fernet-encrypted
  llm_model: VARCHAR(100),                     -- nullable
  temperature: FLOAT (default 0.7),
  llm_base_url: VARCHAR(500),                  -- nullable, for custom endpoints
  created_at: TIMESTAMPTZ,
  updated_at: TIMESTAMPTZ
)

-- Documents (uploaded PDFs / added URLs)
documents (
  id: UUID (PK),
  user_id: UUID (FK → users.id),
  title: VARCHAR(500),
  source_type: VARCHAR(10) ("url" | "pdf"),
  source_uri: TEXT,                            -- URL or original filename
  source_hash: VARCHAR(64),                    -- SHA-256 for per-user dedup
  chunk_count: INT (default 0),
  created_at: TIMESTAMPTZ,
  UNIQUE(user_id, source_hash)                 -- one user cannot have same doc twice
)

-- Chunks (document pieces for RAG)
chunks (
  id: UUID (PK),
  doc_id: UUID (FK → documents.id),
  chunk_index: INT,
  content_hash: VARCHAR(64),                   -- SHA-256 of chunk text
  text: TEXT,
  metadata_json: JSONB,                        -- nullable
)

-- Refresh tokens (JWT rotation audit)
refresh_tokens (
  id: UUID (PK),
  user_id: UUID (FK → users.id),
  token_hash: VARCHAR(128) (unique),
  expires_at: TIMESTAMPTZ,
  created_at: TIMESTAMPTZ
)
```

---

## Complete User Flow (End-to-End)

### 1. Authentication Flow

```
┌─────────┐
│ SIGNUP  │
└────┬────┘
     │ POST /api/auth/signup
     │ { email, password, display_name }
     ▼
[Backend]
  ├─ Validate email format + password length (≥8 chars)
  ├─ Hash password with bcrypt
  ├─ Create User row in PostgreSQL
  ├─ Generate JWT access_token (15 min expiry)
  ├─ Generate refresh_token (7 days expiry)
  │  ├─ Store hash in refresh_tokens table (DB)
  │  └─ Store raw token in Redis (for fast lookup)
  └─ Return { access_token, refresh_token, user }
     │
     ▼
[Frontend]
  ├─ Store access_token → localStorage['insightagent_access_token']
  ├─ Store refresh_token → localStorage['insightagent_refresh_token']
  ├─ Store user_id → localStorage['insightagent_user_id']
  └─ Redirect to /settings (first-time setup)


┌─────────┐
│ LOGIN   │
└────┬────┘
     │ POST /api/auth/login
     │ { email, password }
     ▼
[Backend]
  ├─ Look up user by email
  ├─ Verify password with bcrypt
  ├─ Issue new token pair
  └─ Return { access_token, refresh_token, user }

┌───────────┐
│ TOKEN     │
│ REFRESH   │
└────┬──────┘
     │ POST /api/auth/refresh/v2
     │ { refresh_token, user_id }
     │ (Triggered automatically by frontend on 401)
     ▼
[Backend]
  ├─ Look up token hash in Redis
  ├─ Verify against DB record
  ├─ Rotate: invalidate old token, issue new pair
  └─ Return { access_token, refresh_token }

┌───────────┐
│ LOGOUT    │
└────┬──────┘
     │ POST /api/auth/logout
     ▼
[Backend]
  ├─ Delete refresh token from Redis
  ├─ Delete from DB
  └─ (Frontend clears localStorage)
```

### 2. Settings Configuration

```
┌──────────────────────┐
│ /settings page       │
└────┬─────────────────┘
     │
     │ GET /api/settings (on page load)
     ▼
[Backend returns current config]
  └─ { llm_provider, llm_model, temperature, has_api_key,
       display_name, llm_base_url, llm_api_key (decrypted) }

     │
     │ User fills in:
     │ • Display Name
     │ • Provider (free text: groq, openai, deepseek, etc.)
     │ • API Key 🔒 (masked by default, eye button to toggle)
     │ • Model Name
     │ • Temperature slider (0.0 - 2.0)
     │ • Base URL (optional, for custom endpoints)
     │
     │ PUT /api/settings
     │ { llm_provider, llm_api_key, llm_model, temperature, ... }
     ▼
[Backend]
  ├─ Encrypt API key with Fernet: encrypt_api_key(plaintext)
  ├─ Store encrypted key in DB
  ├─ Save provider, model, temperature, base_url
  ├─ Decrypt and return the key in response
  └─ Return updated SettingsResponse

     │
     │ (Optional) POST /api/settings/test
     │ { llm_provider, llm_api_key, llm_model, llm_base_url }
     ▼
[Backend]
  ├─ Send a test message "Respond with just the word OK"
  ├─ If success: "✓ {Provider} connection successful!"
  └─ If fail: specific error message
```

### 3. Source / Document Management

```
┌─────────────────────────┐
│ Sources Panel (sidebar) │
└────┬────────────────────┘
     │
     ├─ Add URL: POST /api/sources/url
     │  { url: "https://...", session_id }
     │
     │  [Backend]
     │  ├─ Validate URL
     │  ├─ Scrape webpage (WebBaseLoader / BeautifulSoup)
     │  ├─ Split into 1000-char chunks (200 overlap)
     │  ├─ Generate embeddings (sentence-transformers/all-MiniLM-L6-v2)
     │  ├─ Store in ChromaDB (persistent, collection named url_<hash>)
     │  ├─ Save Document + Chunks in PostgreSQL
     │  ├─ Create LangChain retriever tool → "URL_Source_{N}"
     │  ├─ Register in session_store
     │  └─ Return { success, title, message }
     │
     └─ Upload PDF: POST /api/sources/pdf
        FormData: { file: <binary>, session_id }

        [Backend]
        ├─ Save to temp file
        ├─ Parse with PyPDFLoader
        ├─ Split into 1000-char chunks (200 overlap)
        ├─ Generate embeddings
        ├─ Store in ChromaDB (persistent, collection named pdf_<name>_<hash>)
        ├─ Save Document + Chunks in PostgreSQL
        ├─ Create LangChain retriever tool → "PDF_Source_{N}"
        ├─ Register in session_store
        └─ Return { success, filename, message }

     │
     └─ List sources: GET /api/sources/list?session_id=...
        └─ Return list of URL/PDF sources with metadata

     └─ Delete source: DELETE /api/sources/url?url=...&session_id=...
                          DELETE /api/sources/pdf?filename=...&session_id=...
        └─ Remove from session_store
```

### 4. Chat with RAG Agent (Full Detailed Flow)

```
┌──────────────────────────────────────┐
│ User types message in Chat Page      │
│ "What is NLP?"                       │
│ (with 2 URLs + 2 PDFs already added) │
└──────────────┬───────────────────────┘
               │
               ▼
[Frontend: ChatPage.jsx]
  ├─ Generate or load session_id (UUID)
  ├─ Build payload:
  │  { message, session_id, history, model_name,
  │    provider, api_key, temperature, memory_turns }
  └─ POST /api/chat
               │
               ▼
[Backend: chat.py]
  ├─ If user is authenticated AND no explicit api_key:
  │  ├─ Load stored provider/model/key from DB
  │  └─ Decrypt API key
  └─ Call run_agent(req)
               │
               ▼
[Backend: agent_service.py → run_agent()]
  │
  ├─ 1. BUILD CONTEXT
  │  ├─ build_history_text(history, max_turns=6)
  │  │  └─ Formats last 6 messages as "Human: ...\nAssistant: ..."
  │  ├─ get_source_lines(session_id)
  │  │  └─ Lists custom sources: "• URL_Source_1 → Webpage: '...' (url)"
  │  │                           "• PDF_Source_1 → PDF: 'filename.pdf'"
  │  ├─ get_all_tools(session_id)
  │  │  └─ Returns LangChain tool objects for each source
  │  └─ Combine with base tools: DuckDuckGo + Arxiv + Wikipedia
  │
  ├─ 2. BUILD LLM
  │  └─ _build_chat_model(provider, api_key, model, temp, base_url)
  │     ├─ Groq → ChatGroq (LangChain SDK)
  │     ├─ OpenAI → OpenAIProvider (direct HTTP via httpx)
  │     ├─ Anthropic → AnthropicProvider
  │     └─ Everything else → GenericOpenAIProvider (with tenacity retry)
  │
  ├─ 3. SMART TOOL CHECK
  │  └─ _needs_tools(message, history, has_custom_sources)
  │     ├─ Greetings ("hi", "hello") → SKIP agent, direct query only
  │     ├─ Identity questions ("what is my name") → SKIP agent
  │     ├─ Has custom sources (PDFs/URLs) → USE agent with tools
  │     └─ Everything else → USE agent with tools
  │
  ├─ 4. BUILD AGENT PROMPT (if tools needed)
  │  ├─ build_agent_prefix(history, source_lines)
  │  │  ├─ "You are InsightAgent, a helpful research assistant..."
  │  │  ├─ "CONVERSATION HISTORY: ..."
  │  │  ├─ "Custom knowledge sources loaded: ..."
  │  │  ├─ "Call the matching tool FIRST for questions about these sources"
  │  │  └─ Lists all available tools
  │  ├─ augment_prompt(message, history)
  │  │  └─ "[CONVERSATION HISTORY]\n...\n[CURRENT QUESTION]\n..."
  │  └─ Initialize LangChain agent (ZERO_SHOT_REACT_DESCRIPTION)
  │     ├─ max_iterations=4
  │     ├─ early_stopping_method="generate"
  │     └─ handle_parsing_errors=True
  │
  ├─ 5. RUN AGENT LOOP
  │  └─ agent.ainvoke({"input": augmented_message})
  │
  │     ┌────────────────────────────────────────────────┐
  │     │  ZERO_SHOT_REACT LOOP                          │
  │     │                                                │
  │     │  Iteration 1:                                  │
  │     │   Thought: "I need to check the custom sources"│
  │     │   Action: URL_Source_1                         │
  │     │   Action Input: "What is NLP"                  │
  │     │   Observation: "NLP is a subfield of AI..."    │
  │     │                                                │
  │     │  Iteration 2:                                  │
  │     │   Thought: "Let me also check the PDF"         │
  │     │   Action: PDF_Source_1                         │
  │     │   Action Input: "core concepts of NLP"         │
  │     │   Observation: "Core concepts include..."      │
  │     │                                                │
  │     │  Iteration 3:                                  │
  │     │   Thought: "I have enough info. Answering."    │
  │     │   Final Answer: "NLP is..."                    │
  │     └────────────────────────────────────────────────┘
  │
  ├─ 6. HANDLE ERRORS (if agent fails)
  │  ├─ Log the actual error type + message
  │  ├─ Try fallback: direct query without tools
  │  │  └─ _direct_query(llm, message, history)
  │  └─ If fallback also fails:
  │     ├─ OutputParserException → "The model had trouble formatting..."
  │     ├─ RateLimitError / 429 → "Rate limit exceeded..."
  │     ├─ Timeout → "The model took too long..."
  │     └─ Other → "Something went wrong: {ErrorType}..."
  │
  ├─ 7. BUILD RESPONSE
  │  ├─ answer = result.get("output", "")
  │  ├─ steps = result.get("intermediate_steps", [])
  │  ├─ For each step → ToolStep { step, tool, tool_input, observation }
  │  └─ Return ChatResponse { answer, tool_steps, tools_used,
  │                            answered_from_history }
  │
  └─ Send response to frontend
               │
               ▼
[Frontend: ChatPage.jsx]
  ├─ Display assistant answer
  ├─ Show tool calls with icons:
  │  📖 Wikipedia | 🌐 URL_Source_1 | 📕 PDF_Source_1
  │  🔍 DuckDuckGo_Search | 🔧 _Exception
  └─ Append to conversation history
```

### 5. Recommender Feature

```
┌──────────────────────┐
│ /recommend page      │
└────┬─────────────────┘
     │ POST /api/recommend
     │ { query: "I need an LLM for code generation" }
     ▼
[Backend]
  ├─ Build prompt asking LLM to recommend itself
  ├─ Send to user's configured provider
  └─ Return { recommendations, top_pick, reasoning }
```

---

## Tool Selection Priority (How the LLM Chooses)

The LLM does NOT follow a hardcoded priority. It decides based on the prompt:

| Prompt Section | What it tells the LLM |
|----------------|----------------------|
| "Custom knowledge sources loaded: ... Call the matching tool FIRST" | Prioritize user's PDFs/URLs |
| "CONVERSATION HISTORY: ... If answerable from history, do so WITHOUT calling tools" | Use memory first |
| Tool descriptions | Each tool has a name + description |
| "You have access to the following tools:" | Lists DuckDuckGo, Arxiv, Wikipedia as fallbacks |

**Typical decision flow for "what is NLP" with 2 URLs + 2 PDFs:**

1. 🤔 "User has custom NLP sources → check those first"
2. → Calls `URL_Source_1` → gets IBM article text
3. → Calls `PDF_Source_1` → gets PDF content  
4. → Calls `Wikipedia` (supplemental) → gets general definition
5. ✅ Synthesizes final answer from all sources

---

## File Tree (Actual Project Structure)

```
multitool-ai-chatbot/
├── docker-compose.yml
├── README.md
├── README_FULL_GUIDE.md          ← This file
├── TASK_PROGRESS.md
│
├── backend/
│   ├── .env                      # Secrets (DB URL, JWT key, etc.)
│   ├── .env.example
│   ├── .gitignore
│   ├── .python-version           # Python 3.11
│   ├── Dockerfile
│   ├── main.py                   # FastAPI app entry point
│   ├── pyproject.toml
│   ├── requirements.txt          # All Python dependencies
│   ├── uv.lock
│   ├── logs/                     # Application logs
│   ├── vector_store/             # ChromaDB persistent storage
│   │
│   └── app/
│       ├── __init__.py
│       │
│       ├── api/                  # HTTP endpoints
│       │   ├── auth.py           # /api/auth/* (signup, login, logout, refresh, me)
│       │   ├── chat.py           # /api/chat (RAG agent)
│       │   ├── settings.py       # /api/settings (GET, PUT, POST /test)
│       │   ├── sources.py        # /api/sources/* (URL, PDF, list, delete)
│       │   └── recommend.py      # /api/recommend
│       │
│       ├── core/                 # Models, DB, schemas
│       │   ├── models_db.py      # SQLAlchemy ORM (User, Document, Chunk, RefreshToken)
│       │   ├── models.py         # Pydantic request models (ChatRequest, etc.)
│       │   ├── schemas.py        # Pydantic response schemas (SettingsResponse, etc.)
│       │   ├── database.py       # PostgreSQL async engine + session
│       │   └── memory.py         # Conversation history formatters
│       │
│       ├── services/             # Business logic
│       │   ├── auth_service.py        # JWT, password hashing, refresh tokens
│       │   ├── agent_service.py       # LangChain agent orchestration
│       │   ├── providers.py           # LLM abstractions (9+ providers) + retry
│       │   ├── session_store.py       # In-memory per-session tool registry
│       │   ├── pdf_service.py         # PDF → chunks → Chroma → tool
│       │   ├── url_service.py         # URL → scrape → chunks → Chroma → tool
│       │   ├── vector_store.py        # ChromaDB integration
│       │   ├── redis_service.py       # Upstash/local Redis abstraction
│       │   └── recommender_service.py # LLM recommendation logic
│       │
│       ├── middleware/            # Request/response middleware
│       │   ├── auth.py           # JWT extraction & validation
│       │   └── ratelimit.py      # Rate limiting (60 req/min per user)
│       │
│       └── utils/
│           └── logger.py         # Structured logging
│
└── frontend/
    ├── .env                      # VITE_API_URL (empty = use proxy)
    ├── .env.example
    ├── Dockerfile
    ├── index.html
    ├── nginx.conf                # Production nginx config
    ├── package.json
    ├── postcss.config.js
    ├── tailwind.config.js
    ├── vite.config.js            # Dev proxy: /api → localhost:8000
    │
    └── src/
        ├── main.jsx              # React entry point
        ├── App.jsx               # Router + Layout
        │
        ├── pages/                # Full-page components
        │   ├── LoginPage.jsx     # Login form
        │   ├── SignupPage.jsx    # Registration form
        │   ├── ChatPage.jsx      # Main chat interface
        │   ├── SettingsPage.jsx  # LLM config (provider, key, model)
        │   ├── RecommendPage.jsx # LLM recommendation tool
        │   └── ApiKeyGate.jsx    # Guard page if no API key set
        │
        ├── components/
        │   ├── chat/
        │   │   ├── ModelSelector.jsx  # Provider/model dropdown
        │   │   └── SourcesPanel.jsx   # URL/PDF source manager
        │   └── layout/
        │       └── Layout.jsx         # Sidebar + main content
        │
        ├── hooks/
        │   └── useAuth.jsx       # Auth context (user, login, logout, refresh)
        │
        └── services/
            └── api.js            # Axios client + auto-refresh interceptor
```

---

## Supported LLM Providers

| Provider Name | Base URL (auto-detected) | Requires Base URL | Notes |
|--------------|--------------------------|-------------------|-------|
| `groq` | `https://api.groq.com/openai/v1` | No | Fast inference, free tier available |
| `openai` | `https://api.openai.com/v1` | No | GPT-4, GPT-3.5 |
| `anthropic` | `https://api.anthropic.com/v1` | Yes (uses Anthropic format) | Claude models |
| `claude` | `https://api.anthropic.com/v1` | Yes (uses Anthropic format) | Alias for Anthropic |
| `deepseek` | `https://api.deepseek.com/v1` | No | Very cheap, good quality |
| `mistral` | `https://api.mistral.ai/v1` | No | Mistral models |
| `together` | `https://api.together.xyz/v1` | No | Many open models |
| `openrouter` | `https://openrouter.ai/api/v1` | No | Access to 200+ models |
| `perplexity` | `https://api.perplexity.ai` | No | Perplexity models |
| `ollama` | (user provides) | Yes | Local models, e.g. `http://localhost:11434/v1` |
| *any custom* | (user provides) | Yes | Any OpenAI-compatible API |

---

## Key Features Implemented

### Recent Fixes & Improvements

| Feature | File(s) | Description |
|---------|---------|-------------|
| **API Key Eye Toggle** | `SettingsPage.jsx`, `schemas.py`, `settings.py` | Eye button to show/hide API key; key fetched from DB on page load |
| **Tenacity Retry** | `providers.py`, `requirements.txt` | Auto-retry 429 errors with 2s→4s→8s→16s backoff |
| **Smart Tool Detection** | `agent_service.py` | Skip agent for greetings/simple questions, saves rate limits |
| **F-String Safety** | `memory.py`, `agent_service.py` | Replaced f-strings with concatenation to prevent `} crash` |
| **Better Error Messages** | `agent_service.py` | Distinguishes parse errors, rate limits, timeouts |
| **Reduced Iterations** | `agent_service.py` | `max_iterations` 6→4 to reduce rate limit usage |
| **Event Loop Fix** | `agent_service.py` | Threaded fallback for sync _call inside async context |
| **OpenRouter Response Fix** | `providers.py` | Handle missing `choices` key in response |

### Security Features

- **API keys encrypted at rest** using Fernet (symmetric encryption)
- **JWT access tokens** (15 min expiry) with refresh token rotation
- **Refresh tokens** stored hashed in DB + Redis for fast lookup
- **Rate limiting**: 60 requests/minute per user via Redis/Upstash
- **Password hashing** with bcrypt
- **CORS** configured for frontend origin only

---

## Local Development Setup

### Prerequisites
- Python 3.11+
- Node.js 20+
- PostgreSQL (or Neon.tech account)
- Redis (or Upstash account)

### Backend Setup

```bash
cd backend

# Create virtual environment
python -m venv .venv
.venv\Scripts\activate        # Windows
source .venv/bin/activate     # macOS/Linux

# Install dependencies
pip install -r requirements.txt

# Configure .env (copy from .env.example)
# Required: DATABASE_URL, JWT_SECRET_KEY, ENCRYPTION_KEY
# Optional: UPSTASH_REDIS_REST_URL, UPSTASH_REDIS_REST_TOKEN

# Run database migrations (auto-create tables on startup)
# Start the server
uvicorn main:app --reload --port 8000
# or: uv run uvicorn main:app --reload --port 8000
```

### Frontend Setup

```bash
cd frontend
npm install
npm run dev
# Opens at http://localhost:5173
# Proxies /api/* to http://localhost:8000
```

### Environment Variables (backend/.env)

```bash
# Database (PostgreSQL with pgvector)
DATABASE_URL=postgresql://user:pass@host:5432/db?sslmode=require

# Redis (for refresh tokens and rate limiting)
REDIS_URL=redis://localhost:6379/0
UPSTASH_REDIS_REST_URL="https://your-upstash-url.upstash.io"
UPSTASH_REDIS_REST_TOKEN="your-upstash-token"

# JWT Authentication
JWT_SECRET_KEY=your-random-secret-at-least-32-chars
JWT_ACCESS_EXPIRE_MIN=15
JWT_REFRESH_EXPIRE_DAYS=7

# API Key Encryption (Fernet)
# Generate with: python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
ENCRYPTION_KEY=your-fernet-key

# CORS
ALLOWED_ORIGINS=http://localhost:5173,http://localhost:3000
```

---

## Docker Deployment

```bash
# Build and run with docker-compose
docker-compose up --build

# Services:
# - backend (FastAPI) on port 8000
# - frontend (Nginx) on port 80
# - PostgreSQL on port 5432
# - Redis on port 6379
```

### docker-compose.yml structure:
- **backend**: Python FastAPI with uvicorn
- **frontend**: Nginx serving built React app + proxying /api to backend
- **db**: PostgreSQL 15 with pgvector
- **redis**: Redis 7 for rate limiting + sessions

---

## API Endpoints Reference

| Method | Endpoint | Auth | Description |
|--------|----------|------|-------------|
| POST | `/api/auth/signup` | No | Create account |
| POST | `/api/auth/login` | No | Login, get tokens |
| POST | `/api/auth/logout` | Yes | Invalidate tokens |
| POST | `/api/auth/refresh/v2` | No | Refresh access token |
| GET | `/api/auth/me` | Yes | Get current user |
| GET | `/api/settings` | Yes | Get LLM config + decrypted key |
| PUT | `/api/settings` | Yes | Update LLM config |
| POST | `/api/settings/test` | Yes | Test LLM connection |
| POST | `/api/chat` | Optional | Send message to RAG agent |
| POST | `/api/sources/url` | Yes | Add URL source |
| POST | `/api/sources/pdf` | Yes | Upload PDF source |
| GET | `/api/sources/list` | Yes | List session sources |
| DELETE | `/api/sources/url` | Yes | Remove URL source |
| DELETE | `/api/sources/pdf` | Yes | Remove PDF source |
| POST | `/api/recommend` | Yes | Get LLM recommendations |
| GET | `/` | No | Health check |
| GET | `/health` | No | Health check |
| GET | `/docs` | No | Swagger UI |
| GET | `/redoc` | No | ReDoc UI |

---

## Testing Checklist

- [ ] Signup with email + password
- [ ] Login with credentials
- [ ] Auto-refresh token on expiry (wait 15 min or test manually)
- [ ] Logout clears all tokens
- [ ] Save settings (provider, API key, model)
- [ ] API key eye toggle (show/hide)
- [ ] API key persists on page reload (fetched from DB)
- [ ] Test connection button works
- [ ] Chat works with Groq (`llama-3.3-70b-versatile`)
- [ ] Chat works with OpenRouter
- [ ] Chat works with DeepSeek
- [ ] Chat works with custom provider (e.g., Ollama local)
- [ ] Add URL source → ask about it → agent uses it
- [ ] Upload PDF → ask about it → agent uses it
- [ ] Conversation memory works (follow-up questions)
- [ ] Smart tool detection: "hi" → no agent loop
- [ ] Smart tool detection: "what is my name" → no agent loop
- [ ] Smart tool detection: with PDFs → agent uses custom tools
- [ ] Rate limiting: 60+ requests/min → 429 error
- [ ] Error messages show correct type (parse vs rate limit vs timeout)
- [ ] Recommender page works
- [ ] CORS works from frontend origin
- [ ] Refresh token rotation (old token invalidated on refresh)

---

## Deployment Checklist

- [ ] Change `JWT_SECRET_KEY` to a long random value
- [ ] Set `ENCRYPTION_KEY` to a proper Fernet key (not "pratham_raj")
- [ ] Use managed PostgreSQL (Neon.tech, AWS RDS, etc.)
- [ ] Configure Upstash Redis (with password)
- [ ] Set `ALLOWED_ORIGINS` to production frontend URL
- [ ] Enable HTTPS (via Nginx reverse proxy or cloud LB)
- [ ] Use environment variables for all secrets
- [ ] Run database migrations on startup
- [ ] Set up logging to external service
- [ ] Configure proper rate limits for production
- [ ] Test with production load
- [ ] Set up monitoring/alerts