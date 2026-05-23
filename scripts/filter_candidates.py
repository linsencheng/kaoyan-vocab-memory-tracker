"""Split OCR extraction rows into auto-merge, quick-audit, and manual-review tiers."""

from __future__ import annotations

import argparse
import csv
import json
import random
import re
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[1]
OCR_DIR = PROJECT_ROOT / "extracted" / "ocr"
DATA_DIR = PROJECT_ROOT / "data"
DEFAULT_INPUT = OCR_DIR / "auto_filled_review.csv"
DEFAULT_AUTO = OCR_DIR / "auto_merge_candidates.csv"
DEFAULT_QUICK = OCR_DIR / "quick_audit_candidates.csv"
DEFAULT_MANUAL = OCR_DIR / "manual_review_candidates.csv"
DEFAULT_REPORT = OCR_DIR / "filter_report.json"
VOCAB_PATH = DATA_DIR / "vocab.json"
FREQUENCY_PATH = DATA_DIR / "exam_frequency.json"

WORD_RE = re.compile(r"^[A-Za-z][A-Za-z'-]*$")
NORMALIZE_RE = re.compile(r"[^a-z'-]")
VOWEL_RE = re.compile(r"[aeiouy]")

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
    "theof",
}

OUTPUT_EXTRA_FIELDS = [
    "candidate_level",
    "filter_reason",
    "normalized_word",
    "in_vocab",
    "in_exam_frequency",
]

CONFIDENCE_TOLERANCE = 0.02


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Filter OCR rows into safer candidate tiers.")
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT, help="Input auto-filled review CSV.")
    parser.add_argument("--auto-output", type=Path, default=DEFAULT_AUTO, help="Auto-merge CSV output.")
    parser.add_argument("--quick-output", type=Path, default=DEFAULT_QUICK, help="Quick-audit CSV output.")
    parser.add_argument("--manual-output", type=Path, default=DEFAULT_MANUAL, help="Manual-review CSV output.")
    parser.add_argument("--report", type=Path, default=DEFAULT_REPORT, help="Filter report JSON output.")
    parser.add_argument("--min-confidence", type=float, default=0.82, help="Minimum confidence for auto merge.")
    parser.add_argument("--min-word-confidence", type=float, default=0.82, help="Minimum OCR word confidence.")
    parser.add_argument("--min-count-confidence", type=float, default=0.70, help="Minimum count confidence.")
    parser.add_argument("--max-auto-merge", type=int, default=4000, help="Maximum auto-merge rows to emit.")
    parser.add_argument("--max-manual-review", type=int, default=800, help="Maximum manual-review rows to emit.")
    parser.add_argument("--quick-audit-rate", type=float, default=0.05, help="Random audit rate from auto rows.")
    parser.add_argument("--seed", type=int, default=20260523, help="Random seed for stable sampling.")
    return parser.parse_args()


def resolve_path(path: Path) -> Path:
    return path if path.is_absolute() else PROJECT_ROOT / path


