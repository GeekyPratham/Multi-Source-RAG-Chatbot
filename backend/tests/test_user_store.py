"""tests/test_user_store.py — hashing, isolation, naming & metadata contract.

Unit-level tests only: no DB, no Chroma, no network. They verify the security
invariants of the vector store architecture (deterministic identity, per-user
isolation, metadata contract, concurrency guards).
"""
import asyncio

import pytest

from app.services import user_store as us


# ── Hashing strategy ─────────────────────────────────────────────────────────
class TestHashing:
    def test_canonical_hash_is_deterministic(self):
        assert us.canonical_hash("hello world") == us.canonical_hash("hello world")

    def test_canonical_hash_is_full_sha256_hex(self):
        h = us.canonical_hash("content")
        assert len(h) == 64
        int(h, 16)  # valid hex

    def test_canonical_hash_normalizes_whitespace(self):
        assert us.canonical_hash("a\n  b\tc") == us.canonical_hash("a b c")

    def test_canonical_hash_distinguishes_content(self):
        assert us.canonical_hash("alpha") != us.canonical_hash("beta")

    def test_chunk_hash_is_raw_sha256(self):
        assert us.chunk_hash("x") == __import__("hashlib").sha256(b"x").hexdigest()


# ── User isolation via collection naming ─────────────────────────────────────
class TestCollectionNaming:
    def test_deterministic_for_same_user_and_doc(self):
        assert (
            us.user_collection_name("u1", "h123")
            == us.user_collection_name("u1", "h123")
        )

    def test_different_users_never_share_a_collection(self):
        # Same document hash — still must be separate collections per user.
        names = {us.user_collection_name(u, "samehash") for u in ("u1", "u2", "u3")}
        assert len(names) == 3

    def test_prefix_is_consistent_with_collection_name(self):
        name = us.user_collection_name("u1", "h123")
        assert name.startswith(us.user_collection_prefix("u1"))

    def test_prefixes_differ_between_users(self):
        assert us.user_collection_prefix("u1") != us.user_collection_prefix("u2")

    def test_collection_name_length_bounded(self):
        # Chroma collection names must stay short/safe.
        assert len(us.user_collection_name("u" * 500, "d" * 500)) <= 50


# ── Composite metadata contract ───────────────────────────────────────────────
class TestMetadataContract:
    def test_required_fields_present(self):
        md = us._make_metadata("u1", "hash", 3, "url", "https://x.com")
        for key in (
            us.META_USER_ID,
            us.META_DOC_HASH,
            us.META_CHUNK_INDEX,
            us.META_SOURCE_TYPE,
            us.META_SOURCE_URI,
            us.META_TIMESTAMP,
        ):
            assert key in md

    def test_values_are_correct(self):
        md = us._make_metadata("u7", "abc", 2, "pdf", None)
        assert md[us.META_USER_ID] == "u7"
        assert md[us.META_DOC_HASH] == "abc"
        assert md[us.META_CHUNK_INDEX] == 2
        assert md[us.META_SOURCE_TYPE] == "pdf"
        assert md[us.META_SOURCE_URI] == ""  # empty, not None (Chroma-safe)
        assert md[us.META_TIMESTAMP].endswith("+00:00")


# ── Concurrency guards ────────────────────────────────────────────────────────
class TestPerUserLocks:
    def test_same_user_shares_one_lock(self):
        assert us._get_lock("uA") is us._get_lock("uA")

    def test_different_users_get_distinct_locks(self):
        assert us._get_lock("uA") is not us._get_lock("uB")


# ── Error types ───────────────────────────────────────────────────────────────
class TestErrors:
    def test_duplicate_document_error_carries_hash(self):
        err = us.DuplicateDocumentError("deadbeef")
        assert err.document_hash == "deadbeef"

    def test_lock_serializes_writers(self):
        """Two coroutines for the same user must not interleave writes."""
        order = []
        lock = us._get_lock("uL")

        async def writer(tag):
            async with lock:
                order.append(f"{tag}:in")
                await asyncio.sleep(0)
                order.append(f"{tag}:out")

        async def run():
            await asyncio.gather(writer("a"), writer("b"))

        asyncio.run(run())
        # Each writer's in/out pair must be contiguous — no interleaving.
        assert order == ["a:in", "a:out", "b:in", "b:out"] or order == [
            "b:in",
            "b:out",
            "a:in",
            "a:out",
        ]
