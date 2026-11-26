# LLD: Query path (not implemented)

This document records the source-level absence and defines only the narrow boundary needed for future work.

## Current interfaces

- `BM25Store.search(query: str, top_k: int = 10) -> list[dict]` in `src/stores/bm25.py` calls OpenSearch and formats hits.
- `LLMClient` in `src/llm/client.py` wraps Ollama generation/streaming/structured output.
- Query schemas, routers, retrieval gateway, reranker, context builder, answer generator, verifier, and API route modules are zero-byte files.

There is no caller connecting those two implemented adapters. No payload, error format, citation contract, or query latency can be truthfully documented as product behavior.

## Proposed minimal contract

A future `QueryUseCase` should accept an authorized collection/document scope and query text, return answer text plus cited source-version/page/chunk references and an explicit abstention state. Search must apply authorization filters in the index. Prompt text from source passages must be treated as untrusted data. The design requires tests and a quality corpus before a model is connected.
