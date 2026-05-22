"""Validate vocabulary and exam-frequency JSON files."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[1]
VOCAB_PATH = PROJECT_ROOT / "data" / "vocab.json"
FREQUENCY_PATH = PROJECT_ROOT / "data" / "exam_frequency.json"
WORD_RE = re.compile(r"^[a-z][a-z'-]*$")
DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")

REQUIRED_ENTRY_FIELDS = {
    "word",
    "normalized_word",
    "forget_count",
    "exam_frequency",
    "exam_frequency_label",
    "chinese",
    "similar_words",
    "examples",
    "sources",
    "first_seen",
    "last_seen",
}

REQUIRED_SOURCE_FIELDS = {
    "file",
    "page",
    "raw_count_mark",
    "detected_count",
    "corrected_count",
    "confidence",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Validate data/vocab.json.")
    parser.add_argument("--strict-warnings", action="store_true", help="Treat warnings as failures.")
    return parser.parse_args()


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def is_non_negative_int(value: Any) -> bool:
    return isinstance(value, int) and value >= 0


def is_optional_non_negative_int(value: Any) -> bool:
    return value is None or value == "" or is_non_negative_int(value)


def is_optional_confidence(value: Any) -> bool:
    if value is None or value == "":
        return True
    return isinstance(value, (int, float)) and 0 <= value <= 1


def validate_frequency(frequency: dict[str, Any], errors: list[str], warnings: list[str]) -> None:
    for word, item in frequency.items():
        if not WORD_RE.match(word):
            errors.append(f"exam_frequency key is not normalized: {word}")
        if not isinstance(item, dict):
            errors.append(f"exam_frequency.{word} must be an object")
            continue
        score = item.get("score")
        label = item.get("label")
        source = item.get("source")
        if not isinstance(score, int) or not 0 <= score <= 5:
            errors.append(f"exam_frequency.{word}.score must be an integer from 0 to 5")
        if not isinstance(label, str) or not label:
            errors.append(f"exam_frequency.{word}.label is required")
        if source not in {"manual", "demo"}:
            warnings.append(f"exam_frequency.{word}.source should be manual or demo")


def validate_vocab_entry(
    entry: dict[str, Any],
    index: int,
    frequency: dict[str, Any],
    seen_words: set[str],
    errors: list[str],
    warnings: list[str],
) -> None:
    label = entry.get("word", f"entry[{index}]")
    missing = REQUIRED_ENTRY_FIELDS - set(entry)
    if missing:
        errors.append(f"{label}: missing fields {sorted(missing)}")

    normalized = entry.get("normalized_word")
    if not isinstance(normalized, str) or not WORD_RE.match(normalized):
        errors.append(f"{label}: invalid normalized_word")
    elif normalized in seen_words:
        errors.append(f"{label}: duplicate normalized_word {normalized}")
    else:
        seen_words.add(normalized)

    if not is_non_negative_int(entry.get("forget_count")):
        errors.append(f"{label}: forget_count must be a non-negative integer")

    exam_frequency = entry.get("exam_frequency")
    if not isinstance(exam_frequency, int) or not 0 <= exam_frequency <= 5:
        errors.append(f"{label}: exam_frequency must be an integer from 0 to 5")

    exam_label = entry.get("exam_frequency_label")
    if not isinstance(exam_label, str) or not exam_label:
        errors.append(f"{label}: exam_frequency_label is required")

    if isinstance(normalized, str):
        frequency_item = frequency.get(normalized)
        if frequency_item:
            if entry.get("exam_frequency") != frequency_item.get("score"):
                errors.append(f"{label}: exam_frequency does not match data/exam_frequency.json")
            if entry.get("exam_frequency_label") != frequency_item.get("label"):
                errors.append(f"{label}: exam_frequency_label does not match data/exam_frequency.json")
        else:
            if entry.get("exam_frequency") != 0 or entry.get("exam_frequency_label") != "未标注":
                errors.append(f"{label}: missing frequency data must use 0/未标注")

    chinese = entry.get("chinese")
    if not isinstance(chinese, str):
        errors.append(f"{label}: chinese must be a string")
    elif not chinese.strip():
        warnings.append(f"{label}: chinese is empty")

    if not isinstance(entry.get("similar_words"), list):
        errors.append(f"{label}: similar_words must be a list")
    if not isinstance(entry.get("examples"), list):
        errors.append(f"{label}: examples must be a list")

    for date_field in ("first_seen", "last_seen"):
        value = entry.get(date_field)
        if not isinstance(value, str) or not DATE_RE.match(value):
            errors.append(f"{label}: {date_field} must use YYYY-MM-DD")

    sources = entry.get("sources")
    if not isinstance(sources, list):
        errors.append(f"{label}: sources must be a list")
        return
    if not sources:
        warnings.append(f"{label}: sources is empty")

    counted_total = 0
    for source_index, source in enumerate(sources, start=1):
        if not isinstance(source, dict):
            errors.append(f"{label}: source #{source_index} must be an object")
            continue
        missing_source = REQUIRED_SOURCE_FIELDS - set(source)
        if missing_source:
            errors.append(f"{label}: source #{source_index} missing fields {sorted(missing_source)}")
        if not isinstance(source.get("file"), str) or not source.get("file"):
            errors.append(f"{label}: source #{source_index} file is required")
        if not isinstance(source.get("page"), int) or source.get("page") < 1:
            errors.append(f"{label}: source #{source_index} page must be a positive integer")
        if not is_optional_non_negative_int(source.get("detected_count")):
            errors.append(f"{label}: source #{source_index} detected_count is invalid")
        if not is_optional_non_negative_int(source.get("corrected_count")):
            errors.append(f"{label}: source #{source_index} corrected_count is invalid")
        if not is_optional_confidence(source.get("confidence")):
            errors.append(f"{label}: source #{source_index} confidence must be between 0 and 1")
        corrected = source.get("corrected_count")
        if isinstance(corrected, int):
            counted_total += corrected

    if counted_total and counted_total != entry.get("forget_count"):
        warnings.append(f"{label}: forget_count differs from sum(corrected_count) sources")


def main() -> int:
    args = parse_args()
    errors: list[str] = []
    warnings: list[str] = []

    vocab = load_json(VOCAB_PATH)
    frequency = load_json(FREQUENCY_PATH)

    if not isinstance(vocab, list):
        errors.append("data/vocab.json must contain a list")
        vocab = []
    if not isinstance(frequency, dict):
        errors.append("data/exam_frequency.json must contain an object")
        frequency = {}

    validate_frequency(frequency, errors, warnings)

    seen_words: set[str] = set()
    for index, entry in enumerate(vocab, start=1):
        if not isinstance(entry, dict):
            errors.append(f"entry[{index}] must be an object")
            continue
        validate_vocab_entry(entry, index, frequency, seen_words, errors, warnings)

    print(f"Checked words: {len(vocab)}")
    print(f"Errors: {len(errors)}")
    print(f"Warnings: {len(warnings)}")

    for item in errors:
        print(f"ERROR: {item}")
    for item in warnings:
        print(f"WARNING: {item}")

    if errors or (args.strict_warnings and warnings):
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
