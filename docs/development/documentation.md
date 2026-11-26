# Documentation workflow

The docs portal uses Zensical and `mkdocs.yml` for its compatible configuration. Install `requirements-docs.txt` in the project virtual environment and build with:

```bash
.venv/bin/zensical build --strict
```

Preview with `.venv/bin/zensical serve`. The CI workflow builds on documentation changes and deploys only from `main`. Cross-links should be relative to files under `docs/`; source code links should point to concrete paths/line numbers and explain whether they are current or proposed.

The GitHub Pages site is currently disabled. The workflow is source configuration only; it does not modify repository Pages settings. A Pages setting approval is still needed before publication.
