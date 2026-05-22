"""Convert raw PDF/image notes into page images and a manual review CSV.

OCR is intentionally best-effort only. The generated CSV must be reviewed by hand
before it is merged into data/vocab.json.
"""

from __future__ import annotations

import argparse
import csv
import json
import re
import shutil
from datetime import datetime
from pathlib import Path
from typing import Iterable


PROJECT_ROOT = Path(__file__).resolve().parents[1]
RAW_DIR = PROJECT_ROOT / "raw_notes"
PAGES_DIR = PROJECT_ROOT / "extracted" / "pages"
OCR_DIR = PROJECT_ROOT / "extracted" / "ocr"
DEFAULT_CSV = OCR_DIR / "review_template.csv"

CSV_FIELDS = [
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

IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".webp", ".bmp", ".tif", ".tiff"}
WORD_RE = re.compile(r"^[A-Za-z][A-Za-z'-]*$")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Import PDFs/images from raw_notes and create a review CSV."
    )
    parser.add_argument(
        "--input",
        type=Path,
        default=RAW_DIR,
        help="A PDF/image file or directory. Defaults to raw_notes/.",
    )
    parser.add_argument(
        "--output-csv",
        type=Path,
        default=DEFAULT_CSV,
        help="Where to write the review CSV.",
    )
    parser.add_argument("--scale", type=float, default=2.0, help="PDF render scale.")
    parser.add_argument(
        "--no-ocr",
        action="store_true",
        help="Skip optional OCR even if pytesseract is installed.",
    )
    return parser.parse_args()


def source_files(input_path: Path) -> list[Path]:
    path = input_path if input_path.is_absolute() else PROJECT_ROOT / input_path
    if path.is_file():
        return [path]
    if not path.exists():
        return []
    allowed = {".pdf", ".hinote", *IMAGE_EXTENSIONS}
    return sorted(item for item in path.iterdir() if item.is_file() and item.suffix.lower() in allowed)


def page_image_name(source: Path, page_number: int, suffix: str = ".png") -> str:
    safe_stem = re.sub(r"[^A-Za-z0-9._-]+", "_", source.stem)
    return f"{safe_stem}_page-{page_number:03}{suffix}"


def render_pdf_with_pypdfium2(pdf_path: Path, scale: float) -> list[Path]:
    import pypdfium2 as pdfium  # type: ignore

    rendered: list[Path] = []
    document = pdfium.PdfDocument(str(pdf_path))
    for index in range(len(document)):
        page = document[index]
        output = PAGES_DIR / page_image_name(pdf_path, index + 1)
        image = page.render(scale=scale).to_pil()
        image.save(output)
        rendered.append(output)
    return rendered


def render_pdf_with_pymupdf(pdf_path: Path, scale: float) -> list[Path]:
    import fitz  # type: ignore

    rendered: list[Path] = []
    matrix = fitz.Matrix(scale, scale)
    with fitz.open(pdf_path) as document:
        for index, page in enumerate(document, start=1):
            output = PAGES_DIR / page_image_name(pdf_path, index)
            pixmap = page.get_pixmap(matrix=matrix, alpha=False)
            pixmap.save(output)
            rendered.append(output)
    return rendered


def render_pdf(pdf_path: Path, scale: float) -> tuple[list[Path], str]:
    try:
        return render_pdf_with_pypdfium2(pdf_path, scale), "pypdfium2"
    except ImportError:
        pass

    try:
        return render_pdf_with_pymupdf(pdf_path, scale), "pymupdf"
    except ImportError as exc:
        raise RuntimeError(
            "PDF rendering requires pypdfium2 or PyMuPDF. "
            "Install one with: python -m pip install pypdfium2"
        ) from exc


def copy_image(image_path: Path) -> Path:
    suffix = image_path.suffix.lower()
    output = PAGES_DIR / page_image_name(image_path, 1, suffix=suffix)
    shutil.copy2(image_path, output)
    return output


