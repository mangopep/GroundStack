# Disaster recovery

There is no verified disaster-recovery procedure. The in-memory watcher/queue loses active and pending state on process restart. Cross-store partial writes can leave orphaned chunks/objects. OpenSearch can be rebuilt only if canonical manifests and source files remain, but current canonical ownership is not defined.

Target recovery requires a durable manifest/job state, idempotent ingest, object/database backup, search reindex procedure, documented RPO/RTO, and a timed restore exercise. Do not claim durability from Docker named volumes alone.
