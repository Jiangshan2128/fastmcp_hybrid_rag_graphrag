"""FastMCP server entry point — thin bootstrap.

Pulls the shared ``mcp`` instance from the ``mcp_server`` package.
Importing ``mcp_server`` registers all ``@mcp.tool`` handlers, so this
file stays free of tool definitions.

Start the server::

    # Via Python (stdio transport, default):
    python server.py

    # Via FastMCP CLI (stdio):
    fastmcp run server.py:mcp

    # Via FastMCP CLI (HTTP on port 9000):
    fastmcp run server.py:mcp --transport http --port 9000

Register as a local MCP server in ``.mcp.json``::

    {
      "mcpServers": {
        "zhiguanhua-kb": {
          "command": ".venv\\\\Scripts\\\\python.exe",
          "args": ["-u", "server.py"]
        }
      }
    }

Package layout
==============
.. code-block:: text

    mcp_server/                 — MCP application layer (sibling of rag_kb)
    ├── __init__.py             — re-exports mcp, registers tool modules
    ├── instance.py             — mcp = FastMCP(...) + lifespan
    ├── runtime.py              — retriever singleton, background init
    └── tools/                  — @mcp.tool handlers
        ├── search.py           — zgh_search_docs, zgh_get_document, zgh_list_docs
        ├── index.py            — zgh_refresh_index, zgh_get_doc_stats
        └── graphrag_tools.py   — zgh_search_graph, ...
    rag_kb/                     — pure RAG domain (no FastMCP imports)
"""

from __future__ import annotations

import logging

# ── Logging -----------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
)
logger = logging.getLogger("server")

# Importing mcp_server registers all @mcp.tool handlers on the instance.
from mcp_server import mcp  # noqa: F401 — registers tools on import

# =====================================================================
# Entry Point
# =====================================================================

if __name__ == "__main__":
    logger.info("Starting 智冠华 Internal Knowledge Base MCP server...")
    mcp.run()
