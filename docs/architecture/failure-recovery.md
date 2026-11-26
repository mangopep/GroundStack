# Failure recovery

The queue and worker modules implement retry-related logic. There is no verified full-stack recovery drill or transactional guarantee across PostgreSQL, OpenSearch, and MinIO.

Target behavior: persist job identity and state, make writes idempotent, retain failure reason and retry count, prevent duplicate concurrent jobs for one document version, and provide a reconciliation command. Backups must include PostgreSQL plus object data and search index rebuild inputs; test restore into an isolated environment and compare manifest counts/hashes. No backup/restore benchmark or drill has been performed.
