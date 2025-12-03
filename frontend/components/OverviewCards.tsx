'use client';

import { ThemeAggregation, WeeklyPulseNote } from '@/lib/types';
import { TrendingUp, TrendingDown, Star, Users, Calendar, Award } from 'lucide-react';

interface OverviewCardsProps {
  aggregation: ThemeAggregation | null;
  latestPulse: WeeklyPulseNote | null;
}

// Helper to calculate average rating from review data if available
function calculateAvgRating(aggregation: ThemeAggregation | null): number {
  // This is a placeholder - in a real scenario, you'd calculate from actual review ratings
  // For now, return a default value
  return 3.2;
}

export default function OverviewCards({ aggregation, latestPulse }: OverviewCardsProps) {
  const totalReviews = aggregation?.overall_counts
    ? Object.values(aggregation.overall_counts).reduce((a, b) => a + b, 0)
    : 0;

  const thisWeekReviews = aggregation?.weekly_counts.length > 0
    ? aggregation.weekly_counts[aggregation.weekly_counts.length - 1]?.total_reviews || 0
    : 0;

  const topTheme = aggregation?.top_themes[0];
  const topThemeName = topTheme ? topTheme.theme_id.replace('_', ' ').replace(/\b\w/g, l => l.toUpperCase()) : 'N/A';
  const topThemeCount = topTheme?.count || 0;

  // Calculate average rating
  const avgRating = calculateAvgRating(aggregation);

  const cards = [
    {
      title: 'Total Reviews',
      value: totalReviews.toLocaleString(),
      icon: Users,
      color: 'bg-blue-500',
      bgColor: 'bg-blue-50',
      textColor: 'text-blue-600',
      trend: '+12%',
      trendUp: true,
    },
    {
      title: 'This Week',
      value: thisWeekReviews.toString(),
      icon: Calendar,
      color: 'bg-green-500',
      bgColor: 'bg-green-50',
      textColor: 'text-green-600',
      trend: '-5%',
      trendUp: false,
    },
    {
      title: 'Top Theme',
      value: topThemeName,
      subtitle: `${topThemeCount} reviews`,
      icon: Award,
      color: 'bg-purple-500',
      bgColor: 'bg-purple-50',
      textColor: 'text-purple-600',
    },
    {
      title: 'Avg Rating',
      value: avgRating.toFixed(1),
      icon: Star,
      color: 'bg-yellow-500',
      bgColor: 'bg-yellow-50',
      textColor: 'text-yellow-600',
    },
  ];

  return (
    <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
      {cards.map((card, index) => {
        const Icon = card.icon;
        return (
          <div
            key={index}
            className="bg-white rounded-lg shadow-sm border border-gray-200 p-5 hover:shadow-md transition-all duration-200"
          >
            <div className="flex items-start justify-between">
              <div className="flex-1 min-w-0">
                <p className="text-xs font-medium text-gray-600 mb-2">{card.title}</p>
                <div className="flex items-baseline gap-2">
                  {card.subtitle ? (
                    <div>
                      <p className="text-2xl font-bold text-gray-900">{card.value}</p>
                      <p className="text-xs text-gray-500 mt-1">{card.subtitle}</p>
                    </div>
                  ) : (
                    <p className="text-3xl font-bold text-gray-900">{card.value}</p>
                  )}
                </div>
                {card.trend && (
                  <div className={`flex items-center gap-1 mt-3 ${card.trendUp ? 'text-green-600' : 'text-red-600'}`}>
                    {card.trendUp ? (
                      <TrendingUp className="w-3 h-3" />
                    ) : (
                      <TrendingDown className="w-3 h-3" />
                    )}
                    <span className="text-xs font-medium">{card.trend}</span>
                  </div>
                )}
              </div>
              <div className={`${card.bgColor} p-3 rounded-lg flex-shrink-0`}>
                <Icon className={`w-5 h-5 ${card.textColor}`} />
              </div>
            </div>
          </div>
        );
      })}
    </div>
  );
}
