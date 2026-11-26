# Introduction

## What is GroundStack?

GroundStack is an experimental system for turning PDF text into smaller records that a search index can find. The long-term goal is to answer questions using a person's documents while showing where the answer came from. Today, the repository primarily implements parsing, chunking, and keyword indexing.

## The basic idea, without jargon

Imagine a large technical manual. Searching the whole book for every question is slow and returns broad matches. A retrieval-augmented generation (RAG) system first finds relevant passages, then gives those passages to a language model to write an answer. The retrieval step supplies evidence; the model does not automatically know whether that evidence is correct.

GroundStack currently implements much of the document preparation and a BM25 text-search adapter. It does not yet connect retrieval to answer generation through an API.

## What exists now

- PDF page extraction with Docling and PyMuPDF fallback.
- Section-oriented chunks with page metadata and deterministic IDs.
- OpenSearch BM25 indexing, PostgreSQL structured-record storage, and MinIO document storage adapters.
- A filesystem watcher and an in-memory async task queue.
- A FastAPI process endpoint and a static UI preview.

## What does not exist yet

Embeddings, vector search, hybrid fusion, query decomposition, answer generation as an application flow, claim verification, citations in a response, authentication, tenant isolation, and coordinated deletion are not implemented. See the [status table](../project/implementation-status.md).

## Who this documentation is for

A newcomer can use the [repository tour](../development/repository-tour.md) and [ingestion walkthrough](../internals/ingestion-engine.md). Contributors can use the [coding standards](../development/coding-standards.md) and [test strategy](../quality/testing-strategy.md). Operators should read the [deployment caveats](../infrastructure/docker.md) before starting services.
