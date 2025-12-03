## App Review Insights Analyzer

App Review Insights Analyzer turns recent public Play Store reviews into a weekly one-page product pulse. The system ingests reviews without logins, deduplicates and sanitizes them, groups the feedback into product themes, surfaces the strongest insights and representative user quotes, and proposes concrete actions. Each weekly pulse is then converted into a draft email so stakeholders can consume the note directly in their inbox—while respecting public-data-only constraints and aggressively stripping any PII. This milestone showcases applied LLM orchestration, summarization, theme grouping, and workflow automation working end-to-end on live data.

### Project Architecture

1. **Layer 1 – Ingestion & Cleaning**  
   - HTTP scraper hits the Play Store `batchexecute` endpoint using a **14‑day window ending yesterday** to pull balanced samples across 1★–5★ ratings (up to **30 reviews per rating**, ~150 reviews if available).  
   - Enforces per-rating targets, deduplicates IDs, removes short/empty texts, normalizes whitespace, and strips obvious PII before any LLM call.  
   - Buckets reviews into **weekly JSON files** (`data/raw/weekly/week_YYYY-MM-DD.json`) for downstream processing.

2. **Layer 2 – Theme Classification**  
   - Gemini-based classifier maps each review into core business themes (see **Theme legend** below) with an `unclassified` fallback.  
   - Uses expanded keyword heuristics (onboarding, KYC, payments, statements, withdrawals, login issues, performance, etc.) so short/ambiguous reviews still land in a meaningful theme when possible.  
   - Runs a **two-pass** strategy: first pass does normal classification; a second pass re-classifies previously `unclassified` reviews with a stricter prompt that forbids `unclassified` and forces the closest theme.  
   - Optionally allows the LLM to propose **new theme IDs** (for analysis only), which are tracked and written to `data/processed/llm_suggested_themes.json`.  
   - Aggregates counts, example quotes, and representative actions per theme.

3. **Layer 3 – Weekly Pulse Generation**  
   - Loads each weekly bucket (requires ≥3 reviews), builds map/reduce prompts, and composes a one-page Markdown note with title, overview, key themes, quotes, and action ideas.  
   - Hardened JSON parsing handles Gemini finish reasons and malformed payloads.  
   - Writes both JSON and Markdown pulses under `data/processed/weekly_pulse/`.

4. **Layer 4 – Email Drafting & Delivery**  
   - Sanitizes the weekly note (emoji removal, sensitive-language masking).  
   - Drafts the email body via Gemini with retries and fallback templates, runs regex + LLM-based PII scrubbing, and sends via Gmail API or SMTP.  
   - Logs every send (or dry run) in `data/processed/email_logs.csv`.  
   - In scheduled/CI runs, **email generation always targets only the latest 7‑day weekly pulse**, even though Layer 1 scrapes 14 days of data for richer trend analysis.

5. **Frontend Dashboard**  
   - Modern Next.js dashboard for visualizing weekly pulses, themes, and action items.  
   - Uses static export (`next export`) and is deployed to **GitHub Pages** automatically by `.github/workflows/weekly-run.yml`.  
   - Reads JSON data from `frontend/public/data/processed/**` so the dashboard is fully static and fast.

---

### 1. Prerequisites

- Python 3.10+
- Node.js 20+ (for frontend)
- Google Gemini API key (free tier works)
- Internet access to Google Play + Gemini endpoints

---

### 2. Setup

#### Backend Setup

```bash
python -m venv .venv
.venv\Scripts\activate        # PowerShell / cmd
pip install -r requirements.txt
python -m playwright install chromium
copy config\.env.example .env
```

Fill `.env` with:
- `GEMINI_API_KEY`
- Optional overrides (see `.env.example`)

#### Frontend Setup

```bash
cd frontend
npm install
npm run dev  # For local development
```

---

### 3. Running locally

#### Backend Pipeline

```bash
python main.py
```

#### Frontend Dashboard

```bash
cd frontend
npm run dev
# Open http://localhost:3000
```

---

### 4. Deployment to GitHub Pages

The project is configured for automatic deployment to GitHub Pages via `.github/workflows/weekly-run.yml`.

- **Branch**: `main` (source) → deployed to `gh-pages` by the workflow  
- **Schedule**: runs every Monday at ~9 AM IST (`cron: '0 3 * * 1'` in UTC)  
- **What the workflow does:**
  - Runs the full Python pipeline (Layers 1–4) and sends the latest weekly pulse email.  
  - Generates `theme_review_details.json` (merged themes + raw review text) for CSV exports.  
  - Builds the Next.js frontend with static export and deploys `frontend/out` to GitHub Pages.  
- **Dashboard URL**: `https://<username>.github.io/<repo-name>/`

**Note:** The weekly email generation continues to behave as before—**only the most recent weekly pulse (7 days)** is emailed, regardless of the 14‑day scrape window used for dashboard/trend data.

---

### 5. Project Structure

```
App-Review-Insights-Analyser/
├── .github/
│   └── workflows/
│       └── weekly-run.yml      # Integrated pipeline + frontend deploy
├── frontend/                   # Next.js dashboard
│   ├── app/                    # Pages
│   ├── components/             # React components
│   ├── lib/                    # Utilities
│   └── public/data/            # Data files (for GitHub Pages)
├── src/                        # Python backend layers
├── scripts/                    # Utility scripts
├── data/                       # Pipeline output
└── main.py                     # Pipeline entry point
```

