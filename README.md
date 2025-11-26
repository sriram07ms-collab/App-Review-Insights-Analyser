## App Review Insights Analyzer

Pipeline that ingests roughly the last six months (default 180-day lookback) of Groww Play Store reviews (Layer 1), tags them into ≤5 fixed themes (Layer 2), and generates weekly one-page pulses with top insights, quotes, and actions (Layer 3).

---

### 1. Prerequisites

- Python 3.10+
- Google Gemini API key (free tier works)
- Internet access to Google Play + Gemini endpoints

---

### 2. Setup

```bash
python -m venv .venv
.venv\Scripts\activate        # PowerShell / cmd
pip install -r requirements.txt
python -m playwright install chromium
copy config\.env.example .env
```

Fill `.env` with:

- `GEMINI_API_KEY`
- Optional overrides (see `.env.example`) such as `PLAY_STORE_APP_ID`, `SCRAPER_OUTPUT_DIR`, `REVIEW_LOOKBACK_DAYS`.
- Layer 3 knobs (chunk sizes, word limits, cache toggles, alternate Gemini models) if you need non-default behaviour:
  - `LAYER3_OUTPUT_DIR`, `LAYER3_CHUNK_SIZE`, `LAYER3_MAX_KEY_POINTS`, `LAYER3_MAX_QUOTES_PER_THEME`, `LAYER3_MAX_THEMES`, `LAYER3_MIN_REVIEWS`, `LAYER3_MAX_WORDS`
  - `LAYER3_ENABLE_CACHE`, `LAYER3_CACHE_PATH`
  - `LAYER3_MAP_MODEL_NAME`, `LAYER3_REDUCE_MODEL_NAME`
- Scraper fallbacks for tougher coverage:
  - `SCRAPER_MAX_SCROLLS`, `SCRAPER_PER_RATING_TARGET`
  - `SCRAPER_SLICE_DAYS` to control how many days each automatic slice spans (default 7)
  - `SCRAPER_ENABLE_RATING_FILTERS` / `SCRAPER_RATING_FILTER_SEQUENCE` (e.g., `5,4,3,2,1`) to force per-rating passes through the Play Store UI
  - `PLAY_STORE_SORT_MODE`
  - `PLAY_STORE_SORT_FALLBACKS` (comma-separated, e.g., `highest_rating,lowest_rating`) to automatically re-run the scrape with alternate sort orders until each rating bucket fills up.
- Layer 4 email delivery:
  - `EMAIL_TRANSPORT` (`smtp` or `gmail`), `EMAIL_DRY_RUN`
  - SMTP envs: `SMTP_HOST`, `SMTP_PORT`, `SMTP_USER`, `SMTP_PASSWORD`, `SMTP_USE_TLS`
  - Gmail envs: `GMAIL_USER`, `GMAIL_CREDENTIALS_PATH`, `GMAIL_TOKEN_PATH` (after enabling Gmail API and running the OAuth consent flow once)

---

### 3. Running locally

Fetch the default 8–12 week window ending last week:

```bash
python main.py
```

Override dates or runtime parameters as needed:

```bash
python main.py ^
  --start-date 2025-08-01 ^
  --end-date 2025-10-15 ^
  --max-reviews 1000 ^
  --max-scrolls 600 ^
  --per-rating-target 20 ^
  --sort-mode newest ^
  --cron-tag "manual-rerun" ^
  --window-slices 2025-05-01:2025-07-31,2025-08-01:2025-10-31
```

**Outputs**

- Raw batch: `data/raw/groww_reviews_<start>_<end>.json`
- Weekly buckets: `data/raw/weekly/week_<YYYY-MM-DD>.json`
- Theme aggregation: `data/processed/theme_aggregation.json`
- Review classifications: `data/processed/review_classifications.json`
- Weekly pulse notes: `data/processed/weekly_pulse/pulse_<YYYY-MM-DD>.json`
- Markdown render: `data/processed/weekly_pulse/pulse_<YYYY-MM-DD>.md`

---

### 4. Scheduling weekly runs

Example cron (Linux) for Mondays 9 AM IST (03:30 UTC):

```
30 3 * * 1  cd /path/to/Milestone-2 && .venv/bin/python main.py --cron-tag "mon-09-ist"
```

Zapier / workflow engines can call the same command line; use `--start-date/--end-date` if a run is missed. For broad coverage, keep `REVIEW_LOOKBACK_DAYS` at ~180, set a high scroll budget (`SCRAPER_MAX_SCROLLS`), and let the built-in sort fallbacks iterate through `highest_rating` / `lowest_rating` to fill thin rating buckets. You can also union multiple explicit time slices with `--window-slices START:END,...` to stitch together six-plus months at once. The scraper auto-stops once each rating bucket meets `SCRAPER_PER_RATING_TARGET` (default 50); otherwise it logs which ratings were short before Layer 2/3 continue.

---

### 5. Next steps

1. Layer 4 email drafting (tone prompt + SMTP/Gmail API send).
2. Add richer analytics/QA dashboards for weekly pulses.
3. Optional: telemetry/alerts for scraper failures or empty windows.

