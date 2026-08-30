"""services/user_store.py — user-isolated, tenant-aware Chroma vector store.

Security model
--------------
* Every (user_id, document_hash) pair owns a dedicated Chroma collection whose
  name is derived from BOTH the user id and the document hash. Two different
  users can therefore never share, or retrieve, the same vectors.
* Logout purges every collection belonging to the user ("purge on logout").
  Removing a single URL/PDF deletes only that document's collection, leaving
  the user's other documents intact.
* Every vector's metadata carries
  {user_id, document_hash, chunk_index, source_type, source_uri, timestamp}
  for precise, auditable bookkeeping and partial deletion.
* Retrievers are built only from the user-scoped collection, so the search
  surface is physically confined to the current user's embeddings.
"""
from __future__ import annotations

import asyncio
import hashlib
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable, Optional

from langchain_chroma import Chroma
from langchain_core.documents import Document
from langchain_core.tools import create_retriever_tool
from sqlalchemy import delete, select

from app.core.database import async_session_factory
from app.core.models_db import AuditLog, Chunk as ChunkRow, Document as DocumentRow
from app.services.embeddings import get_embeddings
from app.utils.logger import log

PERSIST_DIR = Path("vector_store")
PERSIST_DIR.mkdir(exist_ok=True)

# ── Composite metadata contract ─────────────────────────────────────────────
META_USER_ID = "user_id"
META_DOC_HASH = "document_hash"
META_CHUNK_INDEX = "chunk_index"
META_SOURCE_TYPE = "source_type"
META_SOURCE_URI = "source_uri"
META_TIMESTAMP = "timestamp"

# Marker prefix for user-owned collections so purge can enumerate them safely.
_COLL_PREFIX = "u_"


class DuplicateDocumentError(Exception):
    """Raised when a user tries to (re)upload a document they already have."""

    def __init__(self, document_hash: str) -> None:
        super().__init__("Document already uploaded")
        self.document_hash = document_hash
# ── Per-user locks (serialize concurrent ingests/upserts per user) ──────────
_user_locks: dict[str, asyncio.Lock] = {}


def _get_lock(user_id: str) -> asyncio.Lock:
    lock = _user_locks.get(user_id)
    if lock is None:
        lock = asyncio.Lock()
        _user_locks[user_id] = lock
    return lock


# ── Content hashing (deterministic, full SHA-256) ───────────────────────────
def canonical_hash(content: str) -> str:
    """Deterministic full SHA-256 of normalized text content.

    Whitespace is collapsed so content that merely differs in formatting still
    dedups. The returned 64-hex digest is the authoritative document identity.
    """
    norm = " ".join(content.split())
    return hashlib.sha256(norm.encode("utf-8")).hexdigest()


def chunk_hash(chunk_text: str) -> str:
    """Full SHA-256 of a single chunk's raw text (for chunk-level auditing)."""
    return hashlib.sha256(chunk_text.encode("utf-8")).hexdigest()


# ── Collection naming / purge prefix ────────────────────────────────────────
def user_collection_prefix(user_id: str) -> str:
    """Prefix that all of a user's collections share, for logout purge."""
    u = hashlib.sha256(str(user_id).encode()).hexdigest()[:10]
    return f"{_COLL_PREFIX}{u}_"


def user_collection_name(user_id: str, document_hash: str) -> str:
    """Deterministic per-(user, document) collection name."""
    u = hashlib.sha256(str(user_id).encode()).hexdigest()[:10]
    d = str(document_hash)[:12]
    return f"{_COLL_PREFIX}{u}_{d}"[:50]


def _make_metadata(
    user_id,
    document_hash: str,
    chunk_index: int,
    source_type: str,
    source_uri: Optional[str],
) -> dict:
    return {
        META_USER_ID: str(user_id),
        META_DOC_HASH: document_hash,
        META_CHUNK_INDEX: chunk_index,
        META_SOURCE_TYPE: source_type,
        META_SOURCE_URI: source_uri or "",
        META_TIMESTAMP: datetime.now(timezone.utc).isoformat(),
    }
# ── Low-level Chroma helpers ────────────────────────────────────────────────
def _open_user_store(collection_name: str) -> Chroma:
    return Chroma(
        collection_name=collection_name,
        embedding_function=get_embeddings(),
        persist_directory=str(PERSIST_DIR),
    )


