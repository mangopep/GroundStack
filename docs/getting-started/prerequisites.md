# Prerequisites

## Python work

- Python 3.11.5 or newer. The lock excludes vulnerable dependency resolutions on earlier 3.11 patch releases. The checked-in application requirements include native document/OCR and ML dependencies, so a complete install can use substantial disk and memory.
- macOS or Linux. Windows/WSL is not covered by this repository's executed test evidence.
- A virtual environment. `make setup` installs the checked-in hash locks for application, development, and docs tools.

## Service-backed ingestion

The current ingestion pipeline expects PostgreSQL, OpenSearch, and MinIO. Docker Compose also defines Redis and Langfuse. Ollama is installed on the host by the startup script, not as a Compose service.

Before running Compose, inspect `.env.example` and create an ignored `.env` only if you do not already have one. Compose requires Postgres, MinIO, and Langfuse secrets. Do not replace an existing `.env` blindly.

## Hardware caveat

This audit host reported 16 GiB RAM, not the requested 8 GiB M4 profile. OpenSearch was near its configured 1 GiB cap and disk availability was low. The 8 GiB profile remains **NOT TESTED**. A single Ollama model's size does not represent total system memory use.
