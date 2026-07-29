"""FastMCP server — exposes RAG knowledge base tools via MCP protocol.

Start the server::

    # Via Python (stdio transport, default):
    python mcp/server.py

    # Via FastMCP CLI (stdio):
    fastmcp run mcp/server.py:mcp

    # Via FastMCP CLI (HTTP on port 9000):
    fastmcp run mcp/server.py:mcp --transport http --port 9000

Register as a local MCP server in ``mcp_servers.json``::

    {
      "mcpServers": {
        "zhiguanhua-kb": {
          "enabled": true,
          "type": "stdio",
          "command": "python",
          "args": ["mcp/server.py"],
          "description": "智冠华 Internal Knowledge Base — RAG + GraphRAG query service"
        }
      }
    }

Tools
=====
Search & Retrieval
    zgh_search_docs       — Search product specs, parameters, SDK docs
    zgh_get_document      — Read a full internal document by path
    zgh_list_docs         — List all indexed internal documents
    zgh_get_usage_guide   — Get usage guide (start here)

Index Management
    zgh_refresh_index — Manually trigger a re-index of the docs directory
    zgh_get_doc_stats — View knowledge base statistics

Tool Modules
============
.. code-block:: text

    mcp/rag_kb/tools/
    ├── __init__.py     — mcp instance, retriever singleton, lifecycle hooks
    ├── search.py       — zgh_search_docs, zgh_get_document, zgh_list_docs
    └── index.py        — zgh_refresh_index, zgh_get_doc_stats

Design notes
============
- Indexing happens automatically on server startup (``AUTO_INDEX_ON_START=true``).
- Documents live in ``knowledge_base/documents/`` — just drop files there.
- Use ``zgh_refresh_index`` to re-index after adding files (or enable WATCH_ENABLED).
- The vector store backend is swappable via ``VECTOR_STORE_BACKEND`` config.
"""

from __future__ import annotations

import logging
import sys
from pathlib import Path

# Ensure the mcp/ directory is on sys.path so that ``rag_kb`` is importable
# when running ``python mcp/server.py`` from the project root.
_mcp_dir = str(Path(__file__).resolve().parent)
if _mcp_dir not in sys.path:
    sys.path.insert(0, _mcp_dir)

# -- Logging -----------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
)
logger = logging.getLogger("mcp.server")

# ── Import tool modules to register @mcp.tool decorators ─────────────
# Order matters: __init__.py creates the mcp instance, then search.py
# and index.py decorate it.  Lifecycle hooks live in __init__.py.
from rag_kb.tools import mcp  # noqa: F401 — needed for fastmcp run
from rag_kb.tools import search  # noqa: F401 — registers search tools
from rag_kb.tools import index  # noqa: F401 — registers index tools
from rag_kb.tools import graphrag_tools  # noqa: F401 — registers graphrag tools

logger.info("Registered tool modules: search, index, graphrag")

# =====================================================================
# Entry Point
# =====================================================================

if __name__ == "__main__":
    logger.info("Starting 智冠华 Internal Knowledge Base MCP server...")
    mcp.run()