---

### 6. Outputs

- Raw batch: `data/raw/groww_reviews_<start>_<end>.json`
- Weekly buckets: `data/raw/weekly/week_<YYYY-MM-DD>.json`
- Theme aggregation: `data/processed/theme_aggregation.json`
- Review classifications: `data/processed/review_classifications.json`
- Weekly pulse notes: `data/processed/weekly_pulse/pulse_<YYYY-MM-DD>.json`
- Markdown render: `data/processed/weekly_pulse/pulse_<YYYY-MM-DD>.md`
- Theme-level aggregation: `data/processed/theme_aggregation.json`
- Merged theme + review details (for CSV export): `data/processed/theme_review_details.json`
- **Frontend Dashboard**: Deployed to GitHub Pages

---

### 7. How to re-run for a new week

You can generate a new weekly pulse and refresh the dashboard either **locally** or by **triggering the GitHub Action manually**.

- **Locally (no email):**
  ```bash
  # 1) Activate virtualenv
  .venv\Scripts\activate  # Windows

  # 2) Run full pipeline (Layers 1–3)
  python main.py

  # 3) Optionally run Layer 4 email in dry-run mode
  EMAIL_DRY_RUN=true EMAIL_SINGLE_LATEST=true python main.py --email-single-latest

  # 4) Rebuild frontend to reflect new data
  cd frontend
  npm run build
  ```

- **On GitHub (recommended weekly run):**
  1. Go to **Actions → Weekly App Review Pipeline & Frontend Deploy**.  
  2. Click **“Run workflow”** to trigger an on-demand run (or wait for the cron on Monday).  
  3. The workflow will scrape the latest 14 days, regenerate weekly pulses, send the latest 7‑day email, rebuild the dashboard, and deploy it.

Each run writes a new `week_YYYY-MM-DD.json` and corresponding `pulse_YYYY-MM-DD.json/md` if enough reviews are available for that week.

---

### 8. Theme legend used

Core themes (icons/colors match the dashboard legend):

- **customer_support** – Login, account access, KYC issues, onboarding help, general support quality.  
- **payments** – Deposits, withdrawals, UPI issues, delayed settlements, mutual fund payment/refund problems.  
- **fees** – Brokerage, charges, deductions, pricing transparency, value for money.  
- **glitches** – App crashes, order placement issues, data not loading, option chain not opening, “something went wrong”.  
- **slow** – Performance, loading times, chart/terminal lag, “app is slow” type feedback.  
- **unclassified** – Items that do not clearly map to one of the above (rare after the two-pass classification and heuristics).

The classifier can also surface **LLM-suggested themes** for exploratory analysis; these appear in the data and dashboard but do not change the core legend above.

---

### 9. Example weekly artifacts (latest sample)

These examples show what a typical weekly output looks like end‑to‑end. The concrete filenames will change as new weeks are generated, but the shape stays the same.

- **One‑page weekly note (Markdown)**  
  - Latest example (at time of writing):  
    - `data/processed/weekly_pulse/pulse_2025-11-24.md`  
  - This is the exact one‑page product pulse rendered from the JSON note and is what stakeholders read on the dashboard.

- **Weekly email draft (sample text)**  
  A typical email generated from the latest weekly pulse looks like:

  ```text
  Subject: Weekly Product Pulse – Nov 24–30: Glitches & Stability

  Hi team,

  Here’s this week’s pulse from Play Store reviews (Nov 24–30).

  Summary
  - Users are reporting frequent glitches in core trading flows, especially option chain
    loading and trending line behaviour.
  - Some users are blocked from acting on opportunities because live prices and P&L
    occasionally go out of sync with reality.

  Key themes
  - Glitches & Bugs
    - “trending lining not good performance error”
    - “Too much glitch, option chain not open properly sometime working sometimes not working.”
    - “something went wrong, live values cannot be shown, you are doing this frequently”

  Recommended actions
  - Prioritise stability fixes in option chain and trending line rendering.
  - Add monitoring around live price/P&L calculation to catch obvious mismatches.
  - Improve error messaging when live values cannot be shown, with clear next steps.

  Best,  
  Weekly Product Pulse Bot
  ```

- **Reviews CSV used (redacted sample)**  
  The Theme Explorer “Reviews CSV (Excel)” export is backed by `theme_review_details.json`. A minimal redacted CSV sample looks like:

  ```csv
  theme_id,theme_name,review_id,rating,date,author,title,week_start_date,week_end_date,review_text,reason
  glitches,"Glitches & Bugs","3ec8ac46-****",2,2025-11-22T20:12:23+00:00,"m*** h******","all over good",2025-11-17,2025-11-23,"all over good but tools option chain sometimes not working","User reports intermittent failures in option chain and tools."
  fees,"Fees & Charges","c893b067-****",1,2025-11-21T10:05:11+00:00,"G*** G****","charges are high",2025-11-17,2025-11-23,"brokerage charges very high compared to others","Explicit complaint about high brokerage fees."
  payments,Payments,"08caad09-****",1,2025-11-20T09:32:45+00:00,"A*** P****","refund delay",2025-11-17,2025-11-23,"funds not credited back even after many days","Mentions refund delays and missing funds."
  ```

In a real run, the exported CSV will contain many more rows and complete (non‑redacted) text, but follows this same column structure.
📄 License
This project is for educational/skill demonstration purposes.
