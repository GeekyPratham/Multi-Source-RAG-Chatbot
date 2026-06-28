# InsightAgent AI — Complete Development Guide for Beginners

## Project Overview

**InsightAgent AI** is a full-stack RAG (Retrieval-Augmented Generation) chatbot with:
- **Multi-provider LLM support** (Groq, OpenAI, Anthropic)
- **User authentication** with JWT tokens
- **Document management** (PDFs, URLs)
- **AI-powered research assistant** with web search, academic papers, Wikipedia
- **Real-time session-based chat** with memory

This guide walks you through the architecture, setup, and how to extend the system.

---

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────┐
│                     FRONTEND (React)                         │
│  ┌────────────┬───────────────┬──────────────┬──────────────┐
│  │ Login/Auth │ Settings      │ Chat Page    │ Recommender  │
│  └──────┬─────┴───────────────┴──────────────┴──────────────┘
│         │ HTTP/CORS                                          │
└─────────┼──────────────────────────────────────────────────┘
          │
┌─────────▼──────────────────────────────────────────────────┐
│              BACKEND (FastAPI + Python)                     │
│                                                              │
│  ┌──────────────────────────────────────────────────────┐  │
│  │  API Routes (FastAPI)                                │  │
│  │  ├─ /api/auth        (signup, login, refresh, logout)  │  │
│  │  ├─ /api/settings    (user LLM config)                 │  │
│  │  ├─ /api/chat        (RAG agent)                       │  │
│  │  ├─ /api/sources     (add URL/PDF, manage docs)        │  │
│  │  └─ /api/recommend   (LLM recommendation)              │  │
│  └──────┬───────────────────────────────────────────────┘  │
│         │                                                    │
│  ┌──────▼──────────────────────────────────────────────┐   │
│  │  Services Layer (Business Logic)                    │   │
│  │  ├─ auth_service.py      (JWT, passwords)          │   │
│  │  ├─ agent_service.py     (LangChain + tools)       │   │
│  │  ├─ providers.py         (LLM abstractions)        │   │
│  │  ├─ embeddings.py        (vector embeddings)       │   │
│  │  ├─ pdf_service.py       (PDF parsing)             │   │
│  │  ├─ url_service.py       (web scraping)            │   │
│  │  ├─ session_store.py     (memory + tools)          │   │
│  │  └─ recommender_service.py (LLM recommendations)   │   │
│  └──────┬──────────────────────────────────────────────┘   │
│         │                                                    │
│  ┌──────▼──────────────────────────────────────────────┐   │
│  │  Core Layer (Models & DB)                           │   │
│  │  ├─ models_db.py    (SQLAlchemy ORM tables)        │   │
│  │  ├─ schemas.py      (Pydantic request/response)    │   │
│  │  ├─ database.py     (PostgreSQL async setup)       │   │
│  │  └─ memory.py       (conversation history)         │   │
│  └──────┬──────────────────────────────────────────────┘   │
│         │                                                    │
│  ┌──────▼──────────────────────────────────────────────┐   │
│  │  External Integrations                              │   │
│  │  ├─ LangChain (agent, tools, memory)               │   │
│  │  ├─ Groq/OpenAI/Anthropic APIs                     │   │
│  │  ├─ Chroma (vector store)                          │   │
│  │  ├─ DuckDuckGo, Arxiv, Wikipedia                   │   │
│  │  └─ Redis (session state, refresh tokens)          │   │
│  └──────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────┘
          │
┌─────────▼──────────────────────────────────────────────────┐
│              DATABASES                                      │
│  ├─ PostgreSQL (users, documents, chunks, tokens)          │
│  ├─ Chroma    (vector embeddings for documents)            │
│  └─ Redis     (session memory, refresh tokens)             │
└──────────────────────────────────────────────────────────────┘
```

---

## Database Schema (PostgreSQL)

```sql
-- Users table
users (
  id: UUID (PK),
  email: VARCHAR (unique),
  password_hash: VARCHAR,
  display_name: VARCHAR,
  llm_provider: ENUM (groq|openai|anthropic) -- nullable
  llm_api_key_encrypted: TEXT,
  llm_model: VARCHAR,                        -- nullable
  temperature: FLOAT (default 0.7),
  created_at: TIMESTAMP,
  updated_at: TIMESTAMP
)

