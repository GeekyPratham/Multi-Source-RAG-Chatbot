"""services/pdf_service.py — PDF loading + chunking for the user-isolated indexer.

Loads a PDF and returns its chunks. Persistence and retrieval are handled
by services/user_store.py, which isolates every (user_id, document_hash) pair.
"""
from __future__ import annotations

import os
import tempfile

from langchain_community.document_loaders import PyPDFLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from app.utils.logger import log

_SPLITTER = RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=200)


def load_pdf_chunks(file_bytes: bytes, filename: str):
    """Load a PDF and return ``(title, preview, chunks)``.

    Returns ``(None, None, None)`` if the PDF produced no content.
    """
    with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
        tmp.write(file_bytes)
        tmp_path = tmp.name
    try:
        docs = PyPDFLoader(tmp_path).load()
    except Exception as e:
        log.error("PDF load failed '%s': %s", filename, e)
        return None, None, None
    finally:
        try:
            os.unlink(tmp_path)
        except OSError:
            pass

    if not docs:
        return None, None, None

    title = filename  # no reliable metadata in base PDF loader
    preview = docs[0].page_content[:300].replace("\n", " ").strip()
    chunks = _SPLITTER.split_documents(docs)
    return title, preview, chunks