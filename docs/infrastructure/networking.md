# Networking

Compose services share a bridge network and use service names internally. Host processes typically connect through `localhost` ports. Current Compose publishes database, search, Redis, MinIO, and Langfuse ports on the host. OpenSearch security is disabled and no TLS profile is defined.

Use loopback-only bindings for a local profile when compatible, and do not expose these ports on public interfaces. A future production profile needs private subnets, TLS, authenticated service-to-service access, egress policy, and least-privilege credentials.
