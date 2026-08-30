"""services/session_store.py
Per-user registry of loaded source retrieval tools.

Each user (keyed by their verified user id, derived from the JWT) owns a dict
of loaded source tools. Tools are only ever constructed from that user's
user-isolated vector collections.

In production you'd back this with Redis; for local use an in-process dict is
fine since FastAPI runs as a single process.
"""
from __future__ import annotations

from typing import Any

# user_id -> { "url_sources": {...}, "pdf_sources": {...} }
_sessions: dict[str, dict[str, Any]] = {}


def get_session(user_id: str) -> dict:
    if user_id not in _sessions:
        _sessions[user_id] = {"url_sources": {}, "pdf_sources": {}}
    return _sessions[user_id]


def clear_session(user_id: str) -> None:
    """Drop all in-memory tools for a user (used on logout)."""
    _sessions.pop(user_id, None)


def register_url_tool(user_id: str, url: str, tool, document_hash: str, title: str, tool_name: str) -> None:
    sess = get_session(user_id)
    sess["url_sources"][url] = {
        "tool": tool,
        "document_hash": document_hash,
        "title": title or url,
        "tool_name": tool_name,
    }


def register_pdf_tool(user_id: str, filename: str, tool, document_hash: str, tool_name: str) -> None:
    sess = get_session(user_id)
    sess["pdf_sources"][filename] = {
        "tool": tool,
        "document_hash": document_hash,
        "tool_name": tool_name,
    }


def has_user_session(user_id: str) -> bool:
    return user_id in _sessions


def pop_url(user_id: str, url: str) -> str | None:
    """Remove a URL source and return its document_hash (or None)."""
    if user_id not in _sessions:
        return None
    info = _sessions[user_id]["url_sources"].pop(url, None)
    return info["document_hash"] if info else None


def pop_pdf(user_id: str, filename: str) -> str | None:
    """Remove a PDF source and return its document_hash (or None)."""
    if user_id not in _sessions:
        return None
    info = _sessions[user_id]["pdf_sources"].pop(filename, None)
    return info["document_hash"] if info else None


def get_all_tools(user_id: str) -> list:
    if user_id not in _sessions:
        return []
    sess = _sessions[user_id]
    tools = []
    tools += [info["tool"] for info in sess["url_sources"].values()]
    tools += [info["tool"] for info in sess["pdf_sources"].values()]
    return tools


def get_source_lines(user_id: str) -> list[str]:
    if user_id not in _sessions:
        return []
    sess = _sessions[user_id]
    lines = []
    for url, info in sess["url_sources"].items():
        lines.append(f"  • {info['tool_name']} → Webpage: '{info['title']}' ({url})")
    for fname, info in sess["pdf_sources"].items():
        lines.append(f"  • {info['tool_name']} → PDF: '{fname}'")
    return lines