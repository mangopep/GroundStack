# Evidence and verification

A citation is useful only if it identifies a source location that supports the adjacent claim. A future answer system should carry document version, page or section, chunk ID, and exact evidence text through retrieval and generation. It should report conflict and abstain when support is missing.

The current `src/answer/verifier.py` is empty and the API has no answer flow. `PageResult` and `ChunkResult` carry some provenance, but citation correctness and claim entailment have not been implemented or measured.
