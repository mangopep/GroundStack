# Knowledge graphs

A knowledge graph represents entities (things) and relations between them, such as “service A depends on database B.” It can help answer relationship questions when those edges are extracted with evidence and kept current.

Compose uses an Apache AGE PostgreSQL image and `init_db.sql` creates a graph namespace. `src/stores/knowledge_graph.py` is empty, and there is no entity extraction, resolution, graph write, or authorized graph retrieval path. Graph support is therefore infrastructure scaffolding only.
