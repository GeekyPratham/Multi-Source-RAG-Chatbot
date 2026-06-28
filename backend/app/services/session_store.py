"""services/session_store.py
In-memory registry of per-session tools (URL/PDF retrievers).

Each user session gets its own dict of loaded source tools.
In production you'd back this with Redis; for local use an in-process
dict is fine since FastAPI runs as a single process.
"""
from __future__ import annotations
from typing import Any

# session_id -> { "url_sources": {...}, "pdf_sources": {...} }
_sessions: dict[str, dict[str, Any]] = {}


def get_session(session_id: str) -> dict:
    if session_id not in _sessions:
        _sessions[session_id] = {"url_sources": {}, "pdf_sources": {}}
    return _sessions[session_id]


def clear_session(session_id: str) -> None:
    _sessions.pop(session_id, None)


def get_all_tools(session_id: str) -> list:
    sess = get_session(session_id)
    tools = []
    tools += [info["tool"] for info in sess["url_sources"].values()]
    tools += [info["tool"] for info in sess["pdf_sources"].values()]
    return tools


def get_source_lines(session_id: str) -> list[str]:
    sess = get_session(session_id)
    lines = []
    for url, info in sess["url_sources"].items():
        lines.append(f"  • {info['tool_name']} → Webpage: '{info['title']}' ({url})")
    for fname, info in sess["pdf_sources"].items():
        lines.append(f"  • {info['tool_name']} → PDF: '{fname}'")
    return lines
