# ADR 0003: Documentation site platform

- Status: Accepted for the documentation portal
- Date: 2026-11-26

## Context

The repository had Markdown documentation but no site build configuration. The requested portal needs responsive navigation, light and dark palettes, search, Mermaid diagrams, syntax highlighting, and a GitHub Pages workflow. Material for MkDocs is the familiar Python choice, but its maintainers document an end-of-life date of May 5, 2027 and identify Zensical as its successor. Zensical 0.1.3 is a beta release, so its maturity is a trade-off that should be revisited before the first long-lived release.

## Decision

Use Zensical 0.1.3 with the compatible `mkdocs.yml` configuration format. Pin the docs toolchain in a hash-locked requirements file. Build in strict mode on pull requests and deploy from `main` through GitHub Actions Pages artifacts when `PAGES_DEPLOYMENT_ENABLED=true` is set.

## Alternatives considered

- **Material for MkDocs:** mature and feature-rich, but has a published 2027 maintenance end date.
- **Sphinx:** established Python documentation tooling, but the current content and Mermaid examples are Markdown-first and do not need Python API autodoc.
- **Custom frontend:** more visual freedom, but adds an unnecessary build and maintenance surface for a documentation portal.

## Consequences

- Zensical supplies search, themes, navigation, code copy, and Mermaid integration without custom JavaScript.
- Existing Markdown and MkDocs-style configuration remain relatively portable.
- The docs dependency is separate from application runtime dependencies.
- Because Pages currently returns no configured site, deployment requires the repository owner to set Pages build and deployment source to GitHub Actions, then set `PAGES_DEPLOYMENT_ENABLED=true`. This ADR and workflow do not change repository settings.

## References

- [Material for MkDocs maintenance notice](https://squidfunk.github.io/mkdocs-material/)
- [Zensical MkDocs compatibility](https://zensical.org/docs/compatibility/mkdocs/plugins/)
- [Zensical diagram support](https://zensical.org/docs/authoring/diagrams/)
