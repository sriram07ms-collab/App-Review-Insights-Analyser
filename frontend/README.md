# App Review Insights Dashboard

A modern Next.js frontend for visualizing weekly pulse notes, theme analysis, and action items from the App Review Insights Analyzer pipeline.

## Features

- 📊 **Dashboard**: Overview cards, theme trends, and latest pulse
- 📅 **Weekly Pulses**: Browse and view detailed weekly pulse notes
- 🏷️ **Theme Explorer**: Explore themes with trends and statistics
- ✅ **Action Ideas Board**: Prioritized action items from all pulses

## Tech Stack

- **Next.js 16** (App Router)
- **TypeScript**
- **Tailwind CSS**
- **Recharts** (for data visualization)
- **Lucide React** (icons)

## Setup

1. **Install dependencies:**
   ```bash
   npm install
   ```

2. **Set up data connection:**
   
   The frontend reads data from the main pipeline's output directory. You have two options:
   
   **Option A: Copy data (recommended for production)**
   ```bash
   # Windows PowerShell
   Copy-Item -Path "..\App-Review-Insights-Analyser\data\processed" -Destination "public\data\processed" -Recurse -Force
   
   # Linux/Mac
   cp -r ../App-Review-Insights-Analyser/data/processed ./public/data/processed
   ```
   
   **Option B: Use environment variable**
   Create `.env.local`:
   ```
   DATA_PATH=C:\Users\SM095616\App-Review-Insights-Analyser\data\processed
   ```

3. **Run development server:**
   ```bash
   npm run dev
   ```

4. **Open in browser:**
   Navigate to [http://localhost:3000](http://localhost:3000)

## Project Structure

```
app-review-dashboard/
├── app/
│   ├── page.tsx              # Dashboard home
│   ├── pulses/                # Weekly pulses pages
│   ├── themes/                # Theme explorer
│   └── actions/               # Action ideas board
├── components/               # React components
│   ├── OverviewCards.tsx
│   ├── ThemeTrendChart.tsx
│   ├── WeeklyPulseCard.tsx
│   └── ThemeCard.tsx
├── lib/
│   ├── types.ts              # TypeScript interfaces
│   ├── data-loader.ts        # Data loading utilities
│   └── utils.ts              # Helper functions
└── public/
    └── data/                 # Data files (copied from main project)
```

## Data Requirements

The frontend expects the following files from the main pipeline:

- `data/processed/weekly_pulse/pulse_*.json` - Weekly pulse notes
- `data/processed/theme_aggregation.json` - Theme aggregation data

## Building for Production

```bash
npm run build
npm start
```

## Updating Data

After running the main pipeline, copy the updated data:

```bash
# Windows PowerShell
Copy-Item -Path "..\App-Review-Insights-Analyser\data\processed" -Destination "public\data\processed" -Recurse -Force

# Or create a sync script (sync-data.ps1)
```

## Notes

- The frontend is completely separate from the main Python pipeline
- No changes are needed to the main project structure
- Data is read at build time (static generation) or server-side (dynamic routes)
- The data loader automatically searches for the data directory in common locations
