# Deployment options

## Current

Only a development Docker Compose topology exists. There is no GroundStack application container, Kubernetes manifest, Helm chart, Terraform module, AWS account setup, managed storage configuration, autoscaling policy, or production deployment tested in this repository.

## Future cloud design

A cloud design should be a separate documented profile with network isolation, managed secrets, durable object storage, database/search persistence, worker concurrency limits, backup and restore drills, monitoring, and predictable model-provider costs. Do not provision cloud resources without approval. Kubernetes/Terraform should be introduced only after a production service boundary and capacity requirement exist.
