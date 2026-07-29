"""MCP tools — index management.

Tools registered at import time via ``@mcp.tool``:

    zgh_refresh_index  — Re-index internal documents after adding or updating files
    zgh_get_doc_stats  — View document library statistics and index status
"""

from __future__ import annotations

import logging

from rag_kb.tools import get_retriever, mcp

logger = logging.getLogger(__name__)


@mcp.tool
def zgh_refresh_index(full_rebuild: bool = False) -> str:
    """Re-index all documents in the 智冠华 internal document library.

    Normally, only new or changed files are re-indexed (content-hash cache).
    Use ``full_rebuild=true`` to rebuild every document from scratch.

    Call this after dropping new DOCX or Markdown files into the documents
    directory.

    Args:
        full_rebuild: If true, re-index everything (ignores cache).

    Returns:
        Summary of what was indexed.
    """
    retriever = get_retriever()
    result = retriever.refresh_index(full_rebuild=full_rebuild)

    msg = f"Index refreshed: {result.summary}"
    if result.errors:
        msg += f"\nErrors ({len(result.errors)}):"
        for err in result.errors[:5]:
            msg += f"\n  - {err}"
    return msg


@mcp.tool
def zgh_get_doc_stats() -> str:
    """Get statistics about the 智冠华 internal document library.

    Returns total indexed chunks, number of unique documents, vector store
    backend, and whether auto-indexing and file watching are enabled.

    Call this to verify what's available before searching.

    Returns:
        Formatted statistics about the document library.
    """
    retriever = get_retriever()
    stats = retriever.get_doc_stats()

    lines = [
        "📊 Knowledge Base Statistics",
        f"  Backend:          {stats['backend']}",
        f"  Total chunks:     {stats['total_chunks']}",
        f"  Total sources:    {stats['total_sources']}",
        f"  Documents dir:    {stats['doc_dir']}",
        f"  Auto-index:       {'✅' if stats['auto_index'] else '❌'}",
        f"  File watching:    {'✅' if stats['watch_enabled'] else '❌'}",
    ]
    return "\n".join(lines)
