# Environment and promotion model

GroundStack currently has a verified local/CI service topology and an API preview image. Staging and production deployments are not configured. Do not treat the table below as evidence that a hosted environment already exists.

| Environment | Purpose | Services and artifacts | Secrets/data | Verification and cleanup |
|---|---|---|---|---|
| Local development | Work on ingestion adapters and static API preview | Docker Compose pins PostgreSQL/AGE, OpenSearch, Redis, MinIO, and Langfuse; Ollama is a separately started host service; API preview is opt-in | Local `.env` contains developer-owned secrets. Do not commit it. Named local volumes persist until an explicit destructive reset. | `make dev`, `make smoke`; `make integration` creates its own fake-credential disposable stack and removes it |
| Pull request CI | Verify untrusted changes | Locked Python dependencies, tests, docs, static JS check, API preview container build, service adapters | Read-only GitHub token; no repository secrets; fake service credentials only | Each workflow runs in an ephemeral hosted runner; PRs do not publish packages or Pages |
| Release candidate | Rehearse a candidate without side effects outside Actions artifacts | The exact multi-platform OCI archive is scanned and retained with per-platform CycloneDX SBOMs | No registry credential or publishing token is used in candidate jobs | Dispatch with `publish=false`; artifact expires after 30 days |
| Staging | Not provisioned | No host, cluster, database, or deployment workflow exists | No staging secrets configured | Future setup must promote the release digest without rebuilding |
| Production | Not provisioned; application is not production-ready | No deployment workflow, managed data stores, or migration runner exists | No production secrets configured | Future deployment requires approved environment, backup/restore drill, monitoring, and tested rollback |

## Promotion rules

After a reviewed release is published, staging and production should consume the same GHCR `@sha256:` digest from the signed release manifest. Do not rebuild between environments or substitute a version tag at deployment time. Environments should be separated by secret scope and data stores, not by changing the image bytes.

The current database schema is initialized by SQL and has no versioned migration lifecycle. Before deploying a feature that changes persistent schemas, add forward/compatibility migrations and a restore-tested rollback procedure. Release publication is described in [the release process](release.md), but deployment promotion remains a documented future control, not an implemented workflow.

## Infrastructure as code

There are no Terraform files because no deployment target, provider, state backend, cost boundary, or account has been approved. A later infrastructure proposal should define environment separation, state access and locking, sensitive variables, cost limits, destruction protection, reviewed plans, recovery, and who may apply/destroy. PR CI must not provision billable resources.