def write_chunks(
    collection_name: str,
    document_hash: str,
    user_id,
    source_type: str,
    source_uri: Optional[str],
    chunks: Iterable[Document],
) -> int:
    """Upsert chunk embeddings into a user document's isolated collection.

    Deterministic ids (``document_hash:chunk_index``) make re-indexing a no-op
    instead of a duplicate-feeding race. Returns the number of chunks written.
    """
    chunk_list = list(chunks)
    if not chunk_list:
        return 0
    ids = [f"{document_hash}:{i}" for i in range(len(chunk_list))]
    metadatas = [
        _make_metadata(user_id, document_hash, i, source_type, source_uri)
        for i in range(len(chunk_list))
    ]
    documents = [ch.page_content for ch in chunk_list]
    store = _open_user_store(collection_name)
    store._collection.upsert(ids=ids, metadatas=metadatas, documents=documents)
    return len(chunk_list)


def _list_collection_names() -> list[str]:
    """Return the names of all Chroma collections in the persisted directory."""
    from chromadb import PersistentClient

    client = PersistentClient(path=str(PERSIST_DIR))
    names: list[str] = []
    for item in client.list_collections():
        name = getattr(item, "name", item)
        if name:
            names.append(name)
    return names


def _drop_collections_with_prefix(prefix: str) -> int:
    """Best-effort deletion of all collections whose name starts with prefix."""
    from chromadb import PersistentClient

    removed = 0
    client = PersistentClient(path=str(PERSIST_DIR))
    for name in _list_collection_names():
        if name.startswith(prefix):
            try:
                client.delete_collection(name)
                removed += 1
            except Exception as e:  # pragma: no cover - defensive
                log.error("Failed to drop collection '%s': %s", name, e)
    return removed


def delete_user_collection(user_id: str, document_hash: str) -> bool:
    """Delete a single (user, document) collection. Returns True if deleted."""
    name = user_collection_name(user_id, document_hash)
    try:
        if name in set(_list_collection_names()):
            store = _open_user_store(name)
            store.delete_collection()
            return True
    except Exception as e:
        log.error("Failed to delete collection '%s': %s", name, e)
    return False
# ── Async orchestration: dedup + persistence + audit ────────────────────────
async def index_user_document(
    *,
    user_id,
    session,
    source_type: str,
    source_uri: Optional[str],
    title: str,
    chunks: list[Document],
) -> tuple[str, str, int]:
    """Persist a user's document into its isolated collection + DB rows.

    Returns ``(document_hash, collection_name, chunk_count)``.

    Raises :class:`DuplicateDocumentError` if the user already uploaded a
    document with the same content hash, so data is never duplicated.
    """
    if not chunks:
        raise ValueError("No chunks to index")
    combined = "\n".join(c.page_content for c in chunks)
    document_hash = canonical_hash(combined)
    user_key = str(user_id)

    async with _get_lock(user_key):
        # 1. Dedup guard at the DB layer (authoritative registry)
        existing = (
            await session.execute(
                select(DocumentRow).where(
                    DocumentRow.user_id == user_id,
                    DocumentRow.source_hash == document_hash,
                )
            )
        ).scalar_one_or_none()
        if existing is not None:
            raise DuplicateDocumentError(document_hash)

        # 2. Isolated vector write
        coll = user_collection_name(user_key, document_hash)
        chunk_count = write_chunks(
            coll, document_hash, user_id, source_type, source_uri, chunks
        )
        if chunk_count != len(chunks):
            raise RuntimeError(
                f"Vector write incomplete for doc {document_hash}: "
                f"{chunk_count}/{len(chunks)} written"
            )

        # 3. Durable metadata rows (documents + chunks)
        doc_row = DocumentRow(
            user_id=user_id,
            title=title,
            source_type=source_type,
            source_uri=source_uri,
            source_hash=document_hash,
            chunk_count=chunk_count,
        )
        session.add(doc_row)
        await session.flush()
        for i, ch in enumerate(chunks):
            session.add(
                ChunkRow(
                    doc_id=doc_row.id,
                    chunk_index=i,
                    content_hash=chunk_hash(ch.page_content),
                    text=ch.page_content,
                    metadata_json=_make_metadata(
                        user_id, document_hash, i, source_type, source_uri
                    ),
                )
            )
        await session.commit()

        audit_log(
            user_id,
            "doc_added",
            document_hash=document_hash,
            source_type=source_type,
            source_uri=source_uri,
            chunk_count=chunk_count,
            metadata={"collection": coll},
        )
        return document_hash, coll, chunk_count
def build_user_retriever_tool(
    user_id,
    document_hash: str,
    tool_name: str,
    description: str,
    k: int = 4,
):
    """Build a retriever tool scoped to a (user, document) collection."""
    coll = user_collection_name(user_id, document_hash)
    store = _open_user_store(coll)
    retriever = store.as_retriever(search_kwargs={"k": k})
    return create_retriever_tool(retriever, tool_name, description)


async def delete_user_document(
    *,
    user_id,
    session,
    document_hash: str,
    reason: str = "user_removed",
) -> bool:
    """Remove a single document (URL/PDF) for a user: DB rows then vectors.

    Deleting DB rows first means a crash mid-way leaves a deterministic,
    recoverable state (row gone, collection orphaned → reaped on next purge).
    """
    user_key = str(user_id)
    removed = delete_user_collection(user_key, document_hash)

    async with _get_lock(user_key):
        await session.execute(
            delete(DocumentRow).where(
                DocumentRow.user_id == user_id,
                DocumentRow.source_hash == document_hash,
            )
        )
        await session.commit()

    audit_log(
        user_id,
        "doc_removed",
        document_hash=document_hash,
        reason=reason,
        metadata={"vector_deleted": removed},
    )
    return removed


async def purge_user_data(*, user_id, session, reason: str = "logout") -> int:
    """Purge ALL of a user's vectors + document rows (logout / clear all).

    Returns the number of collections removed.
    """
    user_key = str(user_id)
    prefix = user_collection_prefix(user_key)

    async with _get_lock(user_key):
        await session.execute(delete(DocumentRow).where(DocumentRow.user_id == user_id))
        await session.commit()

    removed = _drop_collections_with_prefix(prefix)
    audit_log(
        user_id,
        "user_purged",
        reason=reason,
        metadata={"collections_removed": removed},
    )
    return removed
# ── Audit ───────────────────────────────────────────────────────────────────
def audit_log(
    user_id,
    action: str,
    *,
    document_hash: Optional[str] = None,
    source_type: Optional[str] = None,
    source_uri: Optional[str] = None,
    chunk_count: Optional[int] = None,
    reason: Optional[str] = None,
    metadata: Optional[dict] = None,
) -> None:
    """Structured, best-effort audit line (log + durable AuditLog row)."""
    msg = (
        f"{action} user={user_id}"
        + (f" doc={document_hash}" if document_hash else "")
        + (f" type={source_type}" if source_type else "")
        + (f" uri={source_uri}" if source_uri else "")
        + (f" chunks={chunk_count}" if chunk_count is not None else "")
        + (f" reason={reason}" if reason else "")
        + (f" meta={metadata}" if metadata else "")
    )
    log.info("[audit] %s", msg)

    # Best-effort durable audit record (never fails the request).
    try:
        asyncio.get_running_loop().create_task(
            _write_audit_row(
                user_id,
                action,
                document_hash=document_hash,
                source_type=source_type,
                source_uri=source_uri,
                chunk_count=chunk_count,
                metadata=metadata,
            )
        )
    except RuntimeError:
        pass  # No running loop — log-only audit.


async def _write_audit_row(
    user_id,
    action: str,
    document_hash: Optional[str] = None,
    source_type: Optional[str] = None,
    source_uri: Optional[str] = None,
    chunk_count: Optional[int] = None,
    metadata: Optional[dict] = None,
) -> None:
    try:
        async with async_session_factory() as session:
            session.add(
                AuditLog(
                    user_id=user_id,
                    action=action,
                    document_hash=document_hash,
                    source_type=source_type,
                    source_uri=source_uri,
                    chunk_count=chunk_count,
                    details=metadata,
                )
            )
            await session.commit()
    except Exception as e:  # pragma: no cover - defensive
        log.debug("AuditLog write skipped: %s", e)