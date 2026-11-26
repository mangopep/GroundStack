# Embedding engine status

`src/embeddings/embedder.py` is empty. No text is embedded in ingestion, no vector dimension is configured, and no vector index exists. The model adapter should be a separate interface from the Ollama text-generation client, because embedding and generation have different models, inputs, performance, and versioning.

A safe implementation needs a pinned model ID/revision, normalization policy, batch size, dimension validation, retry/timeout behavior, and tests that compare stored dimensions and stable document/chunk provenance. It also needs a labeled retrieval corpus before model quality or speed is claimed.
