"""Merge reviewed or filtered OCR CSV rows into data/vocab.json."""

from __future__ import annotations

import argparse
import csv
import json
import re
from datetime import date, datetime
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[1]
OCR_DIR = PROJECT_ROOT / "extracted" / "ocr"
VOCAB_PATH = PROJECT_ROOT / "data" / "vocab.json"
FREQUENCY_PATH = PROJECT_ROOT / "data" / "exam_frequency.json"
UPDATE_LOG_PATH = PROJECT_ROOT / "data" / "update_log.json"
DEFAULT_CSV = OCR_DIR / "auto_merge_candidates.csv"
DATE_RE = re.compile(r"(20\d{2}[-_]\d{2}[-_]\d{2})")
WORD_RE = re.compile(r"^[A-Za-z][A-Za-z'-]*$")
NORMALIZE_RE = re.compile(r"[^a-z'-]")

GARBAGE_WORDS = {
    "l",
    "ll",
    "lll",
    "iii",
    "rn",
    "vv",
    "cl",
    "larred",
    "giveyouthe",
    "ofthe",
    "inthe",
    "andthe",
    "toyour",
    "inthis",
    "fromthe",
}
SUSPECT_OCR_WORDS = {
    "terant",
    "cenfer",
    "vertica",
    "preindice",
    "vicions",
    "indula",
    "versatil",
    "intensire",
    "inguiry",
    "resilie",
    "sanctimpni",
    "astoni",
    "arain",
    "pilarim",
    "prectige",
    "isbadae",
    "lodae",
    "disrut",
    "dursuit",
    "petran",
    "plaave",
    "enclsu",
    "descen",
    "intimat",
    "expertis",
    "arieve",
    "arind",
    "badae",
    "netort",
    "abundan",
    "adiacer",
    "andit",
    "appraisa",
    "ardendi",
    "ascimilate",
    "calition",
    "cara",
    "carvo",
    "araze",
    "arief",
    "reconci",
    "concurren",
    "complemer",
    "vetera",
    "escence",
    "portrai",
    "ral",
    "cardin",
    "plansible",
}
PHRASE_MERGE_MARKERS = {
    "giveyouthe",
    "ofthe",
    "inthe",
    "andthe",
    "toyour",
    "inthis",
    "fromthe",
    "youthe",
    "youand",
    "andyou",
    "theand",
}
CONFIDENCE_TOLERANCE = 0.02


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Merge reviewed or filtered CSV rows into data/vocab.json.")
    parser.add_argument("--csv", type=Path, default=DEFAULT_CSV, help="Reviewed or filtered candidate CSV path.")
    parser.add_argument(
        "--include-auto",
        action="store_true",
        help="Allow auto_merge rows when corrected_count is blank.",
    )
    parser.add_argument(
        "--include-quick-audit",
        action="store_true",
        help="Allow quick_audit rows when corrected_count is blank. Off by default.",
    )
    parser.add_argument(
        "--min-confidence",
        type=float,
        default=0.82,
        help="Minimum confidence for automatic rows when --include-auto is used.",
    )
    parser.add_argument(
        "--allow-high-confidence-detected",
        action="store_true",
        help="Backward-compatible alias for --include-auto.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Read and validate the CSV merge without writing data/vocab.json or update_log.json.",
    )
    return parser.parse_args()


def load_json(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, data: Any) -> None:
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def normalize_word(word: str) -> str:
    return NORMALIZE_RE.sub("", word.strip().lower())


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


def parse_bool(value: Any) -> bool:
    return str(value).strip().lower() in {"true", "1", "yes", "y"}


def meets_threshold(value: float, threshold: float) -> bool:
    return value + CONFIDENCE_TOLERANCE >= threshold


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
    if source.get("source_type") in {"auto", "auto_merge", "quick_audit"}:
        detected = parse_int(source.get("detected_count"))
        return detected if detected is not None else 0
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
) -> tuple[dict[str, Any], bool]:
    if normalized_word in vocab_by_word:
        return vocab_by_word[normalized_word], False

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
    return entry, True


def choose_count(
    row: dict[str, Any],
    include_auto: bool,
    include_quick_audit: bool,
    min_confidence: float,
    csv_path: Path,
) -> tuple[int | None, str, str]:
    corrected = parse_int(row.get("corrected_count"))
    if corrected is not None:
        return corrected, "manual_corrected", ""

    candidate_level = str(row.get("candidate_level", "")).strip().lower()
    if not candidate_level:
        if csv_path.name == "auto_merge_candidates.csv":
            candidate_level = "auto_merge"
        elif csv_path.name == "quick_audit_candidates.csv":
            candidate_level = "quick_audit"
        elif csv_path.name == "manual_review_candidates.csv":
            candidate_level = "manual_review"

    detected = parse_int(row.get("detected_count"))
    confidence = parse_float(row.get("confidence")) or 0.0
    needs_review = parse_bool(row.get("needs_review"))

    if candidate_level == "manual_review":
        return None, "", "manual_review_requires_corrected_count"
    if candidate_level == "quick_audit":
        if not include_quick_audit:
            return None, "", "quick_audit_requires_include_quick_audit"
        if not meets_threshold(confidence, min_confidence):
            return None, "", "quick_audit_confidence_below_threshold"
        if detected is None:
            return None, "", "detected_count_required_for_quick_audit"
        return detected, "quick_audit", ""

    if not include_auto:
        return None, "", "auto_disabled_or_corrected_count_required"
    if needs_review and candidate_level != "auto_merge":
        return None, "", "needs_review_without_corrected_count"
    if not meets_threshold(confidence, min_confidence):
        return None, "", "auto_confidence_below_threshold"
    if detected is None:
        return None, "", "detected_count_required_for_auto"
    return detected, "auto_merge" if candidate_level == "auto_merge" else "auto", ""


