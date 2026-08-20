"""MCP tool handlers, grouped by domain.

Each module registers its tools on the shared FastMCP instance at import
time (via ``@mcp.tool``).  Import this package to register all tools.

.. code-block:: text

    mcp_server/tools/
    ├── __init__.py        — imports tool modules for registration
    ├── search.py          — zgh_search_docs, zgh_get_document, zgh_list_docs
    ├── index.py           — zgh_refresh_index, zgh_get_doc_stats
    └── graphrag_tools.py  — zgh_search_graph, zgh_refresh_graphrag_index, ...
"""

from mcp_server.tools import search  # noqa: F401 — registers search tools
from mcp_server.tools import index  # noqa: F401 — registers index tools
from mcp_server.tools import graphrag_tools  # noqa: F401 — registers graphrag tools
