import type { Severity } from '../types';

export type ScoreLevel = 'good' | 'fair' | 'poor' | 'none';

export function getScoreLevel(score: number | null | undefined): ScoreLevel {
  if (score === null || score === undefined) return 'none';
  if (score >= 80) return 'good';
  if (score >= 50) return 'fair';
  return 'poor';
}

/** Chakra colorScheme for a 0-100 score: >=80 green, >=50 orange, else red, null gray. */
export function getScoreColorScheme(score: number | null | undefined): string {
  switch (getScoreLevel(score)) {
    case 'good':
      return 'green';
    case 'fair':
      return 'orange';
    case 'poor':
      return 'red';
    default:
      return 'gray';
  }
}

export const SEVERITY_COLOR_SCHEME: Record<Severity, string> = {
  critical: 'red',
  high: 'orange',
  medium: 'yellow',
  low: 'gray',
};

export const SEVERITY_LABEL: Record<Severity, string> = {
  critical: 'Critical',
  high: 'High',
  medium: 'Medium',
  low: 'Low',
};
