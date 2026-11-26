"""Generate or check the committed OpenAPI description for the implemented API."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.api.main import app  # noqa: E402

SPEC_PATH = ROOT / "docs" / "api" / "openapi.json"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--check",
        action="store_true",
        help="fail if the committed API description is stale instead of writing it",
    )
    arguments = parser.parse_args()
    rendered = json.dumps(app.openapi(), ensure_ascii=False, indent=2, sort_keys=True) + "\n"

    if arguments.check:
        if not SPEC_PATH.exists() or SPEC_PATH.read_text(encoding="utf-8") != rendered:
            parser.error("docs/api/openapi.json is stale; run `python scripts/export_openapi.py`")
        print("OpenAPI description is current")
        return 0

    SPEC_PATH.write_text(rendered, encoding="utf-8")
    print(f"Wrote {SPEC_PATH.relative_to(Path.cwd())}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
