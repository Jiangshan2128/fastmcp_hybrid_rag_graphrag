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
from contextlib import asynccontextmanager
from typing import TYPE_CHECKING, AsyncIterator

from fastmcp import FastMCP

if TYPE_CHECKING:
    from rag_kb.retriever import RAGRetriever

logger = logging.getLogger(__name__)

# ── Central FastMCP instance ─────────────────────────────────────────
# Tool modules import this and decorate via @mcp.tool.
# The lifespan ensures the retriever is initialized *before* any tool
# call arrives — no lazy-init delay on first use.


@asynccontextmanager
async def _lifespan(server: FastMCP) -> AsyncIterator[None]:
    """FastMCP lifespan: pre-warm retriever on startup, clean up on shutdown."""
    _init_retriever()
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

# ── Shared retriever singleton ───────────────────────────────────────
_retriever: RAGRetriever | None = None


def _init_retriever() -> None:
    """Initialize the retriever and index documents (called once via lifespan).

    Separated from ``get_retriever()`` so the lifespan can call it eagerly
    on startup, while tools still get the same singleton on demand.
    """
    global _retriever
    if _retriever is not None:
        return

    from rag_kb.config import get_rag_config
    from rag_kb.retriever import RAGRetriever

    logger.info("Startup: initializing RAGRetriever and indexing documents...")
    config = get_rag_config()
    _retriever = RAGRetriever(config)
    result = _retriever.initialize()
    logger.info("Startup indexing complete: %s", result.summary)


def get_retriever() -> RAGRetriever:
    """Return the singleton RAGRetriever.

    By the time any tool function runs, the lifespan has already called
    ``_init_retriever()`` — so this is always a fast no-op return.
    """
    global _retriever
    if _retriever is None:
        # Fallback: lifespan may not have run (e.g. in tests).
        _init_retriever()
    return _retriever


def reset_retriever() -> None:
    """Reset the retriever singleton (for shutdown / testing)."""
    global _retriever
    if _retriever is not None:
        _retriever.shutdown()
        _retriever = None
        logger.info("Retriever shut down.")
