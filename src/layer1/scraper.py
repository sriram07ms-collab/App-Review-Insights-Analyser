"""
Utilities for fetching public Groww app reviews from the Google Play Store.

Primary flow:
1. Determine the weekly date window (default: last 8–12 weeks ending last week).
2. Call the public Play Store `batchexecute` endpoint (no login, no private API) or fall back to a fixture.
3. Filter by date range and emit structured review records ready for validation.
4. Persist raw batches under `data/raw/` (plus weekly buckets) for downstream processing.
"""

from __future__ import annotations

import json
import logging
import re
from collections import defaultdict
from dataclasses import asdict, dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Iterable, List, Optional, Tuple

import requests
from bs4 import BeautifulSoup
from dateutil import parser as date_parser

LOGGER = logging.getLogger(__name__)


@dataclass(slots=True)
class ScraperConfig:
    """Runtime configuration for pulling Google Play reviews."""

    app_id: str
    locale: str = "en"
    country: str = "in"
    lookback_days: int = 28  # 4 weeks
    min_offset_days: int = 7  # skip current-week noise
    max_reviews: int = 2000
    max_scroll_iterations: int = 1000
    scroll_wait_ms: int = 1500
    per_rating_target: int = 20
    output_dir: Path = field(default_factory=lambda: Path("data/raw"))
    weekly_output_dir: Path = field(default_factory=lambda: Path("data/raw/weekly"))
    headless: bool = True
    playwright_browser: str = "chromium"
    sort_mode: str = "newest"
    html_fixture_path: Optional[Path] = None
    fallback_sort_modes: Tuple[str, ...] = field(default_factory=tuple)
    enable_rating_filters: bool = False
    rating_filter_order: Tuple[int, ...] = field(default_factory=lambda: (5, 4, 3, 2, 1))

    def date_window(
        self,
        reference_date: Optional[datetime] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
    ) -> Tuple[datetime, datetime]:
        """
        Compute the target time window. Direct overrides take precedence over lookback logic.
        
        Ensures the last 7 days are always included. For example, if run on Dec 8,
        it will produce data for Nov 30 to Dec 7 (the previous week).
        """
        if start_date and end_date:
            start = _ensure_utc(start_date)
            end = _ensure_utc(end_date)
            if start > end:
                raise ValueError("start_date must be before end_date")
            return start, end

        if reference_date is None:
            reference_date = datetime.now(timezone.utc)
        reference_date = _ensure_utc(reference_date)

        # Always use the last COMPLETE day as the end of the window (yesterday)
        # Example: run on Dec 1 → end_date = Nov 30 23:59:59.999
        end_date = reference_date - timedelta(days=1)
        end_date = end_date.replace(hour=23, minute=59, second=59, microsecond=999999)

        # Start is 6 days before end, at start-of-day → exact 7‑day window
        # Example: end_date Nov 30 → start_date Nov 24 00:00:00
        start_date = end_date - timedelta(days=6)
        start_date = start_date.replace(hour=0, minute=0, second=0, microsecond=0)

        return start_date, end_date


@dataclass(slots=True)
class ReviewRecord:
    """Structured representation of a single Play Store review."""

    review_id: str
    title: str
    text: str
    rating: int
    date: datetime
    author: Optional[str] = None
    product_tag: Optional[str] = None

    def week_bucket(self) -> Tuple[datetime, datetime]:
        """Return a tuple of (week_start, week_end) for bucketing downstream."""
        week_start = datetime(self.date.year, self.date.month, self.date.day, tzinfo=timezone.utc)
        week_start -= timedelta(days=week_start.weekday())  # align to Monday
        week_end = week_start + timedelta(days=6)
        return week_start, week_end


@dataclass(slots=True)
class FetchStats:
    """Return type for Playwright fetches (records plus per-rating counts)."""

    records: List[ReviewRecord]
    rating_counts: dict[int, int]
    sort_mode: str


