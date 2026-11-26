# ADR 0001: Modular Python baseline

- Status: accepted for the current experimental codebase
- Date: 2026-11-26

## Context

The repository is Python 3.11+, with modules for ingestion, stores, workers, and an API. A wholesale rewrite would risk losing existing parser and chunking work.

## Decision

Retain the existing modular Python baseline while documenting its actual boundaries. New use cases should depend on typed ports and adapters; avoid adding an orchestration framework without a demonstrated need.

## Alternatives

A framework-centric rewrite, separate microservices, or a no-code workflow could be considered later. None is justified by the current implementation scale or evidence.

## Consequences

Preserves current code and permits incremental vertical slices. Existing module boundaries are not yet consistently enforced, and the live API remains incomplete.
