#!/usr/bin/env bash
set -euo pipefail

project="groundstack-integration-local-$$"
compose=(docker compose --project-name "$project" --file docker-compose.integration.yml)

read -r postgres_port opensearch_port redis_port minio_port < <(
  python3 - <<'PY'
import socket

ports = []
for _ in range(4):
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        ports.append(sock.getsockname()[1])
print(*ports)
PY
)

export TEST_POSTGRES_PORT="$postgres_port"
export TEST_OPENSEARCH_PORT="$opensearch_port"
export TEST_REDIS_PORT="$redis_port"
export TEST_MINIO_PORT="$minio_port"
export GROUNDSTACK_RUN_SERVICE_INTEGRATION=1
export POSTGRES_HOST=127.0.0.1
export POSTGRES_PORT="$postgres_port"
export POSTGRES_USER=groundstack_test
export POSTGRES_PASSWORD=groundstack_test_only_password
export POSTGRES_DB=groundstack_test
export OPENSEARCH_HOST=127.0.0.1
export OPENSEARCH_PORT="$opensearch_port"
export REDIS_HOST=127.0.0.1
export REDIS_PORT="$redis_port"
export MINIO_ENDPOINT="127.0.0.1:$minio_port"
export MINIO_ACCESS_KEY=groundstack_test
export MINIO_SECRET_KEY=groundstack_test_only_password
export MINIO_SECURE=false

cleanup() {
  "${compose[@]}" down --volumes --remove-orphans
}
trap cleanup EXIT
trap 'exit 130' INT TERM

"${compose[@]}" up --detach --wait --wait-timeout 240
attempt=0
until curl --fail --silent "http://127.0.0.1:$minio_port/minio/health/live" >/dev/null; do
  attempt=$((attempt + 1))
  if [[ "$attempt" -ge 30 ]]; then
    echo "MinIO health endpoint did not become ready" >&2
    exit 1
  fi
  sleep 2
done

"$PWD/.venv/bin/python" -m pytest -q tests/integration
