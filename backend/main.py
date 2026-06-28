"""main.py — FastAPI application entry point.

Run locally:
    uvicorn main:app --reload --port 8000
"""
import os
from dotenv import load_dotenv

# Load .env BEFORE any app imports that read environment variables
load_dotenv()

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.api import auth, chat, recommend, sources, settings
from app.core.database import init_db
from app.services.auth_service import close_redis
from app.utils.logger import log
from contextlib import asynccontextmanager
from fastapi import Request


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifecycle: init DB and clean up connections on shutdown."""
    log.info("Starting InsightAgent AI API — initializing database…")
    await init_db()
    yield
    log.info("Shutting down — closing connections…")
    await close_redis()


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
