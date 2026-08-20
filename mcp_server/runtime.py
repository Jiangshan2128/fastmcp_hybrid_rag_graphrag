"""Retriever singleton with background initialisation.

Owns the ``RAGRetriever`` singleton for the MCP server and its
non-blocking startup lifecycle.  Initialization (creating embeddings,
loading the vector store, indexing documents) runs in a daemon thread
started from the FastMCP lifespan (see :mod:`mcp_server.instance`).
Tool handlers call :func:`get_retriever`; if init hasn't finished, it
raises :class:`RetrieverNotReadyError`, which handlers catch and answer
with a friendly retry message instead of blocking the MCP request.

Lifecycle::

    lifespan → _start_background_init() → thread runs initialize()
                                              ↓ success    ↓ failure
                                       set _retriever    set _retriever_init_error
    get_retriever() → check ready flag → ready → return
                                      → not ready → raise RetrieverNotReadyError

This module imports nothing from ``mcp_server`` — it only reaches into
the pure domain layer (``rag_kb``), keeping the dependency direction
``mcp_server → rag_kb``.
"""

from __future__ import annotations

import logging
import threading
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from rag_kb.retriever import RAGRetriever

logger = logging.getLogger(__name__)

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
