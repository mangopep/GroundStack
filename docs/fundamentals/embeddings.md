# Embeddings

An embedding is a list of numbers produced from text by an embedding model. Texts with related meanings may have nearby vectors. A vector index can use those numbers to find semantically similar passages even when words differ.

GroundStack's `src/embeddings/embedder.py` is empty. No vectors are produced or stored by the current ingestion path. The Ollama client in `src/llm/client.py` generates text; that is a different operation from embedding. Choosing an embedding model, vector dimension, versioning policy, and compatible index is future work and needs a retrieval evaluation set.
