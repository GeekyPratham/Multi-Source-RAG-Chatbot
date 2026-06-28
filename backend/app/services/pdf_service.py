"""services/pdf_service.py — PDF loading + persistent vector indexing."""
from __future__ import annotations
import hashlib, os, tempfile
from langchain_community.document_loaders import PyPDFLoader
from langchain_core.tools import create_retriever_tool
from langchain_text_splitters import RecursiveCharacterTextSplitter
from app.services.vector_store import get_or_create_store, pdf_collection
from app.utils.logger import log

_SPLITTER = RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=200)


def load_pdf_tool(file_bytes: bytes, filename: str, index: int):
    content_hash = hashlib.sha256(file_bytes).hexdigest()[:12]
    coll = pdf_collection(filename, content_hash)

    with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
        tmp.write(file_bytes)
        tmp_path = tmp.name
    try:
        docs = PyPDFLoader(tmp_path).load()
    finally:
        os.unlink(tmp_path)

    if not docs:
        return None, ""

    preview = docs[0].page_content[:300].replace("\n", " ").strip()
    chunks = _SPLITTER.split_documents(docs)
    store = get_or_create_store(coll, chunks)
    retriever = store.as_retriever(search_kwargs={"k": 4})
    tool_name = f"PDF_Source_{index}"
    tool = create_retriever_tool(
        retriever, tool_name,
        f"Source: PDF | File: '{filename}'\nPreview: {preview}\n"
        f"Use this tool to answer questions about '{filename}'."
    )
    log.info("PDF tool ready: %s", tool_name)
    return tool, coll
