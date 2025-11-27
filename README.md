## App Review Insights Analyzer

App Review Insights Analyzer turns the last 8 weeks of public Play Store reviews into a weekly one-page pulse. The system ingests reviews without logins, deduplicates and sanitizes them, groups the feedback into up to five product themes, surfaces the strongest insights and representative user quotes, and proposes concrete actions. Each weekly pulse is then converted into a draft email so stakeholders can consume the note directly in their inbox—while respecting public-data-only constraints and aggressively stripping any PII. This milestone showcases applied LLM orchestration, summarization, theme grouping, and workflow automation working end-to-end on live data.

### Project Architecture

1. **Layer 1 – Ingestion & Cleaning**  
   - HTTP scraper hits the Play Store `batchexecute` endpoint using staged window slices to gather 8 weeks of reviews across star ratings.  
   - Enforces per-rating targets, deduplicates IDs, removes short/empty texts, normalizes whitespace, and strips obvious PII before any LLM call.  
   - Outputs weekly JSON buckets for downstream processing.

2. **Layer 2 – Theme Classification**  
   - Gemini-based classifier maps each review into ≤5 predefined themes (`ui_ux`, `glitches`, `payments_statements`, etc.).  
   - Aggregates counts, example quotes, and representative actions per theme.

3. **Layer 3 – Weekly Pulse Generation**  
   - Loads each weekly bucket (requires ≥3 reviews), builds map/reduce prompts, and composes a one-page Markdown note with title, overview, key themes, quotes, and action ideas.  
   - Hardened JSON parsing handles Gemini finish reasons and malformed payloads.

4. **Layer 4 – Email Drafting & Delivery**  
   - Sanitizes the weekly note (emoji removal, sensitive-language masking).  
   - Drafts the email body via Gemini with retries and fallback templates, runs regex + LLM-based PII scrubbing, and sends via Gmail API or SMTP.  
   - Logs every send (or dry run) in `data/processed/email_logs.csv`.

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
- Layer 2 theme discovery (hybrid classification):
  - `THEME_DISCOVERY_ENABLED` (default: `true`) - Enable/disable LLM-based theme discovery
  - `THEME_DISCOVERY_SAMPLE_SIZE` (default: `50`) - Number of reviews to sample for discovery
  - `THEME_DISCOVERY_MIN_CONFIDENCE` (default: `0.6`) - Minimum mapping confidence to use discovered theme
  - `THEME_DISCOVERY_MAX_THEMES` (default: `4`) - Maximum number of discovered themes (top 4)
  - `THEME_DISCOVERY_MODEL` (optional) - Gemini model for discovery (default: `models/gemini-2.5-flash`)
- Layer 4 email delivery:
  - `EMAIL_TRANSPORT` (`smtp` or `gmail`), `EMAIL_DRY_RUN`
  - SMTP envs: `SMTP_HOST`, `SMTP_PORT`, `SMTP_USER`, `SMTP_PASSWORD`, `SMTP_USE_TLS`
  - Gmail envs: `GMAIL_USER`, `GMAIL_CREDENTIALS_PATH`, `GMAIL_TOKEN_PATH` (after enabling Gmail API and running the OAuth consent flow once)

---

### 3. Running locally

Fetch the default 8 week window ending last week:

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
  --per-rating-target 50 ^
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

### 4. Sample Outputs

#### Latest Weekly Pulse Note

**Week: November 17-23, 2025** ([Full Markdown](data/processed/weekly_pulse/pulse_2025-11-17.md))

```markdown
# Product Pulse: November 17-23, 2025

This week's pulse identifies critical issues with app stability, causing login
failures and feature inaccessibility. Payments experienced challenges with
non-functional Autopay and extended withdrawal times for urgent needs.

## Themes
- **Slow, Glitches** - Users reported significant app instability and login
  failures, severely hindering access to features like Digi Gold investment
  for multiple days.
- **UI/UX** - Though generally user-friendly, a critical flaw in the
  drag-and-drop system is causing users to miss trades due to required manual input.
- **Payments/Statements** - Critical payment functionalities are failing,
  with Autopay repeatedly unsuccessful and withdrawal processing times deemed
  excessively long during urgent situations.

## Quotes
- "Not working since last 5 days (Slow, Glitches)"
- "pls update drag and drop system in target and stop manual type karne jaye
  hai to trade miss ho jata hai (UI/UX)"
- "Withdrawal time is too long, It's an emergency right now and we have to
  wait for 4 days.😡 (Payments/Statements)"

## Actions
- Prioritize investigation and resolution of core app stability, login failures,
  and feature accessibility (e.g., Digi Gold).
- Enhance the drag-and-drop trading interface to prevent manual input errors
  and ensure trade execution without delays.
- Address Autopay functionality failures and optimize withdrawal processing
  times to meet user expectations, especially for urgent needs.
```

#### Email Draft Example

**Subject:** `Weekly Product Pulse – Groww App (2025-11-17–2025-11-23)`

**Body (sample):**
```
Groww App Weekly Pulse | 2025-11-17 – 2025-11-23

Title: Critical Stability and Payment Issues Impact User Experience
Overview: This week's pulse identifies critical issues with app stability,
causing login failures and feature inaccessibility. Payments experienced
challenges with non-functional Autopay and extended withdrawal times.

Top Themes:
- Slow, Glitches: Users reported significant app instability and login failures
- UI/UX: Critical flaw in drag-and-drop system causing missed trades
- Payments/Statements: Autopay failures and excessive withdrawal processing times

Representative Quotes:
- "Not working since last 5 days"
- "pls update drag and drop system in target and stop manual type karne jaye
  hai to trade miss ho jata hai"
- "Withdrawal time is too long, It's an emergency right now and we have to
  wait for 4 days"

Action Ideas:
- Prioritize investigation and resolution of core app stability and login failures
- Enhance the drag-and-drop trading interface to prevent manual input errors
- Address Autopay functionality failures and optimize withdrawal processing times

Reply to this email if you need deeper dives or clarifications.
```

*Note: Email drafts are generated by Gemini LLM with PII scrubbing and fallback
templates. Full email logs are available in `data/processed/email_logs.csv`.*

#### Reviews Data Sample (Redacted)

Sample from `data/raw/groww_reviews_2025-11-04_2025-11-18.json`:

```json
{
  "reviews": [
    {
      "review_id": "6740d4c1-8ae1-4b59-a6ad-64d5ed963560",
      "title": "Customer Review",
      "text": "worse customer support services please don't get fool by this groww app",
      "rating": 1,
      "date": "2025-11-10T17:33:02+00:00",
      "author": "User"
    },
    {
      "review_id": "cffa1d4d-8a48-4b5a-b1a8-ef07bb30987b",
      "title": "Customer Review",
      "text": "to good 👍",
      "rating": 5,
      "date": "2025-11-10T16:59:52+00:00",
      "author": "User"
    }
  ]
}
```

*Note: Author names and PII are redacted in this sample. Full reviews include
original author names (anonymized in email outputs).*

---
