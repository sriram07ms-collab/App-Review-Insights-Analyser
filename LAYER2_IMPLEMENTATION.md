# Layer 2 Implementation Summary

## Overview
Layer 2 has been implemented with **LLM-based classification** into **5 fixed themes** instead of the previous HDBSCAN clustering approach. Each review is now assigned to exactly one theme using Gemini LLM.

## Components Implemented

### 1. Theme Configuration (`src/layer2/theme_config.py`)
- **5 Fixed Themes**:
  1. **Slow, Glitches** (`glitches`) - Order placement delays, app crashes, pending orders
  2. **UI/UX** (`ui_ux`) - Interface design, user experience, statement requests
  3. **Payments/Statements** (`payments_statements`) - Profit/loss discrepancies, balance issues, target accuracy
  4. **Customer Support** (`customer_support`) - Support responsiveness, help requests
  5. **Slow** (`slow`) - Performance issues, slow loading, laggy interface

- Default fallback theme: `ui_ux` (used when classification fails)

### 2. LLM-Based Classifier (`src/layer2/theme_classifier.py`)
- **GeminiThemeClassifier**: Classifies reviews into fixed themes
- **Features**:
  - Batch processing (default: 8 reviews per LLM call)
  - JSON-structured output parsing
  - Theme ID validation with fuzzy matching
  - Fallback classification on LLM failures
  - Retry logic (max 2 retries)

### 3. Weekly Aggregator (`src/layer2/weekly_aggregator.py`)
- **WeeklyThemeAggregator**: Groups reviews by week and counts themes
- **Features**:
  - Loads weekly JSON files from `data/raw/weekly/`
  - Aggregates theme counts per week
  - Computes overall theme counts across all weeks
  - Sorts themes by count (top themes)
  - Saves results to `data/processed/theme_aggregation.json`

### 4. Main Pipeline Integration (`main.py`)
- Replaced clustering/embedding approach with LLM classification
- **Flow**:
  1. Filter reviews with text length < 10 characters (guardrail)
  2. Classify all reviews using GeminiThemeClassifier
  3. Aggregate by week using WeeklyThemeAggregator
  4. Save two outputs:
     - `data/processed/theme_aggregation.json` - Weekly counts and top themes
     - `data/processed/review_classifications.json` - Individual review classifications

## Guardrails Implemented

1. **Empty/Short Review Filtering**: Reviews with text < 10 characters are excluded
2. **Invalid Theme Handling**: Invalid theme IDs are mapped to default theme (`ui_ux`)
3. **LLM Failure Handling**: Fallback classification when LLM calls fail
4. **Fuzzy Theme Matching**: Partial matches (e.g., "glitch" → "glitches") are accepted

## Output Files

### `data/processed/theme_aggregation.json`
```json
{
  "weekly_counts": [
    {
      "week_start_date": "2025-11-10",
      "week_end_date": "2025-11-16",
      "theme_counts": {"glitches": 3, "ui_ux": 1},
      "total_reviews": 4
    }
  ],
  "overall_counts": {"glitches": 9, "ui_ux": 2, ...},
  "top_themes": [{"theme_id": "glitches", "count": 9}, ...]
}
```

### `data/processed/review_classifications.json`
```json
[
  {
    "review_id": "...",
    "theme_id": "glitches",
    "theme_name": "Slow, Glitches",
    "reason": "Review mentions order placement delays"
  }
]
```

## Configuration

Environment variables (optional):
- `THEME_CLASSIFIER_BATCH_SIZE` (default: 8) - Reviews per LLM call
- `THEME_CLASSIFIER_TEMPERATURE` (default: 0.1) - LLM temperature for consistency

## Next Steps

Layer 2 is complete and ready for Layer 3 (Note Generation) which will use:
- Top themes from `theme_aggregation.json`
- Individual classifications from `review_classifications.json`
- Weekly counts for trend analysis


