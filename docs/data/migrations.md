# Database migrations

There is no migration framework. `scripts/init_db.sql` is mounted into PostgreSQL's initialization directory and runs only when the database volume is first initialized. Editing it does not migrate an existing named volume.

Before changing existing schemas, choose a migration tool, define forward/rollback policy, and test upgrades against a copy of a real schema. Never use `docker compose down -v` or delete database directories as a migration method; that removes local data.
