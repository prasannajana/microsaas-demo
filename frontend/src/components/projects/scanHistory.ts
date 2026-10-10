import type { ScanSummary } from '../../types';

export interface ScanHistoryRow {
  scan: ScanSummary;
  /** Score change vs the previous (older) completed scan; null when not comparable. */
  delta: number | null;
}

/** Attach score deltas to a newest-first scan list. */
export function withScoreDeltas(scans: readonly ScanSummary[]): ScanHistoryRow[] {
  const rows: ScanHistoryRow[] = [];
  let previousScore: number | null = null;
  for (let i = scans.length - 1; i >= 0; i -= 1) {
    const scan = scans[i];
    if (!scan) continue;
    const score = scan.status === 'completed' ? scan.score : null;
    const delta = score !== null && previousScore !== null ? score - previousScore : null;
    rows.unshift({ scan, delta });
    if (score !== null) previousScore = score;
  }
  return rows;
}
