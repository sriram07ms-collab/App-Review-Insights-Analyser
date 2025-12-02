export interface WeeklyPulseNote {
  week_start: string;
  week_end: string;
  title: string;
  overview: string;
  themes: Array<{
    name?: string;
    theme_name?: string;
    theme_id?: string;
    summary?: string;
  }>;
  quotes: string[];
  actions: string[];
  word_count: number;
}

export interface WeeklyThemeCounts {
  week_start_date: string;
  week_end_date: string;
  theme_counts: Record<string, number>;
  total_reviews: number;
}

export interface ThemeAggregation {
  weekly_counts: WeeklyThemeCounts[];
  overall_counts: Record<string, number>;
  top_themes: Array<{
    theme_id: string;
    count: number;
  }>;
}

export interface ReviewClassification {
  review_id: string;
  theme_id: string;
  theme_name: string;
  confidence?: number;
}

export interface ThemeReviewDetail {
  review_id: string;
  theme_id: string;
  theme_name: string;
  reason?: string;
  text: string;
  rating: number;
  date: string;
  author: string;
  title?: string;
  week_start_date?: string;
  week_end_date?: string;
}

export const THEME_COLORS: Record<string, string> = {
  customer_support: '#3b82f6',
  payments: '#10b981',
  fees: '#f59e0b',
  glitches: '#ef4444',
  slow: '#8b5cf6',
  unclassified: '#6b7280',
};

export const THEME_ICONS: Record<string, string> = {
  customer_support: '💬',
  payments: '💳',
  fees: '💰',
  glitches: '🐛',
  slow: '⚡',
  unclassified: '❓',
};