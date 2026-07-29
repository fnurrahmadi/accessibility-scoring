#!/usr/bin/env python3
"""Build the non-identifying beta reference used by deployed V3 scoring."""
from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", required=True, type=Path)
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("reference_data/v3_beta_reference.json"),
    )
    args = parser.parse_args()

    with args.input.open(newline="", encoding="utf-8-sig") as stream:
        beta_values = sorted(
            float(row["beta"])
            for row in csv.DictReader(stream)
            if row.get("beta") not in (None, "")
        )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps({"model_version": "v3", "beta_values": beta_values}, separators=(",", ":")),
        encoding="utf-8",
    )
    print(f"Wrote {len(beta_values)} beta values to {args.output}.")


if __name__ == "__main__":
    main()
