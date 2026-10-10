import type { FindingCategory, FindingOut, Severity } from '../../types';
import { FINDING_CATEGORIES } from '../../types';

export const CATEGORY_LABEL: Record<FindingCategory, string> = {
  documentation: 'Documentation',
  testing: 'Testing',
  ci_cd: 'CI/CD',
  deployment: 'Deployment',
  configuration: 'Configuration',
  dependencies: 'Dependencies',
};

export const SEVERITY_RANK: Record<Severity, number> = {
  critical: 0,
  high: 1,
  medium: 2,
  low: 3,
};

export function sortBySeverity(findings: readonly FindingOut[]): FindingOut[] {
  return [...findings].sort(
    (a, b) => SEVERITY_RANK[a.severity] - SEVERITY_RANK[b.severity] || a.title.localeCompare(b.title),
  );
}

export interface CategoryGroup {
  category: FindingCategory;
  label: string;
  findings: FindingOut[];
}

/** Group findings by category (stable category order), each group sorted by severity. */
export function groupFindingsByCategory(findings: readonly FindingOut[]): CategoryGroup[] {
  return FINDING_CATEGORIES.map((category) => ({
    category,
    label: CATEGORY_LABEL[category],
    findings: sortBySeverity(findings.filter((f) => f.category === category)),
  })).filter((group) => group.findings.length > 0);
}

export function countBySeverity(findings: readonly FindingOut[]): Record<Severity, number> {
  const counts: Record<Severity, number> = { critical: 0, high: 0, medium: 0, low: 0 };
  for (const f of findings) counts[f.severity] += 1;
  return counts;
}

const RELATIVE_UNITS: readonly [Intl.RelativeTimeFormatUnit, number][] = [
  ['year', 60 * 60 * 24 * 365],
  ['month', 60 * 60 * 24 * 30],
  ['week', 60 * 60 * 24 * 7],
  ['day', 60 * 60 * 24],
  ['hour', 60 * 60],
  ['minute', 60],
];

/** "3 hours ago" style relative time; returns `fallback` for null/invalid dates. */
export function formatRelativeTime(iso: string | null | undefined, fallback = 'Never', now: Date = new Date()): string {
  if (!iso) return fallback;
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) return fallback;
  const diffSeconds = (date.getTime() - now.getTime()) / 1000;
  const rtf = new Intl.RelativeTimeFormat(undefined, { numeric: 'auto' });
  for (const [unit, seconds] of RELATIVE_UNITS) {
    if (Math.abs(diffSeconds) >= seconds) {
      return rtf.format(Math.round(diffSeconds / seconds), unit);
    }
  }
  return 'just now';
}

export function formatDateTime(iso: string | null | undefined, fallback = '—'): string {
  if (!iso) return fallback;
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) return fallback;
  return date.toLocaleString(undefined, { dateStyle: 'medium', timeStyle: 'short' });
}

export function shortSha(sha: string | null | undefined): string | null {
  return sha ? sha.slice(0, 7) : null;
}
