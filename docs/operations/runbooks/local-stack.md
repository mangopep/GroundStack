# Runbook: inspect the local stack

1. Read `.env.example` for required variable names; do not print or paste `.env` values.
2. Validate Compose interpolation: `docker compose config --quiet` (read-only).
3. Inspect current state: `docker compose ps` and `docker stats --no-stream`.
4. Inspect one service's logs: `docker compose logs --tail=100 <service>`.
5. The OpenSearch initializer is now create-only, but does not perform mapping migrations. Back up valuable data before any schema change.
6. Stop without deleting data using `docker compose down`.

`docker compose down -v` deletes named volumes and all service data. Use only after a separately approved cleanup plan.