def suspicious_reasons(word: str, filter_reason: str = "") -> list[str]:
    normalized = normalize_word(word)
    reasons: list[str] = []
    if not word or not normalized:
        reasons.append("missing_word")
    if word and not WORD_RE.match(word):
        reasons.append("invalid_chars")
    if normalized in GARBAGE_WORDS:
        reasons.append("known_ocr_garbage")
    if normalized in SUSPECT_OCR_WORDS:
        reasons.append("suspect_ocr_word")
    if normalized in PHRASE_MERGE_MARKERS or any(
        marker in normalized for marker in {"youthe", "ofthe", "inthe", "andthe", "toyour", "inthis", "fromthe"}
    ):
        reasons.append("phrase_merge")
    if len(normalized) > 22:
        reasons.append("too_long")
    if any(token in filter_reason for token in ["phrase_merge", "ocr_garbage_word", "suspect_ocr_word", "word_invalid_chars", "word_too_long"]):
        reasons.append("filter_flagged")
    return list(dict.fromkeys(reasons))


def top_contributions(contributions: dict[str, int], limit: int = 50) -> list[dict[str, Any]]:
    return [
        {"word": word, "forget_count": count}
        for word, count in sorted(contributions.items(), key=lambda item: (-item[1], item[0]))[:limit]
    ]


def count_csv_rows(path: Path) -> int:
    if not path.exists():
        return 0
    with path.open("r", newline="", encoding="utf-8-sig") as csv_file:
        return sum(1 for _ in csv.DictReader(csv_file))


def companion_counts() -> dict[str, int]:
    return {
        "quick_audit_rows": count_csv_rows(OCR_DIR / "quick_audit_candidates.csv"),
        "manual_review_rows": count_csv_rows(OCR_DIR / "manual_review_candidates.csv"),
    }


