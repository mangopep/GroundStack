"""Validate the platforms and OCI labels in a Buildx-produced OCI archive."""

from __future__ import annotations

import argparse
import json
import tarfile
from pathlib import Path
from typing import Any


def _read_json(archive: tarfile.TarFile, path: str) -> dict[str, Any]:
    stream = archive.extractfile(path)
    if stream is None:
        raise ValueError(f"OCI archive is missing {path}")
    value = json.load(stream)
    if not isinstance(value, dict):
        raise ValueError(f"OCI archive entry {path} is not a JSON object")
    return value


def _descriptors(archive: tarfile.TarFile, index: dict[str, Any]) -> list[dict[str, Any]]:
    results: list[dict[str, Any]] = []
    for descriptor in index.get("manifests", []):
        if descriptor.get("platform"):
            results.append(descriptor)
            continue
        digest = descriptor.get("digest", "")
        if not digest.startswith("sha256:"):
            continue
        nested = _read_json(archive, f"blobs/sha256/{digest.removeprefix('sha256:')}")
        results.extend(_descriptors(archive, nested))
    return results


def inspect_archive(path: Path, expected_version: str, expected_revision: str) -> set[str]:
    with tarfile.open(path, mode="r:*") as archive:
        index = _read_json(archive, "index.json")
        manifests = _descriptors(archive, index)
        platforms: set[str] = set()
        for descriptor in manifests:
            platform = descriptor.get("platform", {})
            if platform.get("os") != "linux":
                continue
            architecture = platform.get("architecture")
            if not architecture:
                continue
            digest = descriptor.get("digest", "")
            if not digest.startswith("sha256:"):
                raise ValueError(f"unsupported manifest digest: {digest}")
            manifest = _read_json(archive, f"blobs/sha256/{digest.removeprefix('sha256:')}")
            config_digest = manifest.get("config", {}).get("digest", "")
            if not config_digest.startswith("sha256:"):
                raise ValueError(f"unsupported config digest: {config_digest}")
            config = _read_json(archive, f"blobs/sha256/{config_digest.removeprefix('sha256:')}")
            labels = config.get("config", {}).get("Labels", {}) or {}
            if labels.get("org.opencontainers.image.version") != expected_version:
                raise ValueError(f"wrong OCI version label on linux/{architecture}")
            if labels.get("org.opencontainers.image.revision") != expected_revision:
                raise ValueError(f"wrong OCI source revision label on linux/{architecture}")
            platforms.add(architecture)
    return platforms


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("archive", type=Path)
    parser.add_argument("--version", required=True)
    parser.add_argument("--revision", required=True)
    arguments = parser.parse_args()
    platforms = inspect_archive(arguments.archive, arguments.version, arguments.revision)
    required = {"amd64", "arm64"}
    if not required <= platforms:
        parser.error(f"archive platforms {sorted(platforms)} do not include {sorted(required)}")
    print(
        "OCI archive verified: linux/amd64 and linux/arm64 labels match the requested version and revision"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
