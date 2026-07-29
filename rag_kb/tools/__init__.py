"""MCP tool modules for the RAG knowledge base.

Tools are organized by domain and registered via ``@mcp.tool`` decorators
at import time.  ``server.py`` only needs to import the modules to
register everything.

.. code-block:: text

    rag_kb/tools/
    ├── __init__.py        — mcp instance, lifespan, retriever singleton
    ├── search.py          — zgh_search_docs, zgh_get_document, zgh_list_docs
    └── index.py           — zgh_refresh_index, zgh_get_doc_stats
"""

from __future__ import annotations

import logging
import threading
from contextlib import asynccontextmanager
from typing import TYPE_CHECKING, AsyncIterator

from fastmcp import FastMCP

if TYPE_CHECKING:
    from rag_kb.retriever import RAGRetriever

logger = logging.getLogger(__name__)

# ── Central FastMCP instance ─────────────────────────────────────────
# Tool modules import this and decorate via @mcp.tool.
# The lifespan starts background initialization and yields immediately;
# the first tool call will check readiness and return a friendly message
# if the retriever isn't ready yet.


@asynccontextmanager
async def _lifespan(server: FastMCP) -> AsyncIterator[None]:
    """FastMCP lifespan: start background init, don't block server startup.

    Initialization (creating embeddings, loading vector store, indexing
    documents) runs in a daemon thread.  Tool calls check a ready flag
    and return a "still initializing" message if indexing hasn't finished
    yet — the server stays responsive to the MCP host immediately.
    """
    _start_background_init()
    yield
    reset_retriever()


mcp = FastMCP(
    "智冠华 Internal Knowledge Base",
    lifespan=_lifespan,
    instructions=(
        "## 适用场景\n"
        "当用户提及以下内容时，应调用本知识库：\n"
        "- 内部文档、产品规格、技术参数、性能指标\n"
        '- 提到"智冠华"相关项目的任何技术问题\n'
        "- 设备 SDK 接口定义、协议说明\n\n"
        "## 不适用场景\n"
        "- 通用编程问题 — 使用 AI 自身知识即可\n"
        "- 实时数据 / 在线查询 — 本库为静态文档知识库\n"
        "- 外部网页搜索 — 请使用网页搜索工具\n\n"
        "## 工具选择指南\n"
        "- ``zgh_search_docs``：查询具体参数、指标、接口定义等\n"
        "  **可从独立段落直接提取的信息**。速度快、token 消耗低，是首选。\n"
        "- ``zgh_search_graph``：需要**跨段落推理、总结归纳、\n"
        "  多文档关联分析**时使用。\n"
        "- **同等效果下优先使用 ``zgh_search_docs``**。\n\n"
        "## 推荐工作流\n"
        "1. 先用 ``zgh_list_docs`` 了解知识库中有哪些文档\n"
        "2. 用 ``zgh_search_docs`` 进行具体参数 / 指标查询\n"
        "3. 如需跨文档推理或全局总结，再用 ``zgh_search_graph``\n"
        "4. 需要完整原文时使用 ``zgh_get_document``\n"
        "5. 新文档放入后调用 ``zgh_refresh_index`` 重新索引\n\n"
        "## 注意\n"
        "- 文档以中文为主，查询请使用中文\n"
        "- 用 ``zgh_get_doc_stats`` 可查看索引状态"
    ),
)

# ── Shared retriever singleton with background initialisation ─────────
# Lifecycle:
#   lifespan → _start_background_init() → thread runs initialize()
#                                            ↓ success    ↓ failure
#                                     set _retriever    set _retriever_init_error
#   get_retriever() → check ready flag → ready → return
#                                     → not ready → raise RetrieverNotReadyError
#
# Each tool function catches RetrieverNotReadyError and returns a
# friendly "still initializing, please retry" message instead of
# blocking the MCP request.

_retriever: RAGRetriever | None = None
_retriever_init_event: threading.Event | None = None
_retriever_init_error: Exception | None = None


RETRIEVER_NOT_READY = "【知识库正在初始化】后台索引文档中，请稍候重试。"


class RetrieverNotReadyError(RuntimeError):
    """Raised by ``get_retriever()`` when background init hasn't completed yet.

    Tool functions catch this and return a user-friendly retry message
    instead of blocking the MCP request handler.
    """


def _background_init_worker() -> None:
    """Background thread: run retriever initialisation (embeddings, store, index).

    Only sets ``_retriever`` on success.  On failure, stores the exception
    so ``get_retriever()`` can re-raise it to the caller.
    """
    global _retriever, _retriever_init_error
    try:
        from rag_kb.config import get_rag_config
        from rag_kb.retriever import RAGRetriever

        logger.info(
            "Background init: initializing RAGRetriever and indexing documents..."
        )
        config = get_rag_config()
        retriever = RAGRetriever(config)
        result = retriever.initialize()
        _retriever = retriever
        logger.info("Background init complete: %s", result.summary)
    except Exception as e:
        _retriever_init_error = e
        logger.error("Background init failed (first tool call will raise): %s", e)
    finally:
        if _retriever_init_event is not None:
            _retriever_init_event.set()


def _start_background_init() -> None:
    """Start retriever initialisation in a daemon thread.

    Called once from the lifespan.  Idempotent — subsequent calls are no-ops.
    """
    global _retriever_init_event
    if _retriever is not None:
        return
    if _retriever_init_event is not None:
        return  # already started

    _retriever_init_event = threading.Event()
    thread = threading.Thread(target=_background_init_worker, daemon=True)
    thread.start()
    logger.debug("Background init thread started")


def get_retriever() -> RAGRetriever:
    """Return the singleton retriever if ready, or raise ``RetrieverNotReadyError``.

    NEVER blocks — returns instantly.  Tool functions catch the error and
    respond with a friendly retry message.
    """
    global _retriever

    # Fast path — already initialised.
    if _retriever is not None:
        return _retriever

    # Background init was started — check if it's done.
    event = _retriever_init_event
    if event is not None:
        if event.is_set():
            # Event fired — init completed (success or failure).
            if _retriever_init_error:
                raise RuntimeError(
                    f"Initialisation failed: {_retriever_init_error}"
                ) from _retriever_init_error
            if _retriever is None:
                raise RuntimeError("Initialisation completed but retriever is None")
            return _retriever

        # Init is still running — don't block.
        raise RetrieverNotReadyError(
            "Knowledge base is still initialising. "
            "Indexing documents in the background — "
            "please wait a moment and try again."
        )

    # No background init was started (e.g. tests) — do it synchronously.
    _init_retriever_sync()
    return _retriever


def _init_retriever_sync() -> None:
    """Synchronous initialisation fallback for when lifespan never ran."""
    global _retriever
    if _retriever is not None:
        return

    from rag_kb.config import get_rag_config
    from rag_kb.retriever import RAGRetriever

    logger.info("Sync init: initializing RAGRetriever...")
    config = get_rag_config()
    retriever = RAGRetriever(config)
    result = retriever.initialize()
    _retriever = retriever
    logger.info("Sync init complete: %s", result.summary)


def reset_retriever() -> None:
    """Reset the retriever singleton (for shutdown / testing)."""
    global _retriever, _retriever_init_event, _retriever_init_error
    if _retriever is not None:
        _retriever.shutdown()
        _retriever = None
    _retriever_init_event = None
    _retriever_init_error = None
    logger.info("Retriever shut down.")
