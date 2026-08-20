# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec — onedir bundle for the MCP Knowledge Base Server.

Usage::

    pyinstaller server.spec

Produces ``dist/server/`` — copy the whole directory to the target machine.
The target machine needs **no** Python installation.

On the target machine, create ``.env`` from ``.env.example`` and a
``knowledge_base/documents/`` directory with your documents.
"""

from pathlib import Path

ROOT = Path.cwd()
_VENV_SITE = ROOT / ".venv" / "Lib" / "site-packages"

# Packages pulled in by optional dependencies (FlagEmbedding → torch etc.)
# that are NOT needed by the default qwen/DashScope code path.
_EXCLUDES = [
    # Heavy ML frameworks — only needed by BGE-M3 / HuggingFace providers
    "torch",
    "torchvision",
    "transformers",
    "bitsandbytes",
    "sentence_transformers",
    "langchain_huggingface",
    "FlagEmbedding",
    # NLP libs — not used
    "spacy",
    "thinc",
    "nltk",
    # Scientific / ML — heavy, not used by qwen code path
    "scipy",
    "scipy.special",
    "scipy.linalg",
    "scipy.spatial",
    "scipy.stats",
    "scipy.signal",
    "sklearn",
    "sklearn.metrics",
    "sklearn.cluster",
    "sklearn.neighbors",
    "sklearn.ensemble",
    "sklearn.tree",
    "sklearn.linear_model",
    "sklearn.preprocessing",
    "sklearn.utils",
    # TF — not used
    "tensorflow",
    "tensorboard",
    # GUI / media — not needed for a CLI/MCP server
    "tkinter",
    "PyQt5",
    "PySide6",
    "PIL",
    "matplotlib",
    "plotly",
    # Dev / debug tools
    "jupyter",
    "jedi",
    "IPython",
    "pytest",
    "sentry_sdk",
    # Datasets — not used
    "datasets",
    # Audio — not used
    "pydub",
    "zmq",
    # Not used at query time
    "onnxruntime",
    "onnx",
]

a = Analysis(
    ["server.py"],
    pathex=[],
    binaries=[],
    datas=[
        (str(ROOT / ".env.example"), "."),
        (str(ROOT / "graphrag" / "settings.yaml"), "graphrag"),
        (str(ROOT / "graphrag" / "prompts"), "graphrag/prompts"),
        # Package metadata for importlib.metadata.version()
        (str(_VENV_SITE / "fastmcp-3.4.5.dist-info"), "fastmcp-3.4.5.dist-info"),
        (str(_VENV_SITE / "fastmcp_slim-3.4.5.dist-info"), "fastmcp_slim-3.4.5.dist-info"),
    ],
    hiddenimports=[
        "rag_kb.qdrant_store",
        "rag_kb.graphrag_search",
        "rag_kb.graphrag_indexer",
        "mcp_server.tools.search",
        "mcp_server.tools.index",
        "mcp_server.tools.graphrag_tools",
        "langchain_core.documents",
        "langchain_core.embeddings",
        "langchain_text_splitters",
        "langchain_community.document_loaders",
        "qdrant_client.local.qdrant_local",
    ],
    # Package metadata needed at runtime (importlib.metadata.version)
    copy_metadata=[
        "fastmcp",
        "pydantic",
        "pydantic_settings",
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=_EXCLUDES,
    noarchive=False,
)
pyz = PYZ(a.pure)

app_exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name="server",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
coll = COLLECT(
    app_exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name="server",
)
# Clean up the residual dist/server.exe left by standalone EXE step;
# the real entry point is dist/server/server.exe inside the onedir bundle.
import os as _os, pathlib as _pathlib
try:
    _f = _pathlib.Path("dist") / "server.exe"
    if _f.is_file():
        _os.remove(_f)
        print("  ✓ cleaned up dist/server.exe")
except Exception:
    pass