class GrowwReviewScraper:
    """
    Wrapper around an HTTP-based scraper that calls the public Play Store endpoint
    and extracts review content without authentication.
    """

    def __init__(self, config: ScraperConfig) -> None:
        self.config = config
        self._fetcher = PlayStoreReviewFetcher(config)

    def fetch_reviews(
        self,
        reference_date: Optional[datetime] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
    ) -> List[ReviewRecord]:
        """
        Pull reviews within the configured time window.
        """
        window_start, window_end = self.config.date_window(reference_date, start_date, end_date)
        LOGGER.info(
            "Fetching reviews for %s between %s and %s",
            self.config.app_id,
            window_start.isoformat(),
            window_end.isoformat(),
        )

        sort_sequence = self._build_sort_sequence()
        combined_records: dict[str, ReviewRecord] = {}
        rating_counts = self._empty_rating_counts()

        for mode in sort_sequence:
            stats = self._fetcher.fetch(window_start, window_end, sort_mode=mode)
            new_records = 0
            for record in stats.records:
                if record.review_id not in combined_records:
                    combined_records[record.review_id] = record
                    new_records += 1
                    if len(combined_records) >= self.config.max_reviews:
                        LOGGER.info("Reached max_reviews (%s); stopping collection.", self.config.max_reviews)
                        break
            filtered = self._fetcher._filter_by_window(
                list(combined_records.values()), window_start, window_end
            )
            rating_counts = self._fetcher._count_by_rating(filtered)
            LOGGER.info(
                "Sort '%s' added %s new reviews (%s total unique). Rating counts=%s",
                mode,
                new_records,
                len(filtered),
                rating_counts,
            )
            if self._fetcher._targets_met(rating_counts):
                LOGGER.info("Per-rating targets met after sort '%s'.", mode)
                break
        else:
            LOGGER.warning("Per-rating targets unmet after fallbacks: %s", rating_counts)

        filtered_records = self._fetcher._filter_by_window(
            list(combined_records.values()), window_start, window_end
        )
        limited_records = self._fetcher._limit_per_rating(filtered_records)
        LOGGER.info("Collected %s reviews in range.", len(limited_records))
        return sorted(limited_records, key=lambda r: r.date, reverse=True)

    def _build_sort_sequence(self) -> List[str]:
        seen: set[str] = set()
        sequence: List[str] = []
        for candidate in [self.config.sort_mode, *self.config.fallback_sort_modes]:
            normalized = (candidate or "").strip().lower()
            if not normalized or normalized in seen:
                continue
            seen.add(normalized)
            sequence.append(normalized)
        if not sequence:
            sequence.append("newest")
        return sequence

    @staticmethod
    def _empty_rating_counts() -> dict[int, int]:
        return {score: 0 for score in range(1, 6)}

    def save_reviews(
        self,
        reviews_list: Iterable[ReviewRecord],
        reference_date: Optional[datetime] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
    ) -> Path:
        """
        Persist the given reviews under data/raw with a filename containing the window.
        Also writes week-level buckets for downstream processing.
        """
        window_start, window_end = self.config.date_window(reference_date, start_date, end_date)
        self.config.output_dir.mkdir(parents=True, exist_ok=True)
        filename = (
            f"groww_reviews_{window_start.date().isoformat()}_{window_end.date().isoformat()}.json"
        )
        output_path = self.config.output_dir / filename
        payload = [self._serialise_record(record) for record in reviews_list]
        with output_path.open("w", encoding="utf-8") as fh:
            json.dump(payload, fh, ensure_ascii=False, indent=2, default=str)
        LOGGER.info("Saved %s reviews to %s", len(payload), output_path)

        self._save_weekly_buckets(reviews_list)
        return output_path

    def _save_weekly_buckets(self, reviews_list: Iterable[ReviewRecord]) -> None:
        weekly_groups: defaultdict[str, List[ReviewRecord]] = defaultdict(list)
        for record in reviews_list:
            week_start, _ = record.week_bucket()
            weekly_groups[week_start.date().isoformat()].append(record)

        if not weekly_groups:
            return

        weekly_dir = self.config.weekly_output_dir
        weekly_dir.mkdir(parents=True, exist_ok=True)
        for week_key, records in weekly_groups.items():
            week_start, week_end = records[0].week_bucket()
            serialized = []
            for r in records:
                payload = self._serialise_record(r)
                payload["week_start_date"] = week_start.date().isoformat()
                payload["week_end_date"] = week_end.date().isoformat()
                serialized.append(payload)
            file_path = weekly_dir / f"week_{week_key}.json"
            with file_path.open("w", encoding="utf-8") as fh:
                json.dump(serialized, fh, ensure_ascii=False, indent=2)
            LOGGER.info("Wrote %s reviews to %s", len(serialized), file_path)

    @staticmethod
    def _serialise_record(record: ReviewRecord) -> dict:
        """Convert dataclass into JSON-friendly dict."""
        serialised = asdict(record)
        serialised["date"] = record.date.isoformat()
        if record.product_tag is None:
            serialised.pop("product_tag", None)
        if record.author is None:
            serialised.pop("author", None)
        return serialised


