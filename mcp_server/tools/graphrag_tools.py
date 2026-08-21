"""MCP tools — GraphRAG knowledge graph search.

Tools registered at import time via ``@mcp.tool``::

    zgh_search_graph              — Cross-document reasoning & knowledge graph retrieval
    zgh_refresh_graphrag_index    — Rebuild the knowledge graph from indexed documents
    zgh_get_graphrag_index_status — Check knowledge graph index readiness

These complement ``zgh_search_docs``. The caller should choose based on
query type:

- ``zgh_search_docs``: fast vector search, best for concrete specs/parameters
  that can be extracted from a single passage
- ``zgh_search_graph``: graph-based retrieval, best for cross-document
  reasoning, global overviews, and multi-hop relationship queries
"""

from __future__ import annotations

import logging
import sys
from pathlib import Path

from mcp_server.instance import mcp

logger = logging.getLogger(__name__)

# GraphRAG store singleton (lazy init, shared across tools)
_graphrag_store = None
_GRAPHRAG_ROOT = None


def _get_graphrag_root() -> str:
    """Return the absolute path to the graphrag project directory."""
    global _GRAPHRAG_ROOT
    if _GRAPHRAG_ROOT is None:
        # Mirror rag_kb/config.py: PyInstaller bundle → dir of server.exe,
        # development → parent of this file (mcp_server/tools/ → project root).
        if getattr(sys, "frozen", False):
            root = Path(sys.executable).resolve().parent
        else:
            root = Path(__file__).resolve().parents[2]
        _GRAPHRAG_ROOT = str(root / "graphrag")
    return _GRAPHRAG_ROOT


def _get_store():
    """Get or create the GraphRagStore singleton."""
    global _graphrag_store
    if _graphrag_store is None:
        from rag_kb.graphrag_search import GraphRagStore

        root = _get_graphrag_root()
        _graphrag_store = GraphRagStore(root)
        stats = _graphrag_store.get_stats()
        if stats.is_ready:
            logger.info(
                "GraphRAG store ready: %d entities, %d relationships, %d communities",
                stats.entity_count,
                stats.relationship_count,
                stats.community_count,
            )
        else:
            logger.info("GraphRAG store loaded but index not built yet")
    return _graphrag_store


# ── Tools ─────────────────────────────────────────────────────────────


@mcp.tool
async def zgh_search_graph(
    query: str,
    mode: str = "local",
    community_level: int = 1,
) -> str:
    """Cross-document reasoning and knowledge graph retrieval for complex queries.

    Uses the 智冠华 knowledge graph (GraphRAG) to answer queries that span
    multiple documents or require reasoning beyond a single passage.

    Use **local** mode when the question involves specific entities,
    parameters, or technical details:
    - "机芯供电电压是多少"
    - "云台定位精度"
    - "A818 支持哪些分辨率"

    Use **global** mode when the question involves overall themes,
    cross-document comparison, or summarization:
    - "文档整体讲了什么"
    - "涉及哪些技术领域"
    - "三个文档的共同主题是什么"

    For simple fact/parameter lookups, use ``zgh_search_docs`` instead —
    it is faster and more cost-effective.

    Note: This tool requires the GraphRAG index to be built first.
    If indexing has not been run, it will suggest using ``zgh_search_docs``.

    Args:
        query: Natural language query for graph-based retrieval.
        mode: ``"local"`` (entity-focused, default) or ``"global"``
            (theme-focused).
        community_level: Hierarchy level to search. 0=most granular
            details, higher=broader themes. Default: 1.

    Returns:
        Formatted answer generated from the knowledge graph.
    """
    store = _get_store()

    if mode == "global":
        return await store.search_global(
            query=query, community_level=community_level
        )
    return await store.search_local(
        query=query, community_level=community_level
    )


@mcp.tool
async def zgh_refresh_graphrag_index(
    method: str = "standard",
    incremental: bool = False,
    skip_preprocess: bool = True,
) -> str:
    """Rebuild the 智冠华 knowledge graph from indexed documents.

    Runs the full GraphRAG pipeline: entity extraction → graph construction
    → community detection → summaries.

    Call this after ``zgh_refresh_index`` when you also want to refresh
    the knowledge graph. Indexing may take several minutes depending on
    document volume.

    Args:
        method: Indexing method — ``"standard"`` (LLM-based, higher quality)
            or ``"fast"`` (NLP graph construction, rule-based). Default: standard.
        incremental: If true, run an incremental update instead of full
            rebuild. Only new/changed documents are processed.
        skip_preprocess: Skip DOCX preprocessing (e.g. if input files
            are already in place).

    Returns:
        Summary of indexing results (workflow status + output stats).
    """
    from rag_kb.graphrag_indexer import build_index as _build

    result = await _build(
        verbose=True,
        method=method,
        is_update_run=incremental,
        skip_preprocess=skip_preprocess,
    )
    return result


@mcp.tool
def zgh_get_graphrag_index_status() -> str:
    """Check whether the 智冠华 knowledge graph index is built and ready.

    Returns readiness status, output directory, and entity/relationship/
    community counts if built. If not ready, suggests building it.

    Returns:
        Status message with path info.
    """
    store = _get_store()
    stats = store.get_stats()
    root = _get_graphrag_root()

    lines = [
        "GraphRAG Index Status",
        f"  Ready:  {'✅ Yes' if stats.is_ready else '❌ No'}",
        f"  Root:   {root}",
        f"  Output: {root}/output/",
    ]

    if stats.is_ready:
        lines.append(f"  Entities:     {stats.entity_count}")
        lines.append(f"  Relationships:{stats.relationship_count}")
        lines.append(f"  Communities:  {stats.community_count}")
        lines.append(f"  Text Units:   {stats.text_unit_count}")
        lines.append(f"  Documents:    {stats.document_count}")
    else:
        lines.append("")
        lines.append("Call `zgh_refresh_graphrag_index` to build the index.")

    return "\n".join(lines)
