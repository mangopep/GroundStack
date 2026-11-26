"""Render every Mermaid fence to validate diagram syntax with pinned Mermaid CLI."""

from __future__ import annotations

import re
import subprocess
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MERMAID_IMAGE = (
    "ghcr.io/mermaid-js/mermaid-cli/mermaid-cli"
    "@sha256:18938e53497376d524e04b1fc0bf7b6d61a491ce9ff7032bb2855d57155acb10"
)
FENCE = re.compile(r"^```mermaid\s*\n(.*?)^```\s*$", re.MULTILINE | re.DOTALL)


def main() -> int:
    diagrams = [
        (path, match.group(1))
        for path in sorted((ROOT / "docs").rglob("*.md"))
        for match in FENCE.finditer(path.read_text(encoding="utf-8"))
    ]
    if not diagrams:
        raise SystemExit("No Mermaid diagrams found; expected documentation diagrams to be checked")

    with tempfile.TemporaryDirectory(prefix="groundstack-mermaid-") as temporary:
        temp_dir = Path(temporary)
        for index, (source, diagram) in enumerate(diagrams, start=1):
            input_name = f"diagram-{index:03}.mmd"
            output_name = f"diagram-{index:03}.svg"
            (temp_dir / input_name).write_text(diagram, encoding="utf-8")
            try:
                subprocess.run(
                    [
                        "docker",
                        "run",
                        "--rm",
                        "--volume",
                        f"{temp_dir}:/data",
                        MERMAID_IMAGE,
                        "--input",
                        f"/data/{input_name}",
                        "--output",
                        f"/data/{output_name}",
                    ],
                    check=True,
                    stdout=subprocess.DEVNULL,
                )
            except subprocess.CalledProcessError as exc:
                raise SystemExit(f"Invalid Mermaid diagram in {source.relative_to(ROOT)}") from exc

    print(f"Validated {len(diagrams)} Mermaid diagrams")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