def main() -> int:
    args = parse_args()
    include_auto = args.include_auto or args.allow_high_confidence_detected
    csv_path = args.csv if args.csv.is_absolute() else PROJECT_ROOT / args.csv
    if not csv_path.exists():
        print(f"CSV not found: {csv_path}")
        return 1

    vocab = load_json(VOCAB_PATH, [])
    frequency = load_json(FREQUENCY_PATH, {})
    update_log = load_json(UPDATE_LOG_PATH, [])
    vocab_by_word = {item["normalized_word"]: item for item in vocab}
    existing_words = set(vocab_by_word)
    frequency_words = set(frequency.keys())

    merged = 0
    auto_merge_rows = 0
    skipped: list[dict[str, Any]] = []
    needs_review_rows_seen = 0
    quick_audit_rows_seen = 0
    manual_review_rows_seen = 0
    new_words: set[str] = set()
    updated_words: set[str] = set()
    unknown_new_words: set[str] = set()
    contributions: dict[str, int] = {}
    merge_preview: list[dict[str, Any]] = []
    suspicious_preview: list[dict[str, Any]] = []

    with csv_path.open("r", newline="", encoding="utf-8-sig") as csv_file:
        reader = csv.DictReader(csv_file)
        for row_number, row in enumerate(reader, start=2):
            candidate_level = str(row.get("candidate_level", "")).strip().lower()
            if parse_bool(row.get("needs_review")):
                needs_review_rows_seen += 1
            if candidate_level == "quick_audit":
                quick_audit_rows_seen += 1
            if candidate_level == "manual_review":
                manual_review_rows_seen += 1

            word = str(row.get("word", "")).strip()
            normalized = normalize_word(word)
            if not normalized:
                skipped.append({"row": row_number, "reason": "missing_word"})
                continue

            count_to_use, source_type, skip_reason = choose_count(
                row,
                include_auto,
                args.include_quick_audit,
                args.min_confidence,
                csv_path,
            )
            if count_to_use is None:
                skipped.append({"row": row_number, "word": word, "reason": skip_reason})
                continue

            file_name = str(row.get("file", "")).strip()
            seen_date = date_from_file(file_name)
            page = parse_page(row.get("page"))
            line_index = parse_page(row.get("line_index"))

            entry, was_new = ensure_entry(vocab_by_word, word, normalized, frequency, seen_date)
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
                "detected_count": parse_int(row.get("detected_count")),
                "corrected_count": parse_int(row.get("corrected_count")),
                "confidence": parse_float(row.get("confidence")),
                "word_confidence": parse_float(row.get("word_confidence")),
                "count_confidence": parse_float(row.get("count_confidence")),
                "source_type": source_type,
                "crop_word_path": str(row.get("crop_word_path", "")).strip(),
                "crop_count_path": str(row.get("crop_count_path", "")).strip(),
            }

            merge_source(entry, source)
            entry["forget_count"] = recalc_forget_count(entry)
            contributions[normalized] = contributions.get(normalized, 0) + count_to_use
            if was_new or normalized not in existing_words:
                new_words.add(normalized)
                if normalized not in frequency_words:
                    unknown_new_words.add(normalized)
            else:
                updated_words.add(normalized)
            if source_type == "auto_merge":
                auto_merge_rows += 1

            if len(merge_preview) < 50:
                merge_preview.append(
                    {
                        "word": normalized,
                        "detected_count": count_to_use,
                        "confidence": parse_float(row.get("confidence")),
                        "source_type": source_type,
                    }
                )

            reasons = suspicious_reasons(word, str(row.get("filter_reason", "")))
            if reasons and len(suspicious_preview) < 100:
                suspicious_preview.append(
                    {
                        "row": row_number,
                        "word": word,
                        "reason": ";".join(reasons),
                        "confidence": row.get("confidence", ""),
                    }
                )
            merged += 1

    output_vocab = sorted(vocab_by_word.values(), key=lambda item: item["normalized_word"])
    top_50 = top_contributions(contributions, 50)
    high_forget_count_words = sum(1 for item in contributions.values() if item >= 10)
    companion = companion_counts()
    recommendation = "nothing_to_merge"
    if merged > 0 and suspicious_preview:
        recommendation = "do_not_merge_review_suspicious_words"
    elif merged > 0:
        recommendation = "recommended_to_merge"

    dry_run_summary = {
        "merge_rows": merged,
        "auto_merge_rows": auto_merge_rows,
        "skip_rows": len(skipped),
        "needs_review_rows": needs_review_rows_seen,
        "quick_audit_rows_in_csv": quick_audit_rows_seen,
        "manual_review_rows_in_csv": manual_review_rows_seen,
        "quick_audit_rows_companion": companion["quick_audit_rows"],
        "manual_review_rows_companion": companion["manual_review_rows"],
        "new_words": len(new_words),
        "updated_words": len(updated_words),
        "high_forget_count_words": high_forget_count_words,
        "unknown_new_words": len(unknown_new_words),
        "merge_preview_first_50": merge_preview,
        "suspicious_preview_first_100": suspicious_preview,
        "top_50_forget_count": top_50,
        "recommendation": recommendation,
    }

    if not args.dry_run:
        write_json(VOCAB_PATH, output_vocab)
        update_log.append(
            {
                "date": datetime.now().isoformat(timespec="seconds"),
                "action": "merge_filtered_csv",
                "csv": str(csv_path.relative_to(PROJECT_ROOT) if csv_path.is_relative_to(PROJECT_ROOT) else csv_path),
                "include_auto": include_auto,
                "include_quick_audit": args.include_quick_audit,
                "min_confidence": args.min_confidence,
                "confidence_threshold_tolerance": CONFIDENCE_TOLERANCE,
                "merged_rows": merged,
                "auto_merge_rows": auto_merge_rows,
                "skipped_rows": len(skipped),
                "new_words": len(new_words),
                "updated_words": len(updated_words),
                "high_forget_count_words": high_forget_count_words,
                "unknown_new_words": len(unknown_new_words),
                "recommendation": recommendation,
                "top_50_forget_count": top_50,
                "skipped": skipped[:50],
            }
        )
        write_json(UPDATE_LOG_PATH, update_log)

    print(f"Will merge rows: {merged}")
    print(f"Auto-merge rows: {auto_merge_rows}")
    print(f"New words: {len(new_words)}")
    print(f"Updated words: {len(updated_words)}")
    print(f"Skipped rows: {len(skipped)}")
    print(f"Manual-review rows in this CSV: {manual_review_rows_seen}")
    print(f"Quick-audit rows in this CSV: {quick_audit_rows_seen}")
    print(f"Manual-review rows companion file: {companion['manual_review_rows']}")
    print(f"Quick-audit rows companion file: {companion['quick_audit_rows']}")
    print(f"High forget_count word count (>=10): {high_forget_count_words}")
    print(f"New words not in exam_frequency.json or existing vocab.json: {len(unknown_new_words)}")
    print("First 50 words to merge:")
    for item in merge_preview:
        print(f"  {item['word']}: count={item['detected_count']}, confidence={item['confidence']}, source={item['source_type']}")
    print("Potential suspicious words first 100:")
    if suspicious_preview:
        for item in suspicious_preview:
            print(f"  row {item['row']}: {item['word']} ({item['reason']}, confidence={item['confidence']})")
    else:
        print("  none")
    print("Top 50 forget_count contributions:")
    for item in top_50:
        print(f"  {item['word']}: {item['forget_count']}")
    print(f"Recommendation: {recommendation}")
    if args.dry_run:
        print("Dry run: no files written")
    else:
        print(f"Updated: {VOCAB_PATH}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
