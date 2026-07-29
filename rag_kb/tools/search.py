"""MCP tools — search and retrieval.

Tools registered at import time via ``@mcp.tool``:

    zgh_search_docs    — Semantic search for product specs, parameters, SDK docs
    zgh_get_document   — Read a full internal document by path
    zgh_list_docs      — List all indexed internal documents
    zgh_get_usage_guide — Get usage guide for the knowledge base (start here)
"""

from __future__ import annotations

import logging
from pathlib import Path

from rag_kb.tools import get_retriever, mcp

logger = logging.getLogger(__name__)


@mcp.tool
def zgh_get_usage_guide() -> str:
    """Get the usage guide for the 智冠华 Internal Knowledge Base.

    Call this tool FIRST when:
    - You're unsure which knowledge base tool to use
    - You want to understand what kinds of questions this server can answer
    - You need to know the recommended search workflow

    Returns:
        Usage guide with when-to-use guidance and tool selection rules.
    """
    return (
        "## 智冠华 Internal Knowledge Base — 使用指南\n\n"
        "### 适用场景\n"
        "- 内部文档、产品规格、技术参数、性能指标\n"
        '- 提到"智冠华"相关项目的技术问题\n'
        "- 设备 SDK 接口定义、协议说明\n\n"
        "### 不适用\n"
        "- 通用编程问题\n"
        "- 实时数据 / 在线查询\n"
        "- 外部网页搜索\n\n"
        "### 工具选择\n"
        "- ``zgh_search_docs``（首选）：具体参数、指标、接口定义，"
        "可从独立段落直接提取 → 快、省 token\n"
        "- ``zgh_search_graph``：跨段落推理、总结归纳、多文档关联分析\n"
        "- ``zgh_list_docs``：查看知识库中有哪些文档\n"
        "- ``zgh_get_document``：读取完整文档原文\n"
        "- ``zgh_refresh_index``：新文档放入后重新索引\n"
        "- ``zgh_get_doc_stats``：查看索引状态\n\n"
        "### 推荐流程\n"
        "1. ``zgh_list_docs`` → 了解有什么文档\n"
        "2. ``zgh_search_docs`` → 查询具体内容\n"
        "3. 如需跨文档推理 → ``zgh_search_graph``\n"
        "4. 需要的片段未覆盖 → ``zgh_get_document`` 读原文\n\n"
        "### 注意\n"
        "- 文档以中文为主，查询请使用中文\n"
        "- 同等效果优先 ``zgh_search_docs``"
    )


@mcp.tool
def zgh_search_docs(query: str, top_k: int = 5) -> str:
    """Search internal product specs, device parameters, and SDK documentation.

    Use this to look up technical specifications, interface definitions,
    performance metrics, and other parameter-level details from the 智冠华
    internal document library.

    For cross-document reasoning or global summarization, prefer
    ``zgh_search_graph`` instead.

    Args:
        query: Natural language query describing what you're looking for.
               Chinese is recommended for best results.
        top_k: Number of top results to return (default: 5, max: 20).

    Returns:
        Formatted search results with content snippet, source path,
        and relevance score.
    """
    top_k = min(top_k, 20)
    retriever = get_retriever()
    return retriever.search(query, top_k=top_k)


@mcp.tool
def zgh_get_document(path: str) -> str:
    """Read a full internal document by its relative path.

    Use this when ``zgh_search_docs`` snippets are insufficient and you
    need the complete original text of a product spec or SDK document.

    Args:
        path: Relative path within the documents directory
              (e.g. ``设备SDK接口需求文档.v1.3.md``).

    Returns:
        The full text content of the document, or an error message
        if not found.
    """
    from rag_kb.config import get_rag_config

    config = get_rag_config()
    doc_dir = Path(config.DOCUMENTS_PATH)
    full_path = (doc_dir / path).resolve()

    # Security: prevent path traversal outside documents directory
    if not str(full_path).startswith(str(doc_dir.resolve())):
        return (
            f"Error: path traversal detected — '{path}' is outside "
            "the documents directory."
        )

    if not full_path.is_file():
        return f"Error: document not found at '{path}'."

    try:
        text = full_path.read_text(encoding="utf-8")
        suffix = full_path.suffix.lower()
        lines = [
            f"# {path}",
            f"```{suffix.lstrip('.')}",
            text.rstrip(),
            "```",
        ]
        return "\n".join(lines)
    except Exception as e:
        return f"Error reading document '{path}': {e}"


@mcp.tool
def zgh_list_docs() -> str:
    """List all indexed documents in the 智冠华 internal document library.

    Returns each document with its chunk count, file name, and source path.
    Call this first to understand what product specs and SDK documents
    are available before searching.

    Returns:
        Formatted list of indexed documents.
    """
    retriever = get_retriever()
    return retriever.list_sources()
