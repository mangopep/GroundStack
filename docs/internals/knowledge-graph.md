# Knowledge graph status

`init_db.sql` loads Apache AGE and creates a `rag_knowledge` graph. The schema includes structured KB and override tables, but the checked-in `src/stores/knowledge_graph.py` is empty. There is no graph vertex/edge model, extraction, entity resolution, source assertion provenance, conflict handling, query route, or graph test suite.

Before implementing graph retrieval, define entity keys, relation types, source assertion/version provenance, merge/conflict behavior, authorization filters, and a deletion strategy. Graph traversal complexity depends on graph shape and requested traversal depth; the repository has no measured query plan or graph size limits.
