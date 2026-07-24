"""CLI wrapper: apply monkey-patch then run ``graphrag index``.

Usage::

    python mcp/graphrag/cli.py index [--root mcp/graphrag]
    python mcp/graphrag/cli.py update [--root mcp/graphrag]
    python mcp/graphrag/cli.py query "..." [--root mcp/graphrag]
"""
from __future__ import annotations

import sys
from pathlib import Path

# Add mcp/ to sys.path so rag_kb is importable
_mcp_dir = Path(__file__).resolve().parents[1]
if str(_mcp_dir) not in sys.path:
    sys.path.insert(0, str(_mcp_dir))

# Apply monkey-patch before graphrag CLI loads
from rag_kb.graphrag_patch import patch_community_reports
patch_community_reports()

# Run graphrag CLI
from graphrag.cli.main import app

if __name__ == "__main__":
    app()
