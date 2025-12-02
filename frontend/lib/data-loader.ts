import type { WeeklyPulseNote, ThemeAggregation, ThemeReviewDetail } from './types';

// Base path for GitHub Pages (matches next.config.ts basePath)
// This will be /Milestone-2 for project sites
const BASE_PATH = '/Milestone-2';

// Client-side data fetching functions (for static export)
export async function fetchAllPulses(): Promise<WeeklyPulseNote[]> {
  try {
    // Try manifest first
    const manifestUrl = `${BASE_PATH}/data/processed/weekly_pulse/manifest.json`;
    console.log('Fetching manifest from:', manifestUrl);
    const response = await fetch(manifestUrl);
    
    if (response.ok) {
      const manifest = await response.json();
      console.log('Manifest loaded, files:', manifest.files?.length || 0);
      const pulses: WeeklyPulseNote[] = [];
      
      for (const file of manifest.files || []) {
        try {
          const pulseUrl = `${BASE_PATH}/data/processed/weekly_pulse/${file}`;
          const pulseResponse = await fetch(pulseUrl);
          if (pulseResponse.ok) {
            pulses.push(await pulseResponse.json());
          }
        } catch (error) {
          console.error(`Error fetching pulse ${file}:`, error);
        }
      }
      
      console.log(`Loaded ${pulses.length} pulses from manifest`);
      return pulses.sort((a, b) => b.week_start.localeCompare(a.week_start));
    }
    
    // Fallback: try to discover files directly
    console.warn('Manifest not found, trying to discover files');
    const commonFiles = [
      'pulse_2025-11-24.json',
      'pulse_2025-11-17.json',
      'pulse_2025-11-10.json',
      'pulse_2025-11-03.json',
      'pulse_2025-10-27.json',
      'pulse_2025-10-20.json',
      'pulse_2025-10-13.json',
      'pulse_2025-09-15.json',
    ];
    
    const pulses: WeeklyPulseNote[] = [];
    for (const file of commonFiles) {
      try {
        const pulseUrl = `${BASE_PATH}/data/processed/weekly_pulse/${file}`;
        const pulseResponse = await fetch(pulseUrl);
        if (pulseResponse.ok) {
          pulses.push(await pulseResponse.json());
        }
      } catch (error) {
        // Continue to next file
      }
    }
    
    console.log(`Loaded ${pulses.length} pulses from fallback`);
    return pulses.sort((a, b) => b.week_start.localeCompare(a.week_start));
  } catch (error) {
    console.error('Error fetching pulses:', error);
    return [];
  }
}

export async function fetchPulse(weekStart: string): Promise<WeeklyPulseNote | null> {
  try {
    const url = `${BASE_PATH}/data/processed/weekly_pulse/pulse_${weekStart}.json`;
    console.log('Fetching pulse from:', url);
    const response = await fetch(url);
    
    if (!response.ok) {
      console.warn(`Pulse ${weekStart} not found: ${response.status} ${response.statusText}`);
      console.warn('URL attempted:', url);
      return null;
    }
    
    const data = await response.json();
    console.log('Pulse fetched successfully:', weekStart);
    return data;
  } catch (error) {
    console.error(`Error fetching pulse ${weekStart}:`, error);
    console.error('URL attempted:', `${BASE_PATH}/data/processed/weekly_pulse/pulse_${weekStart}.json`);
    throw error; // Re-throw so caller can handle it
  }
}

export async function fetchThemeAggregation(): Promise<ThemeAggregation | null> {
  try {
    const url = `${BASE_PATH}/data/processed/theme_aggregation.json`;
    console.log('Fetching theme aggregation from:', url);
    const response = await fetch(url);
    if (!response.ok) {
      console.warn(`Theme aggregation not found: ${response.status}`);
      return null;
    }
    const data = await response.json();
    console.log('Theme aggregation loaded');
    return data;
  } catch (error) {
    console.error('Error fetching theme aggregation:', error);
    return null;
  }
}

export async function fetchThemeReviewDetails(): Promise<ThemeReviewDetail[]> {
  try {
    const url = `${BASE_PATH}/data/processed/theme_review_details.json`;
    console.log('Fetching theme review details from:', url);
    const response = await fetch(url);

    if (!response.ok) {
      console.warn(
        `Theme review details not found: ${response.status} ${response.statusText}`,
      );
      return [];
    }

    const data = await response.json();
    return Array.isArray(data) ? data : [];
  } catch (error) {
    console.error('Error fetching theme review details:', error);
    return [];
  }
}