def try_ocr_page(image_path: Path) -> tuple[list[dict[str, object]], str]:
    try:
        from PIL import Image  # type: ignore
        import pytesseract  # type: ignore
        from pytesseract import Output  # type: ignore
    except ImportError:
        return [], "ocr_unavailable"

    rows: list[dict[str, object]] = []
    with Image.open(image_path) as image:
        data = pytesseract.image_to_data(
            image,
            output_type=Output.DICT,
            config="--psm 6",
            lang="eng",
        )

    for text, confidence in zip(data.get("text", []), data.get("conf", [])):
        word = str(text).strip()
        if not WORD_RE.match(word):
            continue
        try:
            confidence_value = max(0.0, min(1.0, float(confidence) / 100))
        except (TypeError, ValueError):
            confidence_value = ""
        rows.append(
            {
                "word": word,
                "raw_count_mark": "",
                "detected_count": "",
                "corrected_count": "",
                "confidence": confidence_value,
                "notes": "ocr_word_only; count_requires_manual_review",
            }
        )

    return rows, "ocr_attempted"


def build_review_rows(files: Iterable[Path], scale: float, no_ocr: bool) -> tuple[list[dict[str, object]], list[dict[str, object]]]:
    PAGES_DIR.mkdir(parents=True, exist_ok=True)
    OCR_DIR.mkdir(parents=True, exist_ok=True)

    review_rows: list[dict[str, object]] = []
    import_log: list[dict[str, object]] = []

    for source in files:
        suffix = source.suffix.lower()
        if suffix == ".hinote":
            import_log.append(
                {
                    "file": source.name,
                    "status": "skipped_hinote_archive_only",
                    "message": ".hinote is kept as raw archive; export PDF/images for processing.",
                }
            )
            continue

        try:
            if suffix == ".pdf":
                page_paths, renderer = render_pdf(source, scale)
                import_log.append({"file": source.name, "status": "rendered_pdf", "pages": len(page_paths), "renderer": renderer})
            elif suffix in IMAGE_EXTENSIONS:
                page_paths = [copy_image(source)]
                import_log.append({"file": source.name, "status": "copied_image", "pages": 1})
            else:
                import_log.append({"file": source.name, "status": "skipped_unsupported"})
                continue
        except Exception as exc:
            import_log.append({"file": source.name, "status": "failed", "message": str(exc)})
            continue

        for page_index, page_path in enumerate(page_paths, start=1):
            ocr_rows: list[dict[str, object]] = []
            ocr_status = "ocr_skipped"
            if not no_ocr:
                ocr_rows, ocr_status = try_ocr_page(page_path)

            if not ocr_rows:
                ocr_rows = [
                    {
                        "word": "",
                        "raw_count_mark": "",
                        "detected_count": "",
                        "corrected_count": "",
                        "confidence": "",
                        "notes": f"manual_entry_required; {ocr_status}",
                    }
                ]

            for line_index, row in enumerate(ocr_rows, start=1):
                review_rows.append(
                    {
                        "file": source.name,
                        "page": page_index,
                        "line_index": line_index,
                        "word": row.get("word", ""),
                        "raw_count_mark": row.get("raw_count_mark", ""),
                        "detected_count": row.get("detected_count", ""),
                        "corrected_count": row.get("corrected_count", ""),
                        "confidence": row.get("confidence", ""),
                        "notes": row.get("notes", ""),
                    }
                )

    return review_rows, import_log


def write_review_csv(rows: list[dict[str, object]], output_csv: Path) -> None:
    output = output_csv if output_csv.is_absolute() else PROJECT_ROOT / output_csv
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("w", newline="", encoding="utf-8-sig") as csv_file:
        writer = csv.DictWriter(csv_file, fieldnames=CSV_FIELDS)
        writer.writeheader()
        writer.writerows(rows)


def main() -> int:
    args = parse_args()
    files = source_files(args.input)
    if not files:
        print(f"No PDF/image/.hinote files found in {args.input}")
        write_review_csv([], args.output_csv)
        print(f"Created empty review CSV: {args.output_csv}")
        return 0

    rows, import_log = build_review_rows(files, args.scale, args.no_ocr)
    write_review_csv(rows, args.output_csv)

    log_path = OCR_DIR / "import_log.json"
    log_path.write_text(
        json.dumps(
            {
                "date": datetime.now().date().isoformat(),
                "review_csv": str(args.output_csv),
                "rows": len(rows),
                "files": import_log,
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    print(f"Generated review CSV: {args.output_csv}")
    print(f"Rows: {len(rows)}")
    print(f"Import log: {log_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
