"""services/url_service.py — URL loading + persistent vector indexing."""
from __future__ import annotations
import validators
from langchain_community.document_loaders import WebBaseLoader
from langchain_core.tools import create_retriever_tool
from langchain_text_splitters import RecursiveCharacterTextSplitter
from app.services.vector_store import get_or_create_store, url_collection
from app.utils.logger import log

_SPLITTER = RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=200)


def load_url_tool(url: str, index: int):
    if not validators.url(url):
        return None, "", ""
    coll = url_collection(url)
    try:
        docs = WebBaseLoader(url).load()
    except Exception as e:
        log.error("URL load failed '%s': %s", url, e)
        return None, "", ""
    if not docs:
        return None, "", ""

    title = docs[0].metadata.get("title", url).strip()
    preview = docs[0].page_content[:300].replace("\n", " ").strip()
    chunks = _SPLITTER.split_documents(docs)
    store = get_or_create_store(coll, chunks)
    retriever = store.as_retriever(search_kwargs={"k": 4})
    tool_name = f"URL_Source_{index}"
    tool = create_retriever_tool(
        retriever, tool_name,
        f"Source: WEBPAGE | URL: {url}\nTitle: '{title}'\nPreview: {preview}\n"
        f"Use this tool for questions about this webpage."
    )
    log.info("URL tool ready: %s", tool_name)
    return tool, title, coll
