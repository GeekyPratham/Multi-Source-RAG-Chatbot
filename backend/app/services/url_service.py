"""services/url_service.py — URL loading + chunking for the user-isolated indexer.

Loads a webpage and returns its chunks. Persistence and retrieval are handled
by services/user_store.py, which isolates every (user_id, document_hash) pair.
"""
from __future__ import annotations

import validators  # Format validation
from langchain_community.document_loaders import WebBaseLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from app.utils.logger import log

_SPLITTER = RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=200)


def load_url_chunks(url: str):
    """Load a URL and return ``(title, preview, chunks)``.

    Returns ``(None, None, None)`` on invalid URL, load failure, or empty content.
    """
    if not validators.url(url):
        return None, None, None

    try:
        docs = WebBaseLoader(url).load()
    except Exception as e:
        log.error("URL load failed '%s': %s", url, e)
        return None, None, None

    if not docs:
        return None, None, None

    title = docs[0].metadata.get("title", url).strip()
    preview = docs[0].page_content[:300].replace("\n", " ").strip()
    chunks = _SPLITTER.split_documents(docs)
    return title, preview, chunks