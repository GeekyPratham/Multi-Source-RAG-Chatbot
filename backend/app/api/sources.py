"""api/sources.py — /api/sources endpoints for URL and PDF ingestion.

Every ingestion/removal is bound to the authenticated user (derived from the
JWT). Vectors live in user-isolated Chroma collections and are purged on
logout or per-document removal. Missing/invalid auth → 401.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.models import AddUrlRequest, SourceResponse, UploadPdfResponse
from app.core.models_db import Document as DocumentRow, User
from app.middleware.auth import get_current_user
from app.services import session_store, user_store
from app.services.pdf_service import load_pdf_chunks
from app.services.url_service import load_url_chunks
from app.utils.logger import log

router = APIRouter(prefix="/api/sources", tags=["sources"])


async def _resolve_document_hash(
    session: AsyncSession, user_id, source_type: str, source_uri: str
) -> str | None:
    """Find a user's stored document_hash for a source, or None."""
    row = (
        await session.execute(
            select(DocumentRow).where(
                DocumentRow.user_id == user_id,
                DocumentRow.source_type == source_type,
                DocumentRow.source_uri == source_uri,
            )
        )
    ).scalar_one_or_none()
    return row.source_hash if row else None


@router.post("/url", response_model=SourceResponse)
async def add_url(
    req: AddUrlRequest,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    """Index a URL into the authenticated user's isolated collection."""
    user_id = current_user.id
    user_key = str(user_id)

    title, preview, chunks = load_url_chunks(req.url)
    if title is None:
        raise HTTPException(status_code=400, detail="Could not load content from that URL.")

    try:
        document_hash, _coll, _n = await user_store.index_user_document(
            user_id=user_id,
            session=session,
            source_type="url",
            source_uri=req.url,
            title=title,
            chunks=chunks,
        )
    except user_store.DuplicateDocumentError:
        log.info("URL already loaded for user %s: %s", user_key, req.url)
        return SourceResponse(success=False, message="URL already loaded.")

    idx = len(session_store.get_session(user_key)["url_sources"]) + 1
    tool_name = f"URL_Source_{idx}"
    tool = user_store.build_user_retriever_tool(
        user_key,
        document_hash,
        tool_name,
        f"Source: WEBPAGE | URL: {req.url}\nTitle: '{title}'\nPreview: {preview}\n"
        f"Use this tool for questions about this webpage.",
    )
    session_store.register_url_tool(user_key, req.url, tool, document_hash, title, tool_name)

    log.info("URL added for user %s: %s", user_key, req.url)
    return SourceResponse(success=True, message=f"Loaded: {title}", tool_name=tool_name, title=title)

@router.post("/pdf", response_model=UploadPdfResponse)
async def upload_pdf(
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    """Index an uploaded PDF into the authenticated user's isolated collection."""
    user_id = current_user.id
    user_key = str(user_id)
    fname = file.filename or "upload.pdf"

    contents = await file.read()
    title, preview, chunks = load_pdf_chunks(contents, fname)
    if title is None:
        raise HTTPException(status_code=400, detail="PDF produced no content.")

    try:
        document_hash, _coll, _n = await user_store.index_user_document(
            user_id=user_id,
            session=session,
            source_type="pdf",
            source_uri=fname,
            title=title,
            chunks=chunks,
        )
    except user_store.DuplicateDocumentError:
        log.info("PDF already loaded for user %s: %s", user_key, fname)
        return UploadPdfResponse(success=False, message="PDF already loaded.", filename=fname)

    idx = len(session_store.get_session(user_key)["pdf_sources"]) + 1
    tool_name = f"PDF_Source_{idx}"
    tool = user_store.build_user_retriever_tool(
        user_key,
        document_hash,
        tool_name,
        f"Source: PDF | File: '{fname}'\nPreview: {preview}\n"
        f"Use this tool to answer questions about '{fname}'.",
    )
    session_store.register_pdf_tool(user_key, fname, tool, document_hash, tool_name)

    log.info("PDF added for user %s: %s", user_key, fname)
    return UploadPdfResponse(success=True, message=f"Loaded: {fname}", tool_name=tool_name, filename=fname)
@router.get("/list")
async def list_sources(
    current_user: User = Depends(get_current_user),
):
    """List the current user's loaded sources."""
    user_key = str(current_user.id)
    sess = session_store.get_session(user_key)
    return {
        "urls": [{"url": u, "title": i["title"], "tool_name": i["tool_name"]} for u, i in sess["url_sources"].items()],
        "pdfs": [{"filename": f, "tool_name": i["tool_name"]} for f, i in sess["pdf_sources"].items()],
    }


@router.delete("/url")
async def remove_url(
    url: str,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    """Remove a URL for the current user: vectors + rows + session tool."""
    user_id = current_user.id
    user_key = str(user_id)
    document_hash = session_store.pop_url(user_key, url) or await _resolve_document_hash(
        session, user_id, "url", url
    )
    if document_hash:
        await user_store.delete_user_document(
            user_id=user_id, session=session, document_hash=document_hash
        )
    return {"success": True}


@router.delete("/pdf")
async def remove_pdf(
    filename: str,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    """Remove a PDF for the current user: vectors + rows + session tool."""
    user_id = current_user.id
    user_key = str(user_id)
    document_hash = session_store.pop_pdf(user_key, filename) or await _resolve_document_hash(
        session, user_id, "pdf", filename
    )
    if document_hash:
        await user_store.delete_user_document(
            user_id=user_id, session=session, document_hash=document_hash
        )
    return {"success": True}


@router.delete("/clear")
async def clear_sources(
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    """Purge ALL of the current user's vectors + rows + session tools."""
    user_id = current_user.id
    user_key = str(user_id)
    await user_store.purge_user_data(user_id=user_id, session=session, reason="user_clear_all")
    session_store.clear_session(user_key)
    return {"success": True}