"""Tests for the ``text_type`` parameter on hybrid embedding methods.

Covers the directional-query change: ``embed_with_sparse`` / ``encode_sparse``
must accept ``text_type`` (default ``"document"``) and forward it to the
DashScope call, on both the Qwen and BGE-M3 providers.
"""

from __future__ import annotations

import inspect

from rag_kb.embeddings import BgeM3Embeddings, QwenEmbeddings


# ── Signature contract ────────────────────────────────────────────────

def _text_type_param(func) -> inspect.Parameter:
    params = inspect.signature(func).parameters
    assert "text_type" in params, f"{func.__qualname__} missing text_type"
    return params["text_type"]


def test_qwen_embed_with_sparse_has_text_type_default_document():
    param = _text_type_param(QwenEmbeddings.embed_with_sparse)
    assert param.default == "document"


def test_qwen_encode_sparse_has_text_type_default_document():
    param = _text_type_param(QwenEmbeddings.encode_sparse)
    assert param.default == "document"


def test_bge_m3_embed_with_sparse_has_text_type_default_document():
    param = _text_type_param(BgeM3Embeddings.embed_with_sparse)
    assert param.default == "document"


def test_bge_m3_encode_sparse_has_text_type_default_document():
    param = _text_type_param(BgeM3Embeddings.encode_sparse)
    assert param.default == "document"


# ── text_type forwarding (Qwen → DashScope) ───────────────────────────

def test_qwen_embed_with_sparse_forwards_text_type(monkeypatch):
    emb = QwenEmbeddings()
    calls: list[tuple[list[str], str]] = []

    def fake_hybrid(texts: list[str], text_type: str):
        calls.append((texts, text_type))
        return ([[0.1, 0.2]], [{7: 0.5}])

    monkeypatch.setattr(emb, "_encode_hybrid", fake_hybrid)

    emb.embed_with_sparse(["hello"], text_type="query")
    emb.embed_with_sparse(["world"])  # no arg → default

    assert calls == [(["hello"], "query"), (["world"], "document")]


def test_qwen_encode_sparse_forwards_text_type(monkeypatch):
    emb = QwenEmbeddings()
    calls: list[tuple[list[str], str]] = []

    def fake_sparse_only(texts: list[str], text_type: str):
        calls.append((texts, text_type))
        return [{7: 0.5}]

    monkeypatch.setattr(emb, "_encode_sparse_only", fake_sparse_only)

    emb.encode_sparse(["hello"], text_type="query")
    emb.encode_sparse(["world"])

    assert calls == [(["hello"], "query"), (["world"], "document")]


# ── text_type accepted for parity (BGE-M3, local model) ───────────────

def test_bge_m3_methods_accept_text_type_without_error():
    # BGE-M3 is a local model and encodes query/document identically,
    # but must still accept text_type for interface parity with Qwen.
    assert BgeM3Embeddings.embed_with_sparse.__defaults__ == ("document",)
    assert BgeM3Embeddings.encode_sparse.__defaults__ == ("document",)
