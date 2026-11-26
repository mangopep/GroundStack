# What is retrieval-augmented generation?

Retrieval-augmented generation, or RAG, is a pattern with two jobs:

1. **Retrieve:** find source passages likely to answer a question.
2. **Generate:** ask a language model to compose a response using those passages.

The model can still be wrong, and search can miss relevant sources. A dependable system needs evaluation, source attribution, permission filtering, and a way to say “the evidence is insufficient.”

GroundStack has PDF parsing and BM25 indexing components, but it does not yet implement the two-stage query path as a connected application. Its name and goal are not evidence that an answer is grounded.
