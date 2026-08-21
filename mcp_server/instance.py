"""FastMCP server instance and lifespan.

The shared ``mcp`` instance lives here (not in ``mcp_server/__init__.py``)
so tool modules can import it directly via ``from mcp_server.instance
import mcp`` without circular imports — the standard "server module"
pattern.  ``mcp_server/__init__.py`` re-exports it for entry points such
as ``fastmcp run mcp_server:mcp``.
"""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from typing import AsyncIterator

from fastmcp import FastMCP

from mcp_server.runtime import _start_background_init, reset_retriever

logger = logging.getLogger(__name__)


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
    "zgh Internal Knowledge Base",
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
        "3. 如需跨文档推理，再用 ``zgh_search_graph``\n"
        "4. 需要完整原文时使用 ``zgh_get_document``\n"
        "5. 新文档放入后调用 ``zgh_refresh_index`` 重新索引\n\n"
        "## 注意\n"
        "- 文档以中文为主，查询请使用中文\n"
        "- 用 ``zgh_get_doc_stats`` 可查看索引状态"
    ),
)
