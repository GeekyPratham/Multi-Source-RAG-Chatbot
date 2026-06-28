"""api/sources.py — /api/sources endpoints for URL and PDF ingestion."""
from fastapi import APIRouter, HTTPException, UploadFile, File, Form
from pydantic import BaseModel
from app.core.models import SourceResponse, UploadPdfResponse
from app.services.url_service import load_url_tool
from app.services.pdf_service import load_pdf_tool
from app.services import session_store
from app.utils.logger import log


class AddUrlRequest(BaseModel):
    url: str
    session_id: str = "default"


router = APIRouter(prefix="/api/sources", tags=["sources"])


@router.post("/url", response_model=SourceResponse)
async def add_url(req: AddUrlRequest):
    sess = session_store.get_session(req.session_id)
    if req.url in sess["url_sources"]:
        return SourceResponse(success=False, message="URL already loaded.")

    idx = len(sess["url_sources"]) + 1
    try:
        tool, title, coll = load_url_tool(req.url, idx)
        if not tool:
            raise HTTPException(status_code=400, detail="Could not load content from that URL.")
        tool_name = f"URL_Source_{idx}"
        sess["url_sources"][req.url] = {"tool": tool, "title": title or req.url, "tool_name": tool_name, "collection": coll}
        log.info("URL added to session %s: %s", req.session_id, req.url)
        return SourceResponse(success=True, message=f"Loaded: {title or req.url}", tool_name=tool_name, title=title)
    except HTTPException:
        raise
    except Exception as e:
        log.error("URL load error: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/pdf", response_model=UploadPdfResponse)
async def upload_pdf(
    file: UploadFile = File(...),
    session_id: str = Form(default="default"),
):
    sess = session_store.get_session(session_id)
    fname = file.filename or "upload.pdf"
    if fname in sess["pdf_sources"]:
        return UploadPdfResponse(success=False, message="PDF already loaded.", filename=fname)

    contents = await file.read()
    idx = len(sess["pdf_sources"]) + 1
    try:
        tool, coll = load_pdf_tool(contents, fname, idx)
        if not tool:
            raise HTTPException(status_code=400, detail="PDF produced no content.")
        tool_name = f"PDF_Source_{idx}"
        sess["pdf_sources"][fname] = {"tool": tool, "tool_name": tool_name, "collection": coll}
        log.info("PDF added to session %s: %s", session_id, fname)
        return UploadPdfResponse(success=True, message=f"Loaded: {fname}", tool_name=tool_name, filename=fname)
    except HTTPException:
        raise
    except Exception as e:
        log.error("PDF load error: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/list")
async def list_sources(session_id: str = "default"):
    sess = session_store.get_session(session_id)
    return {
        "urls": [{"url": u, "title": i["title"], "tool_name": i["tool_name"]} for u, i in sess["url_sources"].items()],
        "pdfs": [{"filename": f, "tool_name": i["tool_name"]} for f, i in sess["pdf_sources"].items()],
    }


@router.delete("/url")
async def remove_url(url: str, session_id: str = "default"):
    sess = session_store.get_session(session_id)
    sess["url_sources"].pop(url, None)
    return {"success": True}


@router.delete("/pdf")
async def remove_pdf(filename: str, session_id: str = "default"):
    sess = session_store.get_session(session_id)
    sess["pdf_sources"].pop(filename, None)
    return {"success": True}


@router.delete("/clear")
async def clear_session(session_id: str = "default"):
    session_store.clear_session(session_id)
    return {"success": True}