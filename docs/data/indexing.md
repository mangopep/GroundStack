# Indexing

Current indexing is lexical. The builder sends content-bearing chunks one at a time to `BM25Store.index_chunk(..., refresh=False)`. The store uses each deterministic chunk ID as the OpenSearch document ID. Identical chunk IDs overwrite; changed chunks can leave old records unless they are deleted by document ID first. The builder does not currently perform a complete reindex cleanup before adding new chunks.

The baseline indexing script deleted/recreated the index when it already existed. The recovery change makes initialization preserve the index; mapping drift remains, so page citations should not be relied on until the schema is reconciled.
