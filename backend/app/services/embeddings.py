"""services/embeddings.py — singleton HuggingFace embedding model."""
from __future__ import annotations
from functools import lru_cache
from langchain_huggingface import HuggingFaceEmbeddings
from app.utils.logger import log

MODEL_NAME = "sentence-transformers/all-MiniLM-L6-v2"


@lru_cache(maxsize=1)
def get_embeddings() -> HuggingFaceEmbeddings:
    log.info("Loading embedding model: %s", MODEL_NAME)
    return HuggingFaceEmbeddings(
        model_name=MODEL_NAME,
        model_kwargs={"device": "cpu"},
        encode_kwargs={"normalize_embeddings": True},
    )
