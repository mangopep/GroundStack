# Deployment options

## Current

The development Docker Compose topology includes an optional API preview image for the currently implemented health/root/static-workspace routes. The trusted release workflow can build and attest this image, but no full GroundStack query/ingestion application container, Kubernetes manifest, Helm chart, Terraform module, AWS account setup, managed storage configuration, autoscaling policy, or production deployment has been implemented or tested.

## Future cloud design

A cloud design should be a separate documented profile with network isolation, managed secrets, durable object storage, database/search persistence, worker concurrency limits, backup and restore drills, monitoring, and predictable model-provider costs. Do not provision cloud resources without approval. Kubernetes/Terraform should be introduced only after a production service boundary and capacity requirement exist.
