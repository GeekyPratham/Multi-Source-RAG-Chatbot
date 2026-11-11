"""main.py — FastAPI application entry point.

Run locally:
    uvicorn main:app --reload --port 8000
"""
import os
from dotenv import load_dotenv

# Load .env BEFORE any app imports that read environment variables
load_dotenv()
print("Loaded .env file with environment variables")

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.api import auth, chat, recommend, sources, settings
from app.core.database import init_db
from app.core import models_db  # ensure all SQLAlchemy models are registered with Base.metadata before create_all
from app.utils.logger import log
from contextlib import asynccontextmanager
#It is used to create an asynchronous context manager, especially useful for handling startup and shutdown logic in FastAPI.
from fastapi import Request
# Request represents the incoming HTTP request sent by a client to your FastAPI application.

print("Starting InsightAgent AI API server…")
@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifecycle: init DB and clean up connections on shutdown."""
    # ── Warn about missing critical env vars before anything else ────────────
    import os as _os
    if not _os.getenv("ENCRYPTION_KEY"):
        log.warning(
            "\n" + "=" * 60 +
            "\n[CRITICAL] ENCRYPTION_KEY is not set in .env!" +
            "\n  A new random key is generated every restart." +
            "\n  All stored API keys will be unreadable after each restart." +
            "\n  Fix: run  python -c \"from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())\"" +
            "\n  and set ENCRYPTION_KEY=<result> in backend/.env" +
            "\n" + "=" * 60
        )
    jwt_key = _os.getenv("JWT_SECRET_KEY", "")
    if not jwt_key or jwt_key == "change-this-in-production":
        log.warning(
            "\n" + "=" * 60 +
            "\n[CRITICAL] JWT_SECRET_KEY is not set or is the default value!" +
            "\n  All user sessions are invalidated on every restart." +
            "\n  Fix: set JWT_SECRET_KEY=<random 32+ char string> in backend/.env" +
            "\n" + "=" * 60
        )

    log.info("Starting InsightAgent AI API — initializing database…")
    await init_db()
    yield
    
    log.info("Shutting down — closing connections…")


app = FastAPI(
    title="InsightAgent AI API",
    description="RAG + Agentic AI assistant with pluggable LLM providers. "
                "Supports Groq, OpenAI, and Anthropic. Multi-tenant with JWT auth.",
    version="3.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)


# Log unhandled exceptions with full trace so login errors are visible in the server logs
@app.middleware("http")
async def log_exceptions_middleware(request: Request, call_next):
    try:
        return await call_next(request)
    except Exception as exc:  # pragma: no cover - runtime error logging
        log.exception("Unhandled exception during request %s %s", request.method, request.url)
        raise

# ── CORS ─────────────────────────────────────────────────────────────────────
raw_origins = os.getenv("ALLOWED_ORIGINS", "http://localhost:5173,http://localhost:3000")
origins = [o.strip() for o in raw_origins.split(",")]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Routers ───────────────────────────────────────────────────────────────────
app.include_router(auth.router)
app.include_router(recommend.router)
app.include_router(chat.router)
app.include_router(sources.router)
app.include_router(settings.router)


@app.get("/")
async def root():
    return {"status": "ok", "app": "InsightAgent AI", "version": "2.0.0"}


@app.get("/health")
async def health():
    return {"status": "healthy"}


if __name__ == "__main__":
    import uvicorn
    log.info("Starting InsightAgent API server")
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
