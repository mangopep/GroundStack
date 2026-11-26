# Local development

Use Python 3.11.5 or newer and run `make setup` to install the hash-locked development, ingestion, and documentation dependencies. Run `make lint`, `make typecheck`, `make security`, `make test`, and `make docs`. `make integration` creates a separate test stack with fake credentials, random loopback ports, and a uniquely named volume; it removes only that stack afterward. Do not use `make reset` unless you intend to delete all development Compose volumes.
