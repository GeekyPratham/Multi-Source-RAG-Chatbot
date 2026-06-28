"""services/vector_store.py — persistent ChromaDB vector store."""
from __future__ import annotations
import hashlib
from pathlib import Path
from typing import Optional
from langchain_chroma import Chroma
from langchain_core.documents import Document
from app.services.embeddings import get_embeddings
from app.utils.logger import log

PERSIST_DIR = Path("vector_store")
PERSIST_DIR.mkdir(exist_ok=True)


def _coll_name(prefix: str, key: str) -> str:
    h = hashlib.sha256(key.encode()).hexdigest()[:10]
    return f"{prefix}_{h}"[:50]


def get_or_create_store(collection_name: str, docs: Optional[list[Document]] = None) -> Chroma:
    store = Chroma(
        collection_name=collection_name,
        embedding_function=get_embeddings(),
        persist_directory=str(PERSIST_DIR),
    )
    count = store._collection.count()
    if count == 0 and docs:
        log.info("Creating collection '%s' with %d chunks", collection_name, len(docs))
        store.add_documents(docs)
    elif count > 0:
        log.info("Reusing collection '%s' (%d chunks)", collection_name, count)
    return store


def url_collection(url: str) -> str:
    return _coll_name("url", url)


def pdf_collection(filename: str, content_hash: str) -> str:
    return _coll_name("pdf", f"{filename}_{content_hash}")
