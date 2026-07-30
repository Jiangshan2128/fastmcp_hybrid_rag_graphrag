# AGENTS.md

This file provides guidance to Agent when working with code in this repository.

## Commands

```bash
# One-click MCP Inspector (debugging UI) — kills orphans first
.\inspector.bat

# Install
pip install -e .

# Install dev dependencies
pip install -e ".[dev]"

# Run tests
pytest

# Run a single test
pytest tests/test_foo.py -k test_bar

# GraphRAG index build (via official CLI, after preprocessing)
graphrag index --root graphrag
graphrag index --root graphrag --verbose

# GraphRAG incremental update
graphrag update --root graphrag
```

## Environment Setup

- Copy `.env.example` → `.env` and fill in API keys
- Default embedding provider: Qwen DashScope (`text-embedding-v4`) — supports dense + sparse hybrid in one API call
- GraphRAG requires `DEEPSEEK_API_KEY` for LLM extraction and search
- `AUTO_INDEX_ON_START=true` by default; set to `false` for faster startup during development
- `.env` is loaded from project root by `rag_kb/config.py`

## Project Architecture

### Two-tier RAG: Vector + Knowledge Graph

```
Tool Layer (MCP)                          rag_kb/tools/
  ├── zgh_search_docs        Hybrid vector search (dense + sparse)
  ├── zgh_get_document       Full document reader
  ├── zgh_list_docs          List indexed documents
  ├── zgh_search_graph       GraphRAG knowledge graph search (local/global)
  ├── zgh_refresh_index      Re-index documents
  ├── zgh_get_doc_stats      Knowledge base statistics
  ├── zgh_refresh_graphrag_index  Rebuild knowledge graph
  └── zgh_get_graphrag_index_status  GraphRAG readiness check

RAG Layer                              rag_kb/
  ├── retriever.py          RAGRetriever — orchestrates embeddings + store + index
  ├── embeddings.py         Provider abstraction: Qwen, BGE-M3, OpenAI, HuggingFace
  ├── qdrant_store.py       Qdrant local mode — dense + sparse named vectors + RRF
  ├── indexer.py            Content-hash-cached incremental indexing
  ├── loader.py             DOCX (Pandoc/docx2txt), Markdown, PDF, CSV, HTML
  ├── splitter.py           Structure-aware chunking (Markdown headers + numbered items)
  ├── interfaces.py         Abstract interfaces (VectorStoreInterface, IndexedDoc, SearchResult)
  ├── vector_store_factory.py   Backend selection by config
  ├── watcher.py            File system watcher for live updates
  ├── graphrag_search.py    GraphRagStore — loads Parquet, delegates to graphrag.api
  ├── graphrag_indexer.py   GraphRAG index pipeline: DOCX → Markdown → chunks → input/
  └── config.py             Pydantic-settings config from .env

Config & data              root/
  ├── server.py            FastMCP entry point — imports tool modules
  ├── .env                 API keys and settings (gitignored)
  ├── .mcp.json            Claude Code MCP server registration
  ├── knowledge_base/
  │   ├── documents/       Input documents (.docx, .md)
  │   └── qdrant_data/     Qdrant persistent storage
  └── graphrag/
      ├── settings.yaml    GraphRAG pipeline config
      ├── prompts/         Custom prompt templates (extraction, search, community report)
      └── output/          Parquet files (entities, relationships, communities, etc.)
```

### Key Flow: Hybrid Search

```
Query → DashScope text-embedding-v4 → {dense_vector, sparse_weights}
  ─→ Qdrant prefetch lane 1 (dense named vector)
  ─→ Qdrant prefetch lane 2 (sparse named vector)
  ─→ Reciprocal Rank Fusion (RRF, k=60) → top-k results
```

### Key Flow: GraphRAG

```
GraphRagStore lazily loads Parquet from graphrag/output/ on first search.
zgh_search_graph calls graphrag.api.local_search or graphrag.api.global_search.
Results are stripped of [Data: ...] citation markers before returning.
```

## Critical Design Constraints

### Non-blocking server initialization

**The server MUST NOT block lifespan yield** — MCP hosts (Inspector, Claude Code) have strict timeouts waiting for Initialize response. The `rag_kb/tools/__init__.py` lifecycle:

1. Lifespan calls `_start_background_init()` — starts a daemon thread, yields immediately
2. First tool call checks `threading.Event.is_set()` — if init not done, raises `RetrieverNotReadyError`
3. Tool functions catch this and return `RETRIEVER_NOT_READY` ("【知识库正在初始化】...")
4. Never call `event.wait()` — it blocks the MCP request handler

### Qdrant file lock

- Qdrant local mode uses OS-level exclusive file locks (`portalocker` / `msvcrt.locking`)
- **Only one Python process** can access `knowledge_base/qdrant_data/` at a time
- Kill orphaned processes with `taskkill /f /im python.exe` before re-starting
- `inspector.bat` handles this automatically

### GraphRAG compatibility

- Microsoft GraphRAG uses JSON `strict: true` schema mode by default — **incompatible with DeepSeek and most non-OpenAI LLMs**
- The project was using `rag_kb/graphrag_patch.py` (now removed — kept as backup) to monkey-patch community report extractors to skip strict mode
- When upgrading GraphRAG, check `community_report` extraction for `response_format` settings
- Custom prompts live in `graphrag/prompts/` — tuned for Chinese technical documents with specific entity types (`device`, `specification`, `parameter`, `interface`, `component`)

### Content-hash caching

- `index_documents()` uses `knowledge_base/documents/.index_cache.json` — MD5 hashes per file
- Only changed/new files are re-processed on subsequent runs
- Full re-index with `zgh_refresh_index(full_rebuild=true)` or by deleting `.index_cache.json`

## Quick Reference

- Tools are named with `zgh_` prefix (智冠华), registered via `@mcp.tool` decorators in `rag_kb/tools/`
- All vector store backends must implement `VectorStoreInterface` in `rag_kb/interfaces.py`
- New embedding providers go in `rag_kb/embeddings.py` — implement LangChain's `Embeddings` interface
- GraphRagStore is **lazy-loaded**: parquet loaded on first `search_local()` / `search_global()` call, not at init
- The `server.py` entry point imports tool modules for side-effect registration; order matters (`__init__.py` first for the `mcp` instance)
