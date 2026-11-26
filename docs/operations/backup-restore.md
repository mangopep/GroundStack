# Backup and restore status

`scripts/backup_db.sh` is empty. There is no complete backup for PostgreSQL plus MinIO source objects plus the OpenSearch rebuild inputs, and no restore drill. A database dump alone is not a full GroundStack backup.

Before adding production data, define encryption, key ownership, retention, RPO/RTO, consistency point, and restore validation. Test restore to an isolated environment and compare object hashes, manifest counts, and rebuilt index counts. No backup/restore command is currently safe to recommend as complete.