class PlayStoreReviewFetcher:
    """Fetches reviews from the public Play Store batchexecute endpoint."""

    REVIEWS_SELECTOR = "[data-review-id]"
    BASE_URL = "https://play.google.com/_/PlayStoreUi/data/batchexecute"
    RPC_ID = "UsvDTd"
    MAX_PAGE_SIZE = 199
    SORT_CODES = {
        "newest": 2,
        "most_relevant": 1,
    }
    RESPONSE_PATTERN = re.compile(r"\)\]\}'\n\n(.+)", re.DOTALL)
    PAYLOAD_FIRST_PAGE = (
        "f.req=%5B%5B%5B%22UsvDTd%22%2C%22%5Bnull%2Cnull%2C%5B2%2C{sort}%2C%5B{count}%2Cnull%2Cnull%5D%2Cnull%2C%5Bnull%2C{score}%5D%5D%2C%5B%5C%22{app_id}%5C%22%2C7%5D%5D%22%2Cnull%2C%22generic%22%5D%5D%5D"
    )
    PAYLOAD_PAGINATED_PAGE = (
        "f.req=%5B%5B%5B%22UsvDTd%22%2C%22%5Bnull%2Cnull%2C%5B2%2C{sort}%2C%5B{count}%2Cnull%2C%5C%22{token}%5C%22%5D%2Cnull%2C%5Bnull%2C{score}%5D%5D%2C%5B%5C%22{app_id}%5C%22%2C7%5D%5D%22%2Cnull%2C%22generic%22%5D%5D%5D"
    )

    def __init__(self, config: ScraperConfig) -> None:
        self.config = config
        self._session = requests.Session()

    def fetch(
        self,
        window_start: datetime,
        window_end: datetime,
        sort_mode: Optional[str] = None,
        rating_filter: Optional[int] = None,
    ) -> FetchStats:
        if self.config.html_fixture_path:
            return self._fetch_from_fixture(
                window_start, window_end, sort_mode or self.config.sort_mode
            )

        active_sort_mode = (sort_mode or self.config.sort_mode or "newest").lower()
        sort_code = self.SORT_CODES.get(active_sort_mode, self.SORT_CODES["newest"])
        max_reviews = self.config.max_reviews

        collected: List[ReviewRecord] = []
        seen_ids: set[str] = set()
        rating_counts = self._empty_rating_counts()
        next_token: Optional[str] = None

        while len(collected) < max_reviews:
            batch_size = min(self.MAX_PAGE_SIZE, max_reviews - len(collected))
            page_records, next_token = self._fetch_page(
                sort_code=sort_code,
                count=batch_size,
                rating_filter=rating_filter,
                page_token=next_token,
            )
            if not page_records:
                break

            for record in page_records:
                if record.review_id in seen_ids:
                    continue
                if record.date > window_end:
                    continue
                seen_ids.add(record.review_id)
                collected.append(record)
                if 1 <= record.rating <= 5:
                    rating_counts[record.rating] += 1

            if self._targets_met(rating_counts):
                LOGGER.info("Per-rating targets met; stopping fetch.")
                break

            if not next_token:
                break

        filtered = self._filter_by_window(collected, window_start, window_end)
        rating_counts = self._count_by_rating(filtered)
        limited = self._limit_per_rating(filtered)
        return FetchStats(limited, rating_counts, active_sort_mode)

    def _build_url(self) -> str:
        return f"{self.BASE_URL}?hl={self.config.locale}&gl={self.config.country}"

    def _headers(self) -> dict:
        return {
            "content-type": "application/x-www-form-urlencoded;charset=UTF-8",
            "origin": "https://play.google.com",
            "referer": "https://play.google.com/",
            "user-agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0 Safari/537.36"
            ),
            "x-same-domain": "1",
        }

    def _build_body(
        self,
        sort_code: int,
        count: int,
        rating_filter: Optional[int],
        page_token: Optional[str],
    ) -> bytes:
        filter_value = (
            "null" if rating_filter not in {1, 2, 3, 4, 5} else str(int(rating_filter))
        )
        if page_token:
            # Page tokens may contain characters that need escaping inside the payload.
            escaped_token = json.dumps(page_token)[1:-1]
            payload = self.PAYLOAD_PAGINATED_PAGE.format(
                sort=sort_code,
                count=count,
                score=filter_value,
                app_id=self.config.app_id,
                token=escaped_token,
            )
        else:
            payload = self.PAYLOAD_FIRST_PAGE.format(
                sort=sort_code,
                count=count,
                score=filter_value,
                app_id=self.config.app_id,
            )
        return payload.encode("utf-8")

    def _fetch_page(
        self,
        sort_code: int,
        count: int,
        rating_filter: Optional[int],
        page_token: Optional[str],
    ) -> Tuple[List[ReviewRecord], Optional[str]]:
        try:
            resp = self._session.post(
                self._build_url(),
                data=self._build_body(sort_code, count, rating_filter, page_token),
                headers=self._headers(),
                timeout=30,
            )
            resp.raise_for_status()
        except requests.RequestException as exc:
            LOGGER.warning("Play Store request failed: %s", exc)
            return [], None

        reviews_raw, token = self._parse_response(resp.text)
        records = [self._record_from_raw(item) for item in reviews_raw]
        records = [record for record in records if record is not None]

        if isinstance(token, str) and token:
            next_token = token
        else:
            next_token = None

        return records, next_token

    def _parse_response(self, payload: str) -> Tuple[List[list], Optional[str]]:
        match = self.RESPONSE_PATTERN.search(payload)
        if not match:
            LOGGER.warning("Unexpected Play Store payload; skipping batch.")
            return [], None

        outer = json.loads(match.group(1))
        if not outer or len(outer[0]) < 3:
            return [], None

        try:
            inner = json.loads(outer[0][2])
        except (ValueError, TypeError):
            LOGGER.warning("Unable to decode Play Store batch payload.")
            return [], None

        reviews = inner[0] if inner else []
        next_token: Optional[str] = None
        try:
            next_token = inner[-1][-1]
        except (IndexError, TypeError):
            next_token = None

        return reviews, next_token

    def _record_from_raw(self, raw: list) -> Optional[ReviewRecord]:
        try:
            review_id = raw[0]
            user_name = (raw[1][0] or "").strip()
            rating = int(raw[2])
            text = raw[4] or ""
            timestamp_info = raw[5]
            timestamp = timestamp_info[0]
        except (IndexError, TypeError, ValueError):
            return None

        if not review_id or not timestamp:
            return None

        review_date = datetime.fromtimestamp(timestamp, tz=timezone.utc)
        title = user_name or text[:80]

        return ReviewRecord(
            review_id=review_id,
            title=title or "Play Store Review",
            text=text,
            rating=rating,
            date=review_date,
            author=user_name or None,
            product_tag=None,
        )

    def _targets_met(self, rating_counts: dict[int, int]) -> bool:
        target = self.config.per_rating_target
        if target <= 0:
            return True
        return all(count >= target for count in rating_counts.values())

    def _filter_by_window(
        self,
        collected: Iterable[ReviewRecord],
        window_start: datetime,
        window_end: datetime,
    ) -> List[ReviewRecord]:
        return [record for record in collected if window_start <= record.date <= window_end]

    def _limit_per_rating(self, records: List[ReviewRecord]) -> List[ReviewRecord]:
        if self.config.per_rating_target <= 0:
            return sorted(records, key=lambda r: r.date, reverse=True)

        per_rating_remaining = {score: self.config.per_rating_target for score in range(1, 6)}
        selected: List[ReviewRecord] = []
        for record in sorted(records, key=lambda r: r.date, reverse=True):
            rating = min(max(record.rating, 1), 5)
            if per_rating_remaining[rating] > 0:
                selected.append(record)
                per_rating_remaining[rating] -= 1
            if all(value == 0 for value in per_rating_remaining.values()):
                break

        for rating, remaining in per_rating_remaining.items():
            if remaining > 0:
                LOGGER.warning(
                    "Only %s reviews available for rating %s within window.",
                    self.config.per_rating_target - remaining,
                    rating,
                )
        return selected

    @staticmethod
    def _count_by_rating(records: Iterable[ReviewRecord]) -> dict[int, int]:
        counts = {score: 0 for score in range(1, 6)}
        for record in records:
            rating = min(max(record.rating, 1), 5)
            counts[rating] += 1
        return counts

    @staticmethod
    def _empty_rating_counts() -> dict[int, int]:
        return {score: 0 for score in range(1, 6)}

    def _fetch_from_fixture(
        self,
        window_start: datetime,
        window_end: datetime,
        sort_mode: str,
    ) -> FetchStats:
        fixture_path = self.config.html_fixture_path
        if not fixture_path:
            return FetchStats([], self._empty_rating_counts(), sort_mode)
        try:
            html = fixture_path.read_text(encoding="utf-8")
        except OSError as exc:
            LOGGER.error("Unable to read fixture HTML at %s: %s", fixture_path, exc)
            return FetchStats([], self._empty_rating_counts(), sort_mode)

        soup = BeautifulSoup(html, "html.parser")
        collected: List[ReviewRecord] = []
        seen_ids: set[str] = set()
        for card in soup.select(self.REVIEWS_SELECTOR):
            review_id = card.get("data-review-id")
            if not review_id or review_id in seen_ids:
                continue
            record = self._build_record_from_soup(card)
            if record is None:
                continue
            seen_ids.add(review_id)
            collected.append(record)
        filtered = self._filter_by_window(collected, window_start, window_end)
        counts = self._count_by_rating(filtered)
        return FetchStats(filtered, counts, sort_mode)

    @staticmethod
    def _build_record_from_soup(card) -> Optional[ReviewRecord]:
        review_id = card.get("data-review-id")
        if not review_id:
            return None

        def _text(selector: str) -> str:
            node = card.select_one(selector)
            return node.get_text(" ", strip=True) if node else ""

        title = _text(".X5PpBb")
        text = _text(".h3YV2d")
        if not text:
            text = _text(".UD7Dzf")

        date_str = _text(".bp9Aid") or _text(".p2TkOb")
        review_date = _parse_date(date_str)
        if not review_date:
            return None

        rating_node = card.select_one(".iXRFPc")
        rating_attr = rating_node.get("aria-label") if rating_node else None
        rating = _parse_rating(rating_attr)

        author = _text(".X43Kjb")
        product_tag = _text(".g1rdde")

        if not title:
            title = text[:80]

        return ReviewRecord(
            review_id=review_id,
            title=title,
            text=text,
            rating=rating,
            date=review_date,
            author=author or None,
            product_tag=product_tag or None,
        )
def compute_weekly_buckets(reviews_list: Iterable[ReviewRecord]) -> List[dict]:
    """
    Group reviews by ISO calendar week for downstream batching.

    Returns:
        List of dictionaries with week metadata and review IDs.
    """
    buckets = {}
    for record in reviews_list:
        week_start, week_end = record.week_bucket()
        key = week_start.date().isoformat()
        buckets.setdefault(
            key,
            {
                "week_start": week_start.date().isoformat(),
                "week_end": week_end.date().isoformat(),
                "review_ids": [],
            },
        )
        buckets[key]["review_ids"].append(record.review_id)
    return list(buckets.values())


def _ensure_utc(dt: datetime) -> datetime:
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def _parse_date(value: Optional[str]) -> Optional[datetime]:
    if not value:
        return None
    try:
        parsed = date_parser.parse(value)
    except (ValueError, TypeError):
        return None
    return _ensure_utc(parsed)


def _parse_rating(aria_label: Optional[str]) -> int:
    if not aria_label:
        return 0
    for token in aria_label.split():
        if token.isdigit():
            return int(token)
    return 0

