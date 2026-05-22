"""Merge a manually reviewed CSV into data/vocab.json."""

from __future__ import annotations

import argparse
import csv
import json
import re
from datetime import date, datetime
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[1]
VOCAB_PATH = PROJECT_ROOT / "data" / "vocab.json"
FREQUENCY_PATH = PROJECT_ROOT / "data" / "exam_frequency.json"
UPDATE_LOG_PATH = PROJECT_ROOT / "data" / "update_log.json"
DEFAULT_CSV = PROJECT_ROOT / "extracted" / "ocr" / "review_template.csv"
HIGH_CONFIDENCE_THRESHOLD = 0.9
DATE_RE = re.compile(r"(20\d{2}[-_]\d{2}[-_]\d{2})")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Merge reviewed CSV rows into data/vocab.json.")
    parser.add_argument("--csv", type=Path, default=DEFAULT_CSV, help="Reviewed CSV path.")
    parser.add_argument(
        "--allow-high-confidence-detected",
        action="store_true",
        help="Allow detected_count when corrected_count is blank and confidence is high.",
    )
    return parser.parse_args()


def load_json(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, data: Any) -> None:
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def normalize_word(word: str) -> str:
    return re.sub(r"[^a-z'-]", "", word.strip().lower())


def parse_int(value: Any) -> int | None:
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    try:
        parsed = int(text)
    except ValueError:
        return None
    return parsed if parsed >= 0 else None


def parse_float(value: Any) -> float | None:
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    try:
        parsed = float(text)
    except ValueError:
        return None
    return max(0.0, min(1.0, parsed))


def parse_page(value: Any) -> int:
    parsed = parse_int(value)
    return parsed if parsed is not None and parsed > 0 else 1


def date_from_file(filename: str) -> str:
    match = DATE_RE.search(filename)
    if not match:
        return date.today().isoformat()
    return match.group(1).replace("_", "-")


def exam_info(frequency: dict[str, Any], normalized_word: str) -> tuple[int, str]:
    item = frequency.get(normalized_word)
    if not item:
        return 0, "未标注"
    return int(item.get("score", 0)), str(item.get("label", "未标注"))


def source_key(source: dict[str, Any]) -> tuple[str, int, int]:
    return (
        str(source.get("file", "")),
        int(source.get("page", 0) or 0),
        int(source.get("line_index", 0) or 0),
    )


def source_count(source: dict[str, Any]) -> int:
    corrected = parse_int(source.get("corrected_count"))
    if corrected is not None:
        return corrected
    detected = parse_int(source.get("detected_count"))
    confidence = parse_float(source.get("confidence"))
    if detected is not None and confidence is not None and confidence >= HIGH_CONFIDENCE_THRESHOLD:
        return detected
    return 0


def recalc_forget_count(entry: dict[str, Any]) -> int:
    return sum(source_count(source) for source in entry.get("sources", []))


def merge_source(entry: dict[str, Any], new_source: dict[str, Any]) -> None:
    sources = entry.setdefault("sources", [])
    new_key = source_key(new_source)
    for index, existing in enumerate(sources):
        if source_key(existing) == new_key:
            sources[index] = new_source
            return
    sources.append(new_source)


def ensure_entry(
    vocab_by_word: dict[str, dict[str, Any]],
    word: str,
    normalized_word: str,
    frequency: dict[str, Any],
    seen_date: str,
) -> dict[str, Any]:
    if normalized_word in vocab_by_word:
        return vocab_by_word[normalized_word]

    score, label = exam_info(frequency, normalized_word)
    entry = {
        "word": word,
        "normalized_word": normalized_word,
        "forget_count": 0,
        "exam_frequency": score,
        "exam_frequency_label": label,
        "chinese": "",
        "similar_words": [],
        "examples": [],
        "sources": [],
        "first_seen": seen_date,
        "last_seen": seen_date,
    }
    vocab_by_word[normalized_word] = entry
    return entry


def main() -> int:
    args = parse_args()
    csv_path = args.csv if args.csv.is_absolute() else PROJECT_ROOT / args.csv
    if not csv_path.exists():
        print(f"CSV not found: {csv_path}")
        return 1

    vocab = load_json(VOCAB_PATH, [])
    frequency = load_json(FREQUENCY_PATH, {})
    update_log = load_json(UPDATE_LOG_PATH, [])
    vocab_by_word = {item["normalized_word"]: item for item in vocab}

    merged = 0
    skipped: list[dict[str, Any]] = []
    high_confidence_used = 0

    with csv_path.open("r", newline="", encoding="utf-8-sig") as csv_file:
        reader = csv.DictReader(csv_file)
        for row_number, row in enumerate(reader, start=2):
            word = str(row.get("word", "")).strip()
            normalized = normalize_word(word)
            if not normalized:
                skipped.append({"row": row_number, "reason": "missing_word"})
                continue

            corrected = parse_int(row.get("corrected_count"))
            detected = parse_int(row.get("detected_count"))
            confidence = parse_float(row.get("confidence"))
            count_to_use = corrected
            used_detected = False

            if count_to_use is None:
                if (
                    args.allow_high_confidence_detected
                    and detected is not None
                    and confidence is not None
                    and confidence >= HIGH_CONFIDENCE_THRESHOLD
                ):
                    count_to_use = detected
                    used_detected = True
                    high_confidence_used += 1
                else:
                    skipped.append(
                        {
                            "row": row_number,
                            "word": word,
                            "reason": "corrected_count_required",
                        }
                    )
                    continue

            file_name = str(row.get("file", "")).strip()
            seen_date = date_from_file(file_name)
            page = parse_page(row.get("page"))
            line_index = parse_page(row.get("line_index"))

            entry = ensure_entry(vocab_by_word, word, normalized, frequency, seen_date)
            score, label = exam_info(frequency, normalized)
            entry["exam_frequency"] = score
            entry["exam_frequency_label"] = label
            entry["first_seen"] = min(str(entry.get("first_seen", seen_date)), seen_date)
            entry["last_seen"] = max(str(entry.get("last_seen", seen_date)), seen_date)

            source = {
                "file": file_name,
                "page": page,
                "line_index": line_index,
                "raw_count_mark": str(row.get("raw_count_mark", "")).strip(),
                "detected_count": detected,
                "corrected_count": corrected,
                "confidence": confidence,
            }
            if used_detected:
                source["merge_note"] = "used_high_confidence_detected_count"

            merge_source(entry, source)
            entry["forget_count"] = recalc_forget_count(entry)
            merged += 1

    output_vocab = sorted(vocab_by_word.values(), key=lambda item: item["normalized_word"])
    write_json(VOCAB_PATH, output_vocab)

    update_log.append(
        {
            "date": datetime.now().isoformat(timespec="seconds"),
            "action": "merge_review_csv",
            "csv": str(csv_path.relative_to(PROJECT_ROOT) if csv_path.is_relative_to(PROJECT_ROOT) else csv_path),
            "merged_rows": merged,
            "skipped_rows": len(skipped),
            "high_confidence_detected_rows": high_confidence_used,
            "skipped": skipped[:50],
        }
    )
    write_json(UPDATE_LOG_PATH, update_log)

    print(f"Merged rows: {merged}")
    print(f"Skipped rows: {len(skipped)}")
    if high_confidence_used:
        print(f"Used high-confidence detected counts: {high_confidence_used}")
    print(f"Updated: {VOCAB_PATH}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