-- Documents (uploaded PDFs / added URLs)
documents (
  id: UUID (PK),
  user_id: UUID (FK),
  title: VARCHAR,
  source_type: VARCHAR (url|pdf),
  source_uri: TEXT,
  source_hash: VARCHAR (SHA-256),
  chunk_count: INT,
  created_at: TIMESTAMP
)

-- Chunks (document pieces for RAG)
chunks (
  id: UUID (PK),
  doc_id: UUID (FK),
  chunk_index: INT,
  content_hash: VARCHAR,
  text: TEXT,
  metadata_json: JSONB
)

-- Refresh tokens (JWT rotation)
refresh_tokens (
  id: UUID (PK),
  user_id: UUID (FK),
  token_hash: VARCHAR (unique),
  expires_at: TIMESTAMP,
  created_at: TIMESTAMP
)
```

---

## User Flow (End-to-End)

### 1. **Authentication Flow**

```
┌─────────┐
│ Signup  │
└────┬────┘
     │ POST /api/auth/signup
     │ { email, password, display_name }
     ▼
[Backend validates + creates user with NULL llm_provider/model]
     │
     ├─ Hash password (bcrypt)
     ├─ Create User in DB
     ├─ Generate JWT access_token (15 min)
     ├─ Generate refresh_token (7 days) → store in Redis + DB
     └─ Return { access_token, refresh_token, user }
     │
     ▼
[Frontend stores tokens in localStorage]
     │
     ├─ localStorage['insightagent_access_token']
     ├─ localStorage['insightagent_refresh_token']
     └─ localStorage['insightagent_user_id']
     │
     ▼
┌─────────┐
│ Login   │
└────┬────┘
     │ POST /api/auth/login
     │ { email, password }
     ▼
[Backend verifies password + issues tokens]
```

### 2. **Settings Configuration (Required Before Chat)**

```
┌──────────────────────┐
│ Settings Page        │
└────┬─────────────────┘
     │
     │ User enters:
     │ • LLM Provider (groq, openai, anthropic)
     │ • API Key (encrypted before storage)
     │ • Model Name (e.g., "llama-3.3-70b-versatile")
     │ • Temperature (0.0 - 2.0)
     │
     ▼ PUT /api/settings
     │ { llm_provider, llm_api_key, llm_model, temperature }
     │
[Backend encrypts API key + updates user]
     │
     ├─ encrypt_api_key(api_key) → store in DB
     ├─ Update llm_provider, llm_model, temperature
     └─ Return { llm_provider, llm_model, has_api_key, ... }
     │
     ▼
┌──────────────────────┐
│ Credentials Saved!   │
│ Ready for Chat       │
└──────────────────────┘
```

### 3. **Document Management (Optional)**

```
┌─────────────────────────┐
│ Add URL / Upload PDF    │
└────┬────────────────────┘
     │
     ├─ URL: POST /api/sources/url { url, session_id }
     │  ├─ Scrape web page (BeautifulSoup)
     │  ├─ Extract text
     │  ├─ Split into chunks (overlapping)
     │  ├─ Generate embeddings (Sentence Transformers)
     │  ├─ Store in Chroma (vector DB)
     │  ├─ Save chunks in PostgreSQL
     │  └─ Return { success, title, message }
     │
     └─ PDF: POST /api/sources/pdf { file, session_id }
        ├─ Parse PDF (PyPDF)
        ├─ Extract text
        ├─ Split into chunks
        ├─ Generate embeddings
        ├─ Store in Chroma + PostgreSQL
        └─ Return { success, filename, message }
     │
     ▼
