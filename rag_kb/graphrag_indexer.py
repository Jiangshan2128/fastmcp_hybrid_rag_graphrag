"""One-shot GraphRAG indexing — preprocess + build_index + verify.

Preprocessing reuses the RAG pipeline (Pandoc → Markdown → header-split →
numbered-item-split → recursive-split) so GraphRAG chunking matches RAG chunking
exactly.  Each chunk becomes a separate file in ``input/``, and GraphRAG's own
token splitter is set to a no-op (very large chunk size).

Can run standalone::

    python -c "from rag_kb.graphrag_indexer import run; run()"

Or called from a MCP tool::

    from rag_kb.graphrag_indexer import build_index
    result = await build_index()
"""
from __future__ import annotations

import asyncio
import logging
import re
import shutil
from pathlib import Path

logger = logging.getLogger("rag_kb.graphrag_indexer")

_GRAPHRAG_ROOT = Path(__file__).resolve().parent.parent / "graphrag"


def _get_documents_dir() -> Path:
    """Return the configured documents directory (from .env or default)."""
    from rag_kb.config import RAGConfig
    return Path(RAGConfig().DOCUMENTS_PATH)


def preprocess() -> int:
    """Preprocess DOCX & Markdown → structure-aware chunks → input/.

    Uses the same pipeline as the RAG knowledge base:
    1. Load via ``loader.py`` (DOCX → Pandoc → Markdown; ``.md`` → raw text)
    2. MarkdownHeaderTextSplitter (h1→h4)
    3. Numbered-item-aware splitter (``1)`` / ``2)`` boundaries)
    4. RecursiveCharacterTextSplitter (Chinese-aware separators)
    5. Each chunk → separate ``.md`` file in ``input/``

    GraphRAG's own ``chunking.size`` is set large enough in ``settings.yaml``
    so it treats each file as one text unit (no secondary token split).
    """
    from rag_kb.config import RAGConfig
    from rag_kb.loader import load_file
    from rag_kb.splitter import split_documents

    input_dir = _GRAPHRAG_ROOT / "input"
    input_dir.mkdir(parents=True, exist_ok=True)

    # ── 1. Clear old pre-split files ──────────────────────────────────
    for f in input_dir.glob("*.md"):
        f.unlink()

    # ── 2. Build a RAGConfig that matches existing chunking ───────────
    config = RAGConfig()
    config.CHUNK_SIZE = 1000
    config.CHUNK_OVERLAP = 200

    # ── 3. Find DOCX & Markdown files ─────────────────────────────────
    doc_dir = _get_documents_dir()
    source_files = sorted(
        f for f in doc_dir.rglob("*")
        if f.is_file()
        and f.suffix.lower() in (".docx", ".md")
        and not f.name.startswith(("~$", "~", "."))
    )

    if not source_files:
        logger.warning("No DOCX/Markdown files found in %s", doc_dir)
        return 0

    docx_count = sum(1 for f in source_files if f.suffix.lower() == ".docx")
    md_count = sum(1 for f in source_files if f.suffix.lower() == ".md")
    logger.info(
        "Preprocessing %d file(s) (%d DOCX, %d Markdown) ...",
        len(source_files), docx_count, md_count,
    )
    total_chunks = 0

    for src_path in source_files:
        try:
            # Load via shared pipeline (DOCX → Pandoc → MD; .md → raw)
            docs = load_file(str(src_path))

            # Split via RAG splitter (header → numbered-item → recursive)
            chunks = split_documents(docs, config)

            # Write each chunk as a separate .md file
            for i, chunk in enumerate(chunks):
                safe_name = re.sub(r"[^\w一-鿿]", "_", src_path.stem)[:40]
                fname = f"{safe_name}_chunk_{i:04d}.md"
                fpath = input_dir / fname
                fpath.write_text(chunk.page_content, encoding="utf-8")

            total_chunks += len(chunks)
            logger.info("  %s → %d chunks", src_path.name, len(chunks))

        except Exception as e:
            logger.error("  %s failed: %s", src_path.name, e, exc_info=True)

    logger.info("Preprocess done: %d chunks → %s", total_chunks, input_dir)
    return total_chunks


async def build_index(
    verbose: bool = True,
    method: str = "standard",
    is_update_run: bool = False,
    skip_preprocess: bool = False,
) -> str:
    """Run full GraphRAG indexing pipeline.

    Args:
        verbose: Enable verbose logging.
        method: Indexing method — ``"standard"`` (LLM-based) or ``"fast"``
            (NLP graph construction + LLM summarization).
        is_update_run: Incremental update instead of full rebuild.
        skip_preprocess: Skip the preprocessing step.

    Returns:
        Human-readable result summary.
    """
    root = str(_GRAPHRAG_ROOT)

    if not skip_preprocess:
        preprocess()

    # Apply the community-report compatibility patch BEFORE the pipeline
    # starts. Without it, create_community_reports sends response_format
    # with a Pydantic model → litellm converts to {type: json_schema,
    # strict: true}, which DeepSeek/GLM and most non-OpenAI models reject.
    # The patch drops response_format and parses plain JSON instead.
    from rag_kb.graphrag_patch import patch_community_reports
    patched = patch_community_reports()
    logger.info(
        "CommunityReportsExtractor patch %s",
        "applied (plain JSON mode)" if patched else "NOT applied",
    )

    from graphrag.api import build_index as _graphrag_build_index
    from graphrag.config.load_config import load_config

    config = load_config(root_dir=root)

    logger.info(
        "Starting GraphRAG index (method=%s, update=%s) ...",
        method, is_update_run,
    )

    results = await _graphrag_build_index(
        config=config,
        method=method,
        is_update_run=is_update_run,
        verbose=verbose,
    )

    total = len(results)
    errors = [r for r in results if r.error]
    ok = [r for r in results if r.error is None]

    summary = f"GraphRAG index complete: {total} workflow(s)"
    if ok:
        names = ", ".join(r.workflow for r in ok)
        summary += f"\n  ✅ Done: {names}"
    if errors:
        for e in errors:
            summary += f"\n  ❌ {e.workflow}: {e.error}"

    output_dir = _GRAPHRAG_ROOT / "output"
    parquet_files = list(output_dir.glob("*.parquet")) if output_dir.exists() else []
    if parquet_files:
        import pandas as pd
        for pf in sorted(parquet_files):
            try:
                rows = len(pd.read_parquet(pf))
                summary += f"\n    {pf.name}: {rows} rows"
            except Exception:
                summary += f"\n    {pf.name}: (unreadable)"
    else:
        summary += "\n  ⚠️  No output parquet files found"

    logger.info(summary)
    return summary


def run() -> None:
    """CLI entry point."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
    )
    result = asyncio.run(build_index(verbose=True))
    print("\n" + result)


if __name__ == "__main__":
    run()
