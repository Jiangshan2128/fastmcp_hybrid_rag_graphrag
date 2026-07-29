<div align="center">

# AI Note — MCP Knowledge Base Server 🧠🔍

**A learn-by-building RAG knowledge base powered by FastMCP, hybrid vector search, and GraphRAG**

[![Python](https://img.shields.io/badge/Python-3.13+-blue?logo=python&logoColor=white)](https://www.python.org/)
[![FastMCP](https://img.shields.io/badge/FastMCP-3.0-purple)](https://github.com/jlowin/fastmcp)
[![License](https://img.shields.io/badge/License-MIT-green)](LICENSE)
[![PRs Welcome](https://img.shields.io/badge/PRs-welcome-brightgreen)](https://github.com/Jiangshan2128/ainote-mcp-server/pulls)

</div>

> 🎯 **Goal**: A practical, well-documented MCP (Model Context Protocol) server that turns local documents into an AI-searchable knowledge base — built as an educational project for learning Retrieval-Augmented Generation (RAG) techniques.

---

## ✨ Features

| Feature | Description |
|---------|-------------|
| 🔎 **Hybrid Search** | Dense (semantic) + Sparse (lexical) vector search fused via **Reciprocal Rank Fusion (RRF)** — gets you the best of both worlds |
| 🕸️ **GraphRAG** | Knowledge-graph powered retrieval for cross-document reasoning and global theme analysis (powered by Microsoft GraphRAG) |
| 🔌 **MCP Protocol** | Exposes all tools via the [Model Context Protocol](https://modelcontextprotocol.io/) — pluggable into any MCP-compatible AI client |
| 📄 **Multi-format** | Supports **DOCX** and **Markdown** documents out of the box |
| 🧩 **Pluggable Embeddings** | Drop-in support for Qwen (DashScope), BGE-M3 (local), OpenAI-compatible APIs, and HuggingFace local models |
| 🏠 **Local-First** | Qdrant runs in embedded mode — no server, no Docker, no cloud database needed |
| 🔄 **Auto-Indexing** | Automatically indexes documents on startup; manual re-index via tool |
| ⚡ **FastMCP** | Modern async Python MCP framework with lifespan management and clean tool decoration |

## 🧠 Why This Project?

This project is designed as **a learn-by-building RAG implementation**. Each component is intentionally modular and well-documented:

- **`rag_kb/embeddings.py`** — See how different embedding providers are abstracted behind a common interface
- **`rag_kb/qdrant_store.py`** — Trace through a complete hybrid search implementation (dense → sparse → RRF fusion)
- **`rag_kb/retriever.py`** — Understand the full RAG lifecycle: index → search → format
- **`rag_kb/graphrag_store.py`** — Explore how knowledge graphs enhance retrieval beyond vector similarity
- **`rag_kb/tools/`** — Learn how MCP tools are defined with FastMCP decorators

Whether you're new to RAG or looking for a reference project with **real production patterns** (vector store interface abstraction, hybrid search, content-hash caching, structure-aware chunking), this is a solid starting point.

## 🏗️ Architecture

```
┌──────────────────────────────────────────────────┐
│                  MCP Client                       │
│         (Claude Code / Cursor / any MCP host)     │
└──────────────────────┬───────────────────────────┘
                       │ MCP Protocol (stdio/HTTP)
┌──────────────────────▼───────────────────────────┐
│              FastMCP Server (server.py)            │
│  ┌─────────────────────────────────────────────┐  │
│  │              Tool Layer                       │  │
│  │  zgh_search_docs  zgh_search_graph           │  │
│  │  zgh_get_document zgh_list_docs              │  │
│  │  zgh_refresh_index zgh_get_doc_stats         │  │
│  └──────────────────┬──────────────────────────┘  │
└─────────────────────┼────────────────────────────┘
                      │
┌─────────────────────▼────────────────────────────┐
│              RAG Retriever (rag_kb/)              │
│                                                   │
│  ┌─────────────┐  ┌────────────┐  ┌────────────┐ │
│  │  Embeddings  │  │  Vector    │  │  GraphRAG  │ │
│  │  Factory     │──▶  Store     │  │  Store     │ │
│  │              │  │  (Qdrant)  │  │  (Parquet) │ │
│  │  • Qwen      │  │            │  │            │ │
│  │  • BGE-M3    │  │  Dense +   │  │  Entity    │ │
│  │  • OpenAI    │  │  Sparse    │  │  Relations │ │
│  │  • HF        │  │    ↓       │  │  Community │ │
│  │              │  │  RRF Fusion│  │  Summaries │ │
│  └──────────────┘  └────────────┘  └────────────┘ │
└───────────────────────────────────────────────────┘
```

### Search Flow: Hybrid (Dense + Sparse)

```
User Query: "设备供电电压是多少？"
         │
         ▼
 ┌──────────────────┐     ┌───────────────────┐
 │  Dense Encoding  │     │  Sparse Encoding  │
 │  (semantic)      │     │  (lexical/BM25)   │
 │  Qwen / BGE-M3   │     │  Qwen / BGE-M3    │
 └────────┬─────────┘     └─────────┬──────────┘
          ▼                         ▼
 ┌──────────────────┐     ┌───────────────────┐
 │  Dense Prefetch  │     │  Sparse Prefetch  │
 │  (named vector)  │     │  (named vector)   │
 └────────┬─────────┘     └─────────┬──────────┘
          │            ┌────────────┘
          ▼            ▼
 ┌──────────────────────────┐
 │  Reciprocal Rank Fusion  │  ← Combines & re-ranks
 │         (RRF)            │
 └────────────┬─────────────┘
              ▼
      Top-K results returned
```

## 🚀 Quick Start

### 1. Prerequisites

- **Python 3.13+**
- An API key for the embedding provider of your choice (see [Configuration](#configuration))

### 2. Setup

```bash
# Clone the repository
git clone https://github.com/Jiangshan2128/ainote-mcp-server.git
cd ainote-mcp-server

# Create and activate virtual environment
python -m venv .venv
source .venv/bin/activate       # Linux/macOS
.venv\Scripts\activate          # Windows

# Install the package and all dependencies
pip install -e .

# Copy example config and edit with your API keys
cp .env.example .env
```

### 3. Add Documents

Drop `.docx` or `.md` files into the `knowledge_base/documents/` directory:

```bash
knowledge_base/documents/
├── 设备SDK接口需求文档.v1.3.docx
├── A818产品规格说明.docx
├── 技术白皮书.md
└── ...
```

### 4. Run the Server

```bash
# Start the MCP server (stdio mode)
python server.py
```

The server will:
1. Load your configuration from `.env`
2. Initialize the embedding model
3. Index all documents into the Qdrant vector store
4. Wait for MCP tool calls from the client

### 5. Configure Your MCP Client

Add the server to your MCP client's configuration:

```json
{
  "mcpServers": {
    "ainote-kb": {
      "command": ".venv/bin/python",
      "args": ["-u", "server.py"],
      "cwd": "/path/to/ainote-mcp-server"
    }
  }
}
```

For **Claude Code**, this goes into `.mcp.json` or your local `settings.local.json`.

## 🔧 Configuration

All configuration is via environment variables in `.env`:

### Embedding Backend

| Variable | Description | Example |
|----------|-------------|---------|
| `EMBEDDING_PROVIDER` | Provider to use | `qwen` / `bge-m3` / `openai` / `huggingface` |
| `EMBEDDING_MODEL` | Model name | `text-embedding-v4` / `BAAI/bge-m3` / `text-embedding-3-small` |
| `EMBEDDING_API_KEY` | API key | `sk-xxx` |

**Provider-specific notes:**

- **`qwen`** (default): Uses Alibaba Cloud DashScope SDK. Supports **dense + sparse** hybrid in a single API call. Set `EMBEDDING_API_KEY` to your DashScope API key.
- **`bge-m3`**: Local BGE-M3 model via `FlagEmbedding` (~2 GB download on first use). No API key needed. Also supports **dense + sparse** hybrid.
- **`openai`**: Works with any OpenAI-compatible API (including GLM, Ollama, etc.). Dense-only.
- **`huggingface`**: Local HuggingFace model via `sentence-transformers`. Dense-only.

### Vector Store

| Variable | Description | Default |
|----------|-------------|---------|
| `QDRANT_PATH` | Qdrant data directory | `knowledge_base/qdrant_data` |
| `QDRANT_COLLECTION` | Collection name | `ai_note_knowledge` |
| `QDRANT_DISTANCE` | Distance metric | `cosine` |

### Document Processing

| Variable | Description | Default |
|----------|-------------|---------|
| `DOCUMENTS_PATH` | Where to find documents | `knowledge_base/documents` |
| `CHUNK_SIZE` | Text chunk size (chars) | `1000` |
| `CHUNK_OVERLAP` | Chunk overlap | `200` |
| `AUTO_INDEX_ON_START` | Auto-index on startup | `true` |
| `WATCH_ENABLED` | Watch for file changes | `false` |

## 🛠️ MCP Tools Reference

### Search & Retrieval

| Tool | Description | When to Use |
|------|-------------|-------------|
| `zgh_search_docs` | Hybrid vector search (dense + sparse → RRF) | Finding specific parameters, specs, interface definitions |
| `zgh_search_graph` | Knowledge graph search (local/global mode) | Cross-document reasoning, global summaries, multi-hop queries |
| `zgh_get_document` | Read a full document by path | When snippets aren't enough |
| `zgh_list_docs` | List all indexed documents | Understanding what's available |

### Index Management

| Tool | Description |
|------|-------------|
| `zgh_refresh_index` | Re-index documents (incremental or full) after adding/changing files |
| `zgh_get_doc_stats` | View knowledge base statistics (chunks, sources, backend) |
| `zgh_refresh_graphrag_index` | Rebuild GraphRAG knowledge graph |
| `zgh_get_graphrag_index_status` | Check GraphRAG index readiness |

## 📁 Project Structure

```
ainote-mcp-server/
├── server.py                 # FastMCP entry point
├── pyproject.toml            # Project config & dependencies
├── Dockerfile                # Container build
├── .env                      # Local configuration (gitignored)
├── .env.example              # Config template
│
├── rag_kb/                   # Core RAG library
│   ├── config.py             # Pydantic-settings config
│   ├── embeddings.py         # Embedding providers: Qwen, BGE-M3, OpenAI, HF
│   ├── loader.py             # DOCX/Markdown loading
│   ├── splitter.py           # Structure-aware text splitting
│   ├── indexer.py            # Document indexing pipeline
│   ├── retriever.py          # Search orchestration
│   ├── interfaces.py         # Abstract interfaces (VectorStoreInterface)
│   ├── qdrant_store.py       # Qdrant backend with hybrid search + RRF
│   ├── graphrag_store.py     # GraphRAG knowledge graph queries
│   ├── graphrag_indexer.py   # GraphRAG indexing pipeline
│   ├── vector_store_factory.py  # Backend factory
│   ├── watcher.py            # File system watcher
│   └── tools/                # MCP tool definitions
│       ├── __init__.py       # FastMCP instance, lifespan
│       ├── search.py         # zgh_search_docs, etc.
│       ├── index.py          # zgh_refresh_index, etc.
│       └── graphrag_tools.py # zgh_search_graph, etc.
│
├── knowledge_base/
│   ├── documents/            # Drop your .docx / .md files here
│   └── qdrant_data/          # Qdrant persistent storage (auto-created)
│
└── graphrag/                 # GraphRAG project directory
    ├── settings.yaml
    └── output/               # GraphRAG parquet output (auto-created)
```

## 💡 Learning Path

This project was built as a learning resource. Here's how to explore it:

| Step | File(s) | What You'll Learn |
|------|---------|-------------------|
| 1️⃣ | `server.py`, `rag_kb/tools/__init__.py` | How to set up a FastMCP server with lifespan |
| 2️⃣ | `rag_kb/embeddings.py` | Abstracting embedding providers behind a common interface |
| 3️⃣ | `rag_kb/interfaces.py` | Vector store interface design (backend-agnostic) |
| 4️⃣ | `rag_kb/qdrant_store.py` | **Hybrid search**: dense + sparse vectors with RRF fusion |
| 5️⃣ | `rag_kb/indexer.py`, `rag_kb/loader.py` | Document loading, chunking, content-hash caching |
| 6️⃣ | `rag_kb/retriever.py` | End-to-end RAG lifecycle orchestration |
| 7️⃣ | `rag_kb/graphrag_store.py` | Knowledge-graph-enhanced retrieval with GraphRAG |
| 8️⃣ | `rag_kb/vector_store_factory.py` | Factory pattern for swappable backends |

## 🐳 Docker

```bash
# Build
docker build -t ainote-mcp-server .

# Run (mount documents directory)
docker run -d --name ainote-mcp \
  -v /path/to/documents:/app/knowledge_base/documents \
  --env-file .env \
  ainote-mcp-server
```

## 🧪 Development

```bash
# Install dev dependencies
pip install -e ".[dev]"

# Run tests
pytest
```

## 🤝 Contributing

This is an educational project, and contributions are welcome! Here's how you can help:

- **Add a new vector store backend** — Implement `VectorStoreInterface` for Chroma, pgvector, Milvus, etc.
- **Add more embedding providers** — Jina AI, Cohere, Voyage, etc.
- **Improve chunking strategies** — Semantic splitting, agentic chunking
- **Add document formats** — PDF, HTML, plain text
- **Write tests** — Increase coverage
- **Improve documentation** — Fix typos, add examples, translate

See the [open issues](https://github.com/Jiangshan2128/ainote-mcp-server/issues) for ideas. Please open an issue first for significant changes.

## 📚 References

- [FastMCP Documentation](https://github.com/jlowin/fastmcp) — The Python MCP framework powering this project
- [Model Context Protocol](https://modelcontextprotocol.io/) — The protocol specification
- [Microsoft GraphRAG](https://github.com/microsoft/graphrag) — Knowledge graph generation & retrieval
- [Qdrant](https://qdrant.tech/) — Vector database with native sparse vector support
- [Reciprocal Rank Fusion](https://plg.uwaterloo.ca/~gvcormac/cormacksigir09-rrf.pdf) — The fusion algorithm used for hybrid search
- [LangChain](https://www.langchain.com/) — Embeddings interface & document loaders

## 📄 License

[MIT](LICENSE) © Jiangshan2128

---

<div align="center">
  <sub>Built with ❤️ for learning RAG, MCP, and modern AI engineering</sub>
  <br>
  <sub>⭐ Star this repo if you find it helpful! PRs and issues welcome.</sub>
</div>