[Documents stored in session context for RAG]
```

### 4. **Chat with RAG Agent**

```
┌──────────────────────────────────┐
│ User Types Message in Chat       │
└────┬─────────────────────────────┘
     │ POST /api/chat
     │ {
     │   message: "What is...?",
     │   model_name: "llama-3.3-70b-versatile",
     │   session_id: "default",
     │   history: [...],
     │   memory_turns: 6,
     │   temperature: 0.7
     │ }
     │
     ▼ [Backend: Agent Service]
     │
     ├─ Retrieve user's stored provider/API key/model
     ├─ Build LLM client (ChatGroq, OpenAI SDK, etc.)
     ├─ Initialize LangChain Agent with tools:
     │  ├─ DuckDuckGo (web search)
     │  ├─ Arxiv (academic papers)
     │  ├─ Wikipedia
     │  ├─ Custom tools (from user's documents)
     │  └─ Memory (conversation history)
     │
     ├─ Build prompt:
     │  ├─ System instructions
     │  ├─ Conversation history (last 6 turns)
     │  ├─ Source context (from uploaded docs/URLs)
     │  └─ User's current message
     │
     ├─ Run agent (ZERO_SHOT_REACT loop):
     │  │ Thought: I need to search for...
     │  │ Action: DuckDuckGo_Search
     │  │ Observation: [search results]
     │  │ ...repeat until Final Answer
     │
     ├─ Extract intermediate steps (tools used)
     └─ Return {
         answer: "The answer is...",
         tool_steps: [...],
         tools_used: ["DuckDuckGo", "Wikipedia"],
         answered_from_history: false
       }
     │
     ▼
[Frontend displays answer + sources]
```

---

## Step-by-Step Development Guide

### **Phase 1: Foundation (Week 1-2)**

#### 1.1 Set Up Development Environment

```bash
# Backend setup
cd backend
python -m venv .venv
.venv\Scripts\activate  # Windows
source .venv/bin/activate  # macOS/Linux

# Install dependencies
pip install -r requirements.txt

# Frontend setup
cd ../frontend
npm install
```

#### 1.2 Database & Environment

Create `.env` file in `backend/`:

```bash
DATABASE_URL=postgresql+asyncpg://user:password@localhost:5432/insightagent
REDIS_URL=redis://localhost:6379/0
JWT_SECRET_KEY=your-secret-key-change-in-production
ENCRYPTION_KEY=your-fernet-key-or-will-be-auto-generated
```

Start PostgreSQL and Redis:

```bash
# PostgreSQL (Docker)
docker run -d -e POSTGRES_USER=insightagent -e POSTGRES_PASSWORD=insightagent -e POSTGRES_DB=insightagent -p 5432:5432 postgres:15

# Redis (Docker)
docker run -d -p 6379:6379 redis:7
```

#### 1.3 **FIRST: Build Authentication System**

**Why first?** Because every other endpoint needs user identity.

**Files to create/edit:**

1. **`app/core/models_db.py`** — User model
   ```python
   class User(Base):
       id: UUID
       email: str (unique)
       password_hash: str
       llm_provider: str (nullable)
       llm_api_key_encrypted: str (nullable)
       llm_model: str (nullable)
       temperature: float
   ```

2. **`app/services/auth_service.py`** — JWT + password
   - `hash_password()` / `verify_password()` (bcrypt)
   - `create_access_token()` (JWT)
   - `issue_refresh_token()` (Redis + DB)
   - `decrypt_api_key()` (Fernet encryption)

3. **`app/api/auth.py`** — Endpoints
   - `POST /api/auth/signup` — create user
   - `POST /api/auth/login` — verify password, return tokens
   - `POST /api/auth/logout` — invalidate tokens
   - `GET /api/auth/me` — return current user

4. **`app/middleware/auth.py`** — JWT validation
   - `get_current_user()` — extract + validate Bearer token
   - `get_optional_user()` — optional auth

5. **Frontend: `src/pages/LoginPage.jsx` + `SignupPage.jsx`**
   - Form to enter email/password
   - POST to `/api/auth/signup` or `/api/auth/login`
   - Store tokens in localStorage

6. **Frontend: `src/hooks/useAuth.jsx`**
   - Context to manage user state globally
   - Auto-refresh tokens on expiry

**Test:**
```bash
# Backend: Start server
cd backend && uv run uvicorn main:app --reload

# Frontend: Dev server
cd frontend && npm run dev

# Test in browser: http://localhost:5173
# 1. Signup
# 2. Login
# 3. Verify localStorage has tokens
```

---

### **Phase 2: User Settings & LLM Configuration (Week 2-3)**

#### 2.1 **Settings Endpoint**

**Files:**

1. **`app/api/settings.py`** — Endpoints
   ```
   GET  /api/settings           → return current user's LLM config
   PUT  /api/settings           → update provider/model/api_key
   POST /api/settings/test      → test LLM connection
   ```

2. **`app/services/providers.py`** — LLM abstractions
   - `GroqProvider` class
   - `OpenAIProvider` class
   - `AnthropicProvider` class
   - `get_provider(name)` → returns correct class

3. **Frontend: `src/pages/SettingsPage.jsx`**
   - Dropdown: select provider (Groq, OpenAI, Anthropic)
   - Input: paste API key (masked)
   - Dropdown: select model (based on provider)
   - Slider: temperature (0.0 - 2.0)
   - Button: "Test Connection"

**Test:**
```bash
# Go to /settings
# 1. Select provider = "groq"
# 2. Enter Groq API key
# 3. Select model = "llama-3.3-70b-versatile"
# 4. Click "Test Connection"
# 5. Verify: "Connection successful!"
```

---

### **Phase 3: Core Chat System (Week 3-4)**

#### 3.1 **Build the RAG Agent**

**Files:**

1. **`app/core/memory.py`** — Conversation history
   - `build_history_text()` — format past messages
   - `build_agent_prefix()` — system prompt
   - `augment_prompt()` — add context to user message

2. **`app/services/agent_service.py`** — LangChain agent
   ```python
   async def run_agent(req: ChatRequest) -> ChatResponse:
       # 1. Get user's stored provider/model/api_key
       # 2. Build LLM client (ChatGroq, OpenAI, etc.)
       # 3. Create LangChain agent with tools:
       #    - DuckDuckGo_Search
       #    - ArxivQueryRun
       #    - WikipediaQueryRun
       # 4. Run agent loop (ZERO_SHOT_REACT)
       # 5. Return answer + tool_steps
   ```

3. **`app/api/chat.py`** — Chat endpoint
   ```
   POST /api/chat
   {
     message: str,
     session_id: str,
     history: list,
     temperature: float
   }
   → ChatResponse { answer, tool_steps, tools_used }
   ```

4. **Frontend: `src/pages/ChatPage.jsx`**
   - Message input box
   - Chat history display
   - Model selector (dropdown)
   - Loading indicator while agent runs

5. **Frontend: `src/components/chat/ChatMessage.jsx`**
   - Display user messages (right)
   - Display assistant messages (left)
   - Show tool usage (e.g., "Used DuckDuckGo, Wikipedia")

**Test:**
```bash
# 1. Make sure Settings are configured
# 2. Go to /chat
# 3. Type: "What is the capital of France?"
# 4. Verify: Agent searches Wikipedia, returns "Paris"
# 5. Check tools_used: ["Wikipedia"] or ["DuckDuckGo"]
```

---

### **Phase 4: Document Management (Week 4-5)**

#### 4.1 **Add URL Support**

**Files:**

1. **`app/services/url_service.py`** — Web scraping
   - `scrape_url(url)` → extract text
   - `split_chunks(text)` → break into manageable pieces

2. **`app/services/embeddings.py`** — Vector embeddings
   - `embed_text(text)` → create vector (Sentence Transformers)
   - Store embeddings in Chroma

3. **`app/api/sources.py`** — Document endpoints
   ```
   POST /api/sources/url      { url, session_id }
   DELETE /api/sources/url    { url, session_id }
   GET /api/sources/list      { session_id }
   ```

4. **Frontend: `src/components/SourcesPanel.jsx`**
   - Input: paste URL
   - Button: "Add Source"
   - List: show added sources
   - Button: delete source

**Test:**
```bash
# 1. Open /chat
# 2. Click "Add Source" → enter a URL (e.g., https://en.wikipedia.org/wiki/Python_(programming_language))
# 3. Wait for scraping + embedding
# 4. Ask: "What is Python?"
# 5. Verify: Agent cites the added URL
```

#### 4.2 **Add PDF Support**

**Files:**

1. **`app/services/pdf_service.py`** — PDF parsing
   - `parse_pdf(file)` → extract text
   - `split_chunks(text)` → vectorize

2. **Frontend: File upload to `/api/sources/pdf`**
   - Drag-drop or file picker
   - Send to backend
   - Show progress

**Test:**
```bash
# 1. Upload a PDF
# 2. Ask a question about its content
# 3. Verify: Agent retrieves relevant chunks
```

---

### **Phase 5: Session Management (Week 5)**

#### 5.1 **Session State**

**Files:**

1. **`app/services/session_store.py`** — User sessions
   - Store user's sources per session_id
   - Retrieve tools for RAG context

2. **Frontend: `src/hooks/useSession.js`**
   - Manage session_id (localStorage or generate UUID)

**Test:**
```bash
# 1. Create 2 sessions
# 2. Add different sources to each
# 3. Switch between sessions
# 4. Verify: each session has its own docs
```

---

### **Phase 6: Advanced Features (Week 6+)**

#### 6.1 **LLM Recommender**

**Files:**

1. **`app/api/recommend.py`**
   ```
   POST /api/recommend
   { query: str }
   → RecommendResponse { recommendations, top_pick, reasoning }
   ```

2. **Frontend: `src/pages/RecommendPage.jsx`**
   - Input: describe your task
   - Output: ranked LLM recommendations

#### 6.2 **Admin Dashboard**

- View all users
- Monitor API usage
- See conversation stats

---

## Key Concepts for Beginners

### **1. Authentication Flow**

```
JWT = JSON Web Token (like a signed ID card)
- Access Token: short-lived (15 min), used for API requests
- Refresh Token: long-lived (7 days), used to get new access tokens
- Redis: stores refresh tokens for quick lookup
- DB: stores refresh token hashes for audit trail
```

### **2. API Key Encryption**

```
User enters API key in Settings
↓
Backend encrypts it using Fernet (cryptography.fernet)
↓
Stored in DB as ciphertext
↓
At runtime, decrypt to use with LLM API
```

### **3. LangChain Agent Loop**

```
Observation:
I need to search for information about Python

Action:
Use DuckDuckGo_Search tool

Thought:
The search results are good, I have my answer

Final Answer:
"Python is..."
```

### **4. Vector Embeddings & RAG**

```
User uploads document
↓
Break into chunks (e.g., 500 characters each)
↓
Convert each chunk to a vector (e.g., 384-dim)
↓
Store in Chroma (vector database)
↓
At query time:
  - Convert query to vector
  - Find similar chunks (cosine similarity)
  - Include top chunks in LLM prompt
  - LLM answers based on retrieved context
```

---

## Folder Structure Explained

```
backend/
├── main.py                 # FastAPI app entry point
├── requirements.txt        # Python dependencies
├── .env                    # Secrets (DATABASE_URL, JWT_SECRET_KEY, etc.)
│
├── app/
│   ├── __init__.py
│   │
│   ├── api/                # HTTP endpoints
│   │   ├── auth.py        # Signup, login, logout
│   │   ├── chat.py        # Chat endpoint (RAG agent)
│   │   ├── settings.py    # User LLM configuration
│   │   ├── sources.py     # Add/list documents
│   │   └── recommend.py   # LLM recommendations
│   │
│   ├── core/              # Models & database
│   │   ├── models_db.py   # SQLAlchemy ORM (User, Document, Chunk, RefreshToken)
│   │   ├── models.py      # Pydantic request/response schemas
│   │   ├── schemas.py     # Auth, settings, chat schemas
│   │   ├── database.py    # PostgreSQL async setup
│   │   └── memory.py      # Conversation memory formatting
│   │
│   ├── services/          # Business logic
│   │   ├── auth_service.py          # JWT, password hashing
│   │   ├── agent_service.py         # LangChain agent
│   │   ├── providers.py             # LLM abstractions (Groq, OpenAI, Anthropic)
│   │   ├── embeddings.py            # Vector generation
│   │   ├── pdf_service.py           # PDF parsing
│   │   ├── url_service.py           # Web scraping
│   │   ├── session_store.py         # Session state
│   │   ├── vector_store.py          # Chroma integration
│   │   └── recommender_service.py   # LLM selection logic
│   │
│   ├── middleware/        # Request/response middleware
│   │   └── auth.py       # JWT extraction & validation
│   │
│   └── utils/            # Helpers
│       └── logger.py     # Structured logging
│
└── logs/                 # Application logs

frontend/
├── index.html            # Entry HTML
├── package.json          # Node.js dependencies
│
├── src/
│   ├── main.jsx         # React entry
│   ├── App.jsx          # Main app component
│   ├── index.css        # Global styles
│   │
│   ├── pages/           # Full-page components
│   │   ├── LoginPage.jsx
│   │   ├── SignupPage.jsx
│   │   ├── ChatPage.jsx
│   │   ├── SettingsPage.jsx
│   │   ├── RecommendPage.jsx
│   │   └── ApiKeyGate.jsx
│   │
│   ├── components/      # Reusable components
│   │   ├── chat/
│   │   │   ├── ChatInput.jsx       # Message input box
│   │   │   ├── ChatMessage.jsx     # Message display
│   │   │   ├── ModelSelector.jsx   # Model dropdown
│   │   │   └── SourcesPanel.jsx    # Manage documents
│   │   ├── layout/
│   │   │   └── Layout.jsx          # Navigation + layout
│   │   └── ui/                     # Shared UI components
│   │
│   ├── hooks/           # Custom React hooks
│   │   ├── useAuth.jsx  # Auth context & methods
│   │   ├── useSession.js # Session management
│   │   └── useApiKey.js # API key management
│   │
│   ├── services/        # API calls
│   │   └── api.js       # Axios client + endpoints
│   │
│   └── utils/           # Helpers
│       └── ...
```

---

## Common Tasks

### **Add a New LLM Provider (e.g., Cohere)**

1. **Edit `app/services/providers.py`:**
   ```python
   class CohereProvider(LLMProviderBase):
       async def ainvoke(self, messages: list[dict]) -> str:
           # Use cohere SDK
           ...
   
   PROVIDER_MAP['cohere'] = CohereProvider
   ```

2. **Edit `app/core/models_db.py`:**
   ```python
   class LLMProvider(str, Enum):
       GROQ = "groq"
       OPENAI = "openai"
       ANTHROPIC = "anthropic"
       COHERE = "cohere"  # ADD
   ```

3. **Edit `frontend/src/pages/SettingsPage.jsx`:**
   ```jsx
   const PROVIDERS = [
     { value: 'cohere', label: 'Cohere', models: [...] },
     ...
   ]
   ```

### **Add a New Tool to the Agent**

1. **In `app/services/agent_service.py`:**
   ```python
   def _base_tools():
       return [
           DuckDuckGoSearchRun(...),
           MyCustomTool(),  # ADD
           ...
       ]
   ```

2. **Define `MyCustomTool` (inherit from `langchain.tools.BaseTool`)**

### **Change Default Temperature**

- Edit `app/core/models_db.py`: `temperature: Mapped[float] = mapped_column(Float, default=0.7)`
- Frontend: Update default in `useAuth.jsx`

---

## Testing Checklist

- [ ] Signup works
- [ ] Login works
- [ ] Settings saved correctly
- [ ] API key encrypted/decrypted
- [ ] Chat works with Groq
- [ ] Chat works with OpenAI
- [ ] Chat works with Anthropic
- [ ] URL scraping works
- [ ] PDF parsing works
- [ ] Agent uses correct tools
- [ ] Session management works
- [ ] Tokens refresh on expiry
- [ ] Logout clears tokens

---

## Deployment Checklist

- [ ] Change `JWT_SECRET_KEY` to random value
- [ ] Set `ENCRYPTION_KEY` to proper Fernet key
- [ ] Use PostgreSQL in production (not SQLite)
- [ ] Configure Redis with password
- [ ] Set `ALLOWED_ORIGINS` for CORS
- [ ] Enable HTTPS
- [ ] Use environment variables (no hardcoded secrets)
- [ ] Set up logging to external service
- [ ] Configure rate limiting
- [ ] Test with production load

---

## Next Steps

1. **Fork/clone this repo**
2. **Set up `.env` with your database credentials**
3. **Start with Phase 1: Authentication**
4. **Test each phase locally before moving to the next**
5. **Deploy using Docker** (see `docker-compose.yml`)

---

## Resources

- **LangChain Docs:** https://python.langchain.com/docs/get_started/introduction
- **FastAPI Docs:** https://fastapi.tiangolo.com/
- **React Docs:** https://react.dev/
- **SQLAlchemy Async:** https://docs.sqlalchemy.org/en/20/orm/extensions/asyncio.html
- **JWT:** https://jwt.io/

---

## Questions?

Refer to the code comments in each file for detailed explanations. Each module is well-documented.

Happy coding! 🚀
