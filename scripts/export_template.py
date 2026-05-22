"""Create an empty manual review CSV template."""

from __future__ import annotations

import argparse
import csv
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT = PROJECT_ROOT / "extracted" / "ocr" / "review_template.csv"
FIELDS = [
    "file",
    "page",
    "line_index",
    "word",
    "raw_count_mark",
    "detected_count",
    "corrected_count",
    "confidence",
    "notes",
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate a blank review CSV template.")
    parser.add_argument("--rows", type=int, default=40, help="Number of blank rows to create.")
    parser.add_argument("--file", default="", help="Optional source file name to prefill.")
    parser.add_argument("--page", type=int, default=1, help="Page number to prefill.")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT, help="CSV output path.")
    parser.add_argument("--force", action="store_true", help="Overwrite an existing output file.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    output = args.output if args.output.is_absolute() else PROJECT_ROOT / args.output
    if output.exists() and not args.force:
        print(f"Refusing to overwrite existing file: {output}")
        print("Use --force if you intentionally want to replace it.")
        return 1

    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("w", newline="", encoding="utf-8-sig") as csv_file:
        writer = csv.DictWriter(csv_file, fieldnames=FIELDS)
        writer.writeheader()
        for index in range(1, args.rows + 1):
            writer.writerow(
                {
                    "file": args.file,
                    "page": args.page,
                    "line_index": index,
                    "word": "",
                    "raw_count_mark": "",
                    "detected_count": "",
                    "corrected_count": "",
                    "confidence": "",
                    "notes": "manual_entry",
                }
            )

    print(f"Created review template: {output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
