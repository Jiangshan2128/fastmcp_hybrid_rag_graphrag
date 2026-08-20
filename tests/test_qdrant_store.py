"""Tests for QdrantStore hybrid-search text_type routing.

These use fake embeddings and a fake client so no DashScope API call or
Qdrant disk file-lock is ever touched. ``QdrantStore`` is built via
``object.__new__`` to skip ``__init__`` (which would create a real
on-disk client).
"""

from __future__ import annotations

from types import SimpleNamespace

from rag_kb.interfaces import IndexedDoc
from rag_kb.qdrant_store import QdrantStore


class FakeEmbeddings:
    """Records how the store calls the embeddings layer."""

    def __init__(self) -> None:
        self.hybrid_calls: list[tuple[list[str], str]] = []
        self.dense_calls = 0
        self.sparse_calls = 0

    def embed_with_sparse(self, texts: list[str], text_type: str = "document"):
        self.hybrid_calls.append((texts, text_type))
        dense = [[0.1] * 4 for _ in texts]
        sparse = [{1: 0.5} for _ in texts]
        return dense, sparse

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        self.dense_calls += 1
        return [[0.1] * 4 for _ in texts]

    def embed_query(self, text: str) -> list[float]:
        self.dense_calls += 1
        return [0.1] * 4

    def encode_sparse(self, texts: list[str], text_type: str = "document"):
        self.sparse_calls += 1
        return [{1: 0.5} for _ in texts]


class FakeClient:
    """Minimal Qdrant client stub — records calls, returns canned hits."""

    def __init__(self) -> None:
        self.upsert_count = 0
        self.last_upsert: dict | None = None
        self.query_points_kwargs: dict | None = None

    def upsert(self, **kwargs) -> None:
        self.upsert_count += 1
        self.last_upsert = kwargs

    def query_points(self, **kwargs):
        self.query_points_kwargs = kwargs
        hit = SimpleNamespace(
            payload={
                "content": "matched chunk",
                "metadata": {"source": "a.md", "file_name": "a.md"},
            },
            score=0.9,
        )
        return SimpleNamespace(points=[hit])


def _make_store(has_sparse: bool) -> tuple[QdrantStore, FakeEmbeddings, FakeClient]:
    store = object.__new__(QdrantStore)
    emb = FakeEmbeddings()
    client = FakeClient()
    store._has_sparse = has_sparse
    store._embeddings = emb
    store._client = client
    store._collection_name = "test_coll"
    return store, emb, client


# ── Indexing path ─────────────────────────────────────────────────────

def test_add_documents_calls_embed_with_sparse_with_text_type_document():
    store, emb, client = _make_store(has_sparse=True)
    chunks = [IndexedDoc(id="1", content="hello", metadata={"source": "a.md"})]

    count = store.add_documents(chunks)

    assert count == 1
    assert emb.hybrid_calls == [(["hello"], "document")]
    assert client.upsert_count == 1
    # payload stored on the point
    point = client.last_upsert["points"][0]
    assert point.payload["content"] == "hello"
    assert point.payload["metadata"]["source"] == "a.md"
    # named vectors for dense + sparse
    assert set(point.vector.keys()) == {"dense", "sparse"}


def test_add_documents_without_sparse_uses_embed_documents():
    store, emb, client = _make_store(has_sparse=False)
    chunks = [IndexedDoc(id="1", content="hello", metadata={"source": "a.md"})]

    count = store.add_documents(chunks)

    assert count == 1
    assert emb.hybrid_calls == []  # no embed_with_sparse
    assert emb.dense_calls == 1    # embed_documents used
    # only the dense named vector
    point = client.last_upsert["points"][0]
    assert set(point.vector.keys()) == {"dense"}


# ── Query path ────────────────────────────────────────────────────────

def test_hybrid_search_uses_single_embed_with_sparse_call_text_type_query():
    store, emb, client = _make_store(has_sparse=True)

    results = store._hybrid_search("机芯供电电压", k=5)

    assert len(results) == 1
    assert results[0].content == "matched chunk"
    # ONE call, direction = query, not the two-call path
    assert emb.hybrid_calls == [(["机芯供电电压"], "query")]
    assert emb.dense_calls == 0    # embed_query NOT used
    assert emb.sparse_calls == 0   # encode_sparse NOT used

    kwargs = client.query_points_kwargs
    assert kwargs["limit"] == 5
    # two prefetch lanes → RRF fusion
    prefetch = kwargs["prefetch"]
    assert [p.using for p in prefetch] == ["dense", "sparse"]
    # prefetch surplus: max(20, min(100, k*3)) = 20 for k=5
    assert [p.limit for p in prefetch] == [20, 20]
    assert kwargs["query"].rrf.k == 60


def test_hybrid_search_prefetch_limit_scales_with_k():
    store, emb, client = _make_store(has_sparse=True)

    store._hybrid_search("q", k=50)

    prefetch = client.query_points_kwargs["prefetch"]
    assert [p.limit for p in prefetch] == [100, 100]  # capped at 100


def test_dense_search_uses_embed_query_and_dense_vector():
    store, emb, client = _make_store(has_sparse=True)

    results = store._dense_search("hello", k=3)

    assert len(results) == 1
    assert emb.dense_calls == 1
    assert emb.hybrid_calls == []
    kwargs = client.query_points_kwargs
    assert kwargs["using"] == "dense"
    assert kwargs["limit"] == 3
    assert "prefetch" not in kwargs


def test_similarity_search_routes_to_hybrid_when_sparse_available():
    store, emb, client = _make_store(has_sparse=True)

    store.similarity_search("query", k=5)

    assert emb.hybrid_calls == [(["query"], "query")]


def test_similarity_search_routes_to_dense_when_no_sparse():
    store, emb, client = _make_store(has_sparse=False)

    store.similarity_search("query", k=5)

    assert emb.hybrid_calls == []
    assert emb.dense_calls == 1
    assert client.query_points_kwargs["using"] == "dense"
