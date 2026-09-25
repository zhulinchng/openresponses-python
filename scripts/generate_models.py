"""Regenerate the checked-in Pydantic models from the pinned OpenAPI document."""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCHEMA = ROOT / "openresponses" / "openapi" / "2026-04-24.json"
OUTPUT = ROOT / "src" / "openresponses" / "types" / "generated.py"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    command = [
        sys.executable,
        "-m",
        "datamodel_code_generator",
        "--input",
        str(SCHEMA),
        "--input-file-type",
        "openapi",
        "--output",
        str(OUTPUT),
        "--output-model-type",
        "pydantic_v2.BaseModel",
        "--target-python-version",
        "3.10",
        "--snake-case-field",
        "--use-annotated",
        "--use-standard-collections",
        "--use-union-operator",
        "--use-subclass-enum",
        "--field-constraints",
        "--use-field-description",
        "--use-schema-description",
        "--use-operation-id-as-name",
        "--disable-timestamp",
        "--enum-field-as-literal",
        "all",
        "--base-class",
        "openresponses.types.base.OpenResponsesModel",
    ]
    if args.check:
        import tempfile

        with tempfile.TemporaryDirectory() as directory:
            candidate = Path(directory) / "generated.py"
            command[command.index("--output") + 1] = str(candidate)
            subprocess.run(command, check=True)
            if candidate.read_bytes() != OUTPUT.read_bytes():
                print("generated models are out of date", file=sys.stderr)
                return 1
    else:
        subprocess.run(command, check=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
