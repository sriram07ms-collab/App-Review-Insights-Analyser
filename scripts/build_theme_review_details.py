import json
from pathlib import Path
from typing import Any, Dict, List


RAW_WEEKLY_DIR = Path("data/raw/weekly")
CLASSIFICATIONS_PATH = Path("data/processed/review_classifications.json")
OUTPUT_PATH = Path("data/processed/theme_review_details.json")


def load_raw_reviews() -> Dict[str, Dict[str, Any]]:
    """Load all raw weekly reviews keyed by review_id."""
    reviews_by_id: Dict[str, Dict[str, Any]] = {}

    if not RAW_WEEKLY_DIR.exists():
        print(f"Raw weekly directory not found: {RAW_WEEKLY_DIR}")
        return reviews_by_id

    for path in sorted(RAW_WEEKLY_DIR.glob("week_*.json")):
        try:
            with path.open("r", encoding="utf-8") as f:
                items = json.load(f)
        except Exception as exc:
            print(f"Failed to load {path}: {exc}")
            continue

        for item in items:
            rid = item.get("review_id")
            if not rid:
                continue
            reviews_by_id[rid] = item

    return reviews_by_id


def build_theme_review_details() -> List[Dict[str, Any]]:
    """Merge theme classifications with raw review text/metadata."""
    if not CLASSIFICATIONS_PATH.exists():
        print(f"Classification file not found: {CLASSIFICATIONS_PATH}")
        return []

    with CLASSIFICATIONS_PATH.open("r", encoding="utf-8") as f:
        classifications = json.load(f)

    reviews_by_id = load_raw_reviews()
    merged: List[Dict[str, Any]] = []

    for cls in classifications:
        rid = cls.get("review_id")
        if not rid:
            continue

        raw = reviews_by_id.get(rid)
        if not raw:
            # No matching raw review (can happen if windows changed)
            continue

        merged.append(
            {
                "review_id": rid,
                "theme_id": cls.get("theme_id"),
                "theme_name": cls.get("theme_name"),
                "reason": cls.get("reason"),
                "text": raw.get("text"),
                "rating": raw.get("rating"),
                "date": raw.get("date"),
                "author": raw.get("author"),
                "title": raw.get("title"),
                "week_start_date": raw.get("week_start_date"),
                "week_end_date": raw.get("week_end_date"),
            }
        )

    return merged


def main() -> None:
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    merged = build_theme_review_details()
    with OUTPUT_PATH.open("w", encoding="utf-8") as f:
        json.dump(merged, f, ensure_ascii=False, indent=2)
    print(f"Wrote {len(merged)} merged theme review records to {OUTPUT_PATH}")


if __name__ == "__main__":
    main()


