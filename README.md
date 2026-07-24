# AI Note MCP Server

RAG + GraphRAG knowledge base MCP server for AI Note.

## Quick Start

```bash
# Install dependencies
pip install -e .

# Copy and edit config
cp .env.example .env
# Edit .env with your API keys

# Run server (stdio transport, for MCP host)
python server.py

# Or via fastmcp CLI
fastmcp run server.py:mcp
```

## Directory Layout

```
©À©¤©¤ server.py                 ¡û FastMCP entry point
©À©¤©¤ rag_kb/                   ¡û Core RAG library
©¦   ©À©¤©¤ config.py             ¡û Configuration (pydantic-settings)
©¦   ©À©¤©¤ loader.py             ¡û DOCX/Markdown loading
©¦   ©À©¤©¤ splitter.py           ¡û Structure-aware text splitting
©¦   ©À©¤©¤ embeddings.py         ¡û Embedding providers
©¦   ©À©¤©¤ qdrant_store.py       ¡û Qdrant vector store
©¦   ©À©¤©¤ indexer.py            ¡û Document indexing pipeline
©¦   ©À©¤©¤ retriever.py          ¡û Retrieval (hybrid dense+sparse)
©¦   ©À©¤©¤ graphrag_store.py     ¡û GraphRAG knowledge graph query
©¦   ©À©¤©¤ graphrag_indexer.py   ¡û GraphRAG indexing pipeline
©¦   ©¸©¤©¤ tools/                ¡û MCP tool definitions
©À©¤©¤ graphrag/                 ¡û GraphRAG project (settings.yaml + output)
©¦   ©À©¤©¤ settings.yaml
©¦   ©¸©¤©¤ prompts/
©À©¤©¤ knowledge_base/
©¦   ©À©¤©¤ documents/            ¡û Drop DOCX files here
©¦   ©¸©¤©¤ qdrant_data/          ¡û Qdrant persistent storage (gitignored)
©¸©¤©¤ pyproject.toml
```

## MCP Tools

| Tool | Description |
|------|-------------|
| `search_docs` | Semantic vector search for documentation |
| `get_document` | Read a full document by path |
| `list_docs` | List all indexed documents |
| `refresh_index` | Re-index the documents directory |
| `get_doc_stats` | View knowledge base statistics |
| `search_graph` | GraphRAG knowledge graph search (local/global) |
| `refresh_graphrag_index` | Rebuild GraphRAG knowledge graph |
| `get_graphrag_index_status` | Check GraphRAG index readiness |