def load_json(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    return json.loads(path.read_text(encoding="utf-8"))


def load_rows(path: Path) -> tuple[list[dict[str, Any]], list[str]]:
    with path.open("r", newline="", encoding="utf-8-sig") as csv_file:
        reader = csv.DictReader(csv_file)
        return list(reader), list(reader.fieldnames or [])


def write_csv(path: Path, fields: list[str], rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    output_fields = fields + [field for field in OUTPUT_EXTRA_FIELDS if field not in fields]
    with path.open("w", newline="", encoding="utf-8-sig") as csv_file:
        writer = csv.DictWriter(csv_file, fieldnames=output_fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def parse_float(value: Any) -> float:
    try:
        return max(0.0, min(1.0, float(str(value).strip())))
    except (TypeError, ValueError):
        return 0.0


def parse_int(value: Any) -> int | None:
    text = str(value or "").strip()
    if not text:
        return None
    try:
        parsed = int(text)
    except ValueError:
        return None
    return parsed


def meets_threshold(value: float, threshold: float) -> bool:
    return value + CONFIDENCE_TOLERANCE >= threshold


def normalize_word(word: str) -> str:
    return NORMALIZE_RE.sub("", word.strip().lower())


def row_key(row: dict[str, Any]) -> tuple[str, str, str]:
    return (str(row.get("file", "")), str(row.get("page", "")), str(row.get("line_index", "")))


def word_has_invalid_chars(word: str) -> bool:
    return not bool(WORD_RE.match(word))


def is_phrase_merge(normalized: str) -> bool:
    if normalized in PHRASE_MERGE_MARKERS:
        return True
    return any(marker in normalized for marker in {"youthe", "ofthe", "inthe", "andthe", "toyour", "inthis", "fromthe"})


def is_garbage_word(normalized: str) -> bool:
    if normalized in GARBAGE_WORDS:
        return True
    if len(normalized) == 1:
        return True
    if len(normalized) <= 3 and len(set(normalized)) == 1:
        return True
    return False


def is_suspect_ocr_word(normalized: str) -> bool:
    return normalized in SUSPECT_OCR_WORDS


def common_word_shape(normalized: str, known: bool) -> bool:
    if known:
        return True
    if len(normalized) < 2 or len(normalized) > 22:
        return False
    if not VOWEL_RE.search(normalized) and len(normalized) > 3:
        return False
    if normalized.count("'") > 1 or normalized.count("-") > 2:
        return False
    if re.search(r"(.)\1\1\1", normalized):
        return False
    return True


def page_line_stats(rows: list[dict[str, Any]]) -> dict[tuple[str, str], dict[str, Any]]:
    grouped: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        grouped[(str(row.get("file", "")), str(row.get("page", "")))].append(row)

    stats: dict[tuple[str, str], dict[str, Any]] = {}
    for key, page_rows in grouped.items():
        line_indexes = [parse_int(row.get("line_index")) for row in page_rows]
        valid_indexes = [item for item in line_indexes if item is not None]
        stats[key] = {
            "row_count": len(page_rows),
            "unique_line_count": len(set(valid_indexes)),
            "line_count_ok": 30 <= len(page_rows) <= 50,
            "line_index_ok": len(valid_indexes) == len(page_rows) and len(set(valid_indexes)) == len(valid_indexes),
        }
    return stats


def classify_base(
    row: dict[str, Any],
    known_words: set[str],
    frequency_words: set[str],
    occurrence_counts: Counter[str],
    page_stats: dict[tuple[str, str], dict[str, Any]],
) -> dict[str, Any]:
    word = str(row.get("word", "")).strip()
    normalized = normalize_word(word)
    detected_count = parse_int(row.get("detected_count"))
    confidence = parse_float(row.get("confidence"))
    word_confidence = parse_float(row.get("word_confidence"))
    count_confidence = parse_float(row.get("count_confidence"))
    page_key = (str(row.get("file", "")), str(row.get("page", "")))
    page_info = page_stats.get(page_key, {})
    in_vocab = normalized in known_words
    in_frequency = normalized in frequency_words
    known = in_vocab or in_frequency

    hard_reasons: list[str] = []
    soft_reasons: list[str] = []

    if not word:
        hard_reasons.append("word_empty")
    if detected_count is None:
        hard_reasons.append("count_empty")
    elif detected_count < 1 or detected_count > 30:
        hard_reasons.append("count_invalid_or_too_large")
    if word and word_has_invalid_chars(word):
        hard_reasons.append("word_invalid_chars")
    if normalized and len(normalized) > 22:
        hard_reasons.append("word_too_long")
    if normalized and is_phrase_merge(normalized):
        hard_reasons.append("phrase_merge")
    if normalized and is_garbage_word(normalized):
        hard_reasons.append("ocr_garbage_word")
    if normalized and is_suspect_ocr_word(normalized):
        hard_reasons.append("suspect_ocr_word")
    if str(row.get("notes", "")).find("multiple_words_detected") >= 0:
        hard_reasons.append("multiple_words_detected")
    if confidence < 0.55:
        soft_reasons.append("very_low_confidence")
    if count_confidence < 0.45:
        soft_reasons.append("very_low_count_confidence")
    if not page_info.get("line_count_ok", True) or not page_info.get("line_index_ok", True):
        hard_reasons.append("page_line_sequence_abnormal")
    if normalized and not common_word_shape(normalized, known):
        soft_reasons.append("weak_word_shape")
    if normalized and occurrence_counts[normalized] == 1 and not known and confidence < 0.82:
        soft_reasons.append("single_unknown_word")

    return {
        "word": word,
        "normalized": normalized,
        "detected_count": detected_count,
        "confidence": confidence,
        "word_confidence": word_confidence,
        "count_confidence": count_confidence,
        "in_vocab": in_vocab,
        "in_frequency": in_frequency,
        "known": known,
        "hard_reasons": hard_reasons,
        "soft_reasons": soft_reasons,
    }


def decorate_row(row: dict[str, Any], level: str, reason: str, info: dict[str, Any]) -> dict[str, Any]:
    copied = dict(row)
    copied["candidate_level"] = level
    copied["filter_reason"] = reason
    copied["normalized_word"] = info["normalized"]
    copied["in_vocab"] = "true" if info["in_vocab"] else "false"
    copied["in_exam_frequency"] = "true" if info["in_frequency"] else "false"
    if level == "auto_merge":
        copied["needs_review"] = "False"
    else:
        copied["needs_review"] = "True"
    return copied


def auto_priority(item: tuple[dict[str, Any], dict[str, Any]]) -> tuple[int, float, int, float, str]:
    row, info = item
    known_bonus = 2 if info["known"] else 0
    count = info["detected_count"] or 0
    return (
        known_bonus,
        info["confidence"],
        count,
        info["word_confidence"] + info["count_confidence"],
        info["normalized"],
    )


def manual_priority(item: tuple[dict[str, Any], dict[str, Any], str]) -> tuple[int, int, float, str]:
    _row, info, reason = item
    count = info["detected_count"] or 0
    score = 0
    if count >= 10:
        score += 100
    if count > 0 and not info["word"]:
        score += 80
    if "phrase_merge" in reason or "ocr_garbage_word" in reason:
        score += 70
    if "multiple_words_detected" in reason:
        score += 60
    if info["known"]:
        score += 50
    if info["word"] and count > 0:
        score += 30
    return (score, count, info["confidence"], info["normalized"])


def add_unique(target: dict[tuple[str, str, str], dict[str, Any]], row: dict[str, Any]) -> None:
    target.setdefault(row_key(row), row)


def sample_auto_rows(
    auto_rows: list[dict[str, Any]],
    quick_rows_by_key: dict[tuple[str, str, str], dict[str, Any]],
    sample_rate: float,
    seed: int,
) -> None:
    random.seed(seed)
    by_page: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for row in auto_rows:
        by_page[(str(row.get("file", "")), str(row.get("page", "")))].append(row)

    for page_rows in by_page.values():
        if page_rows:
            add_unique(quick_rows_by_key, dict(random.choice(page_rows)))

    rate = min(0.05, max(0.03, sample_rate))
    sample_size = int(round(len(auto_rows) * rate))
    if auto_rows and sample_size == 0:
        sample_size = 1
    for row in random.sample(auto_rows, min(sample_size, len(auto_rows))):
        add_unique(quick_rows_by_key, dict(row))


def examples(rows: list[dict[str, Any]], limit: int = 8) -> list[dict[str, Any]]:
    return [
        {
            "word": row.get("word", ""),
            "detected_count": row.get("detected_count", ""),
            "confidence": row.get("confidence", ""),
            "reason": row.get("filter_reason", ""),
            "file": row.get("file", ""),
            "page": row.get("page", ""),
            "line_index": row.get("line_index", ""),
        }
        for row in rows[:limit]
    ]


def main() -> int:
    args = parse_args()
    input_path = resolve_path(args.input)
    if not input_path.exists():
        print(f"Input CSV not found: {input_path}")
        return 1

    auto_output = resolve_path(args.auto_output)
    quick_output = resolve_path(args.quick_output)
    manual_output = resolve_path(args.manual_output)
    report_path = resolve_path(args.report)

    rows, fields = load_rows(input_path)
    vocab = load_json(VOCAB_PATH, [])
    frequency = load_json(FREQUENCY_PATH, {})
    known_words = {str(item.get("normalized_word", "")).strip().lower() for item in vocab}
    frequency_words = {str(word).strip().lower() for word in frequency}

    normalized_words = [normalize_word(str(row.get("word", ""))) for row in rows if normalize_word(str(row.get("word", "")))]
    occurrence_counts: Counter[str] = Counter(normalized_words)
    stats_by_page = page_line_stats(rows)

    auto_pool: list[tuple[dict[str, Any], dict[str, Any]]] = []
    quick_by_key: dict[tuple[str, str, str], dict[str, Any]] = {}
    manual_pool: list[tuple[dict[str, Any], dict[str, Any], str]] = []
    skipped_examples: list[dict[str, Any]] = []
    suspicious_counter: Counter[str] = Counter()
    skipped_empty_count = 0
    skipped_missing_count_count = 0
    invalid_count_count = 0
    suspicious_word_count = 0

    for row in rows:
        info = classify_base(row, known_words, frequency_words, occurrence_counts, stats_by_page)
        hard_reasons = list(dict.fromkeys(info["hard_reasons"]))
        soft_reasons = list(dict.fromkeys(info["soft_reasons"]))
        reason = ";".join(hard_reasons + soft_reasons)
        has_word = bool(info["word"])
        has_count = info["detected_count"] is not None

        if not has_word and not has_count:
            skipped_empty_count += 1
            if len(skipped_examples) < 8:
                skipped_examples.append(decorate_row(row, "skipped_empty", "skipped_empty", info))
            continue

        if "count_invalid_or_too_large" in hard_reasons:
            invalid_count_count += 1
        if any(
            item in hard_reasons
            for item in ["phrase_merge", "ocr_garbage_word", "suspect_ocr_word", "word_invalid_chars", "word_too_long"]
        ):
            suspicious_word_count += 1
            if info["normalized"]:
                suspicious_counter[info["normalized"]] += 1

        auto_ok = (
            has_word
            and has_count
            and not hard_reasons
            and info["detected_count"] is not None
            and 1 <= info["detected_count"] <= 30
            and 2 <= len(info["normalized"]) <= 22
            and meets_threshold(info["confidence"], args.min_confidence)
            and meets_threshold(info["word_confidence"], args.min_word_confidence)
            and meets_threshold(info["count_confidence"], args.min_count_confidence)
            and common_word_shape(info["normalized"], info["known"])
            and (
                info["known"]
                or occurrence_counts[info["normalized"]] >= 2
                or (info["detected_count"] or 0) <= 1
            )
        )

        if auto_ok:
            auto_pool.append((row, info))
            if info["detected_count"] and info["detected_count"] >= 10:
                quick_row = decorate_row(row, "quick_audit", "high_forget_count_backup", info)
                add_unique(quick_by_key, quick_row)
            continue

        quick_ok = (
            has_word
            and has_count
            and not any(
                item in hard_reasons
                for item in ["phrase_merge", "ocr_garbage_word", "suspect_ocr_word", "word_invalid_chars", "word_too_long"]
            )
            and info["detected_count"] is not None
            and 1 <= info["detected_count"] <= 30
            and common_word_shape(info["normalized"], info["known"])
            and (
                0.65 <= info["confidence"] < args.min_confidence
                or (info["word_confidence"] >= args.min_word_confidence and info["count_confidence"] >= 0.50)
                or (info["count_confidence"] >= args.min_count_confidence and info["word_confidence"] >= 0.65)
                or ((info["detected_count"] or 0) >= 3 and not info["known"])
                or info["detected_count"] >= 10
            )
        )
        if quick_ok:
            quick_reason = reason or "medium_confidence"
            add_unique(quick_by_key, decorate_row(row, "quick_audit", quick_reason, info))
            continue

        if has_word and not has_count:
            skipped_missing_count_count += 1
            if info["known"] or "phrase_merge" in hard_reasons or "ocr_garbage_word" in hard_reasons:
                manual_pool.append((row, info, reason or "word_without_count_but_worth_checking"))
            elif len(skipped_examples) < 8:
                skipped_examples.append(decorate_row(row, "skipped_missing_count", "skipped_missing_count_low_value", info))
            continue

        salvageable = (
            (has_count and not has_word)
            or (has_word and has_count)
            or bool(info["known"])
            or (info["detected_count"] or 0) >= 10
        )
        if salvageable:
            manual_pool.append((row, info, reason or "low_confidence_salvageable"))
        elif len(skipped_examples) < 8:
            skipped_examples.append(decorate_row(row, "skipped_low_value", reason or "skipped_low_value", info))

    auto_pool.sort(key=auto_priority, reverse=True)
    auto_rows = [
        decorate_row(row, "auto_merge", "auto_merge_candidate", info)
        for row, info in auto_pool[: max(0, args.max_auto_merge)]
    ]
    auto_keys = {row_key(row) for row in auto_rows}

    sample_auto_rows(auto_rows, quick_by_key, args.quick_audit_rate, args.seed)
    for key, row in list(quick_by_key.items()):
        if key in auto_keys:
            row["candidate_level"] = "quick_audit"
            row["needs_review"] = "True"
            if not str(row.get("filter_reason", "")):
                row["filter_reason"] = "auto_merge_random_audit"

    manual_pool.sort(key=manual_priority, reverse=True)
    manual_rows = [
        decorate_row(row, "manual_review", reason, info)
        for row, info, reason in manual_pool[: max(0, args.max_manual_review)]
    ]
    quick_rows = list(quick_by_key.values())

    write_csv(auto_output, fields, auto_rows)
    write_csv(quick_output, fields, quick_rows)
    write_csv(manual_output, fields, manual_rows)

    total_rows = len(rows)
    recognized_word_rows = sum(1 for row in rows if str(row.get("word", "")).strip())
    average_confidence = (
        sum(parse_float(row.get("confidence")) for row in rows) / total_rows if total_rows else 0.0
    )
    report = {
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "input": str(input_path.relative_to(PROJECT_ROOT) if input_path.is_relative_to(PROJECT_ROOT) else input_path),
        "total_rows": total_rows,
        "recognized_word_rows": recognized_word_rows,
        "auto_merge_count": len(auto_rows),
        "quick_audit_count": len(quick_rows),
        "manual_review_count": len(manual_rows),
        "manual_review_overflow_count": max(0, len(manual_pool) - len(manual_rows)),
        "skipped_empty_count": skipped_empty_count,
        "skipped_missing_count_count": skipped_missing_count_count,
        "suspicious_word_count": suspicious_word_count,
        "invalid_count_count": invalid_count_count,
        "average_confidence": round(average_confidence, 3),
        "confidence_threshold_tolerance": CONFIDENCE_TOLERANCE,
        "auto_merge_ratio": round(len(auto_rows) / total_rows, 3) if total_rows else 0,
        "manual_review_ratio": round(len(manual_rows) / total_rows, 3) if total_rows else 0,
        "examples_auto_merge": examples(auto_rows),
        "examples_quick_audit": examples(quick_rows),
        "examples_manual_review": examples(manual_rows),
        "examples_skipped": examples(skipped_examples),
        "top_suspicious_words": [
            {"word": word, "count": count}
            for word, count in suspicious_counter.most_common(30)
        ],
        "outputs": {
            "auto_merge_candidates": str(auto_output.relative_to(PROJECT_ROOT)),
            "quick_audit_candidates": str(quick_output.relative_to(PROJECT_ROOT)),
            "manual_review_candidates": str(manual_output.relative_to(PROJECT_ROOT)),
        },
    }
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    print(f"Total rows: {total_rows}")
    print(f"Recognized word rows: {recognized_word_rows}")
    print(f"Auto-merge candidates: {len(auto_rows)}")
    print(f"Quick-audit candidates: {len(quick_rows)}")
    print(f"Manual-review candidates: {len(manual_rows)}")
    print(f"Skipped empty rows: {skipped_empty_count}")
    print(f"Skipped missing-count rows: {skipped_missing_count_count}")
    print(f"Suspicious word rows: {suspicious_word_count}")
    print(f"Report: {report_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
