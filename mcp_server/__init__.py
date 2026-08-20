"""MCP application layer for the knowledge base server.

Sibling of ``rag_kb`` (the pure domain layer) — not a subpackage of it::

    mcp_server/     — MCP app layer (FastMCP instance + @mcp.tool handlers)
    rag_kb/         — pure RAG domain logic (no FastMCP imports)

Importing this package registers every tool on the shared ``mcp``
instance, so both ``fastmcp run mcp_server:mcp`` and ``from mcp_server
import mcp`` work.
"""

from mcp_server.instance import mcp
from mcp_server import tools  # noqa: F401 — registers @mcp.tool handlers

__all__ = ["mcp"]
