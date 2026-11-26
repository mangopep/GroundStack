# GroundStack engineering documentation

GroundStack is an experimental document-ingestion and lexical-search repository. This portal is a map of what the source code does today and what remains proposed. Start with the [current-state report](project/current-state.md); it distinguishes tested behavior from historical commit claims and planned work.

<div class="grid cards" markdown>

-   🧭 **Understand the project**

    ---

    Read the [introduction](getting-started/introduction.md), then the [repository tour](development/repository-tour.md).

-   📄 **Follow a document**

    ---

    Trace the current [PDF ingestion path](internals/ingestion-engine.md) and [chunker](internals/chunking-engine.md).

-   🔎 **Understand search status**

    ---

    Learn what [BM25 currently does](fundamentals/keyword-search.md) and why a full query pipeline is still missing.

-   🛡️ **Review readiness**

    ---

    See the [implementation matrix](project/implementation-status.md), the [ForgeStack comparison](project/forgestack-comparison.md), [technical debt](project/technical-debt.md), and [release gates](quality/release-checklist.md).

</div>

## Read this before relying on the system

The repository does not yet provide an end-to-end question-answer API. Several directories are empty placeholders. The local test suite covers meaningful ingestion/store code, but its baseline skips MinIO integration and does not validate a complete live ingestion/query flow. No production readiness, citation accuracy, retrieval quality, or 8 GiB performance claim is made.

## Where to go next

- [Set up a local development environment](getting-started/installation.md)
- [See the observed project history](project/development-history.md)
- [Read the current HLD](architecture/hld/system-context.md)
- [Read the current ingestion LLD](architecture/lld/ingestion.md)
- [Review test evidence](quality/testing-strategy.md)
- [Review open risks](project/technical-debt.md)

## Site and source

The documentation source is Markdown in this repository and the site is built with Zensical using the compatible `mkdocs.yml` format. Site builds do not change GitHub Pages settings. The project currently has no published release; `0.1.0` in Python metadata is a development version.
