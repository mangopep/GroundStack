# Vector search

Vector search ranks records by distance or similarity between query and document embeddings. Common indexes trade memory, build time, and recall for faster approximate search.

GroundStack has no active vector-search implementation: `src/stores/vector.py` is empty and Compose does not enable pgvector. Do not infer vector support from the project's RAG goal or from the `psycopg` dependency.
