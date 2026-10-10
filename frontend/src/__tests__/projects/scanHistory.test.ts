import { describe, expect, it } from 'vitest';
import { withScoreDeltas } from '../../components/projects/scanHistory';
import type { ScanStatus, ScanSummary } from '../../types';

function s(id: number, status: ScanStatus, score: number | null): ScanSummary {
  return { id, project_id: 1, status, score, commit_sha: null, error_message: null, started_at: null, completed_at: null, created_at: '2026-10-01T00:00:00Z' };
}

describe('withScoreDeltas', () => {
  it('computes deltas vs the previous completed scan, skipping failed ones', () => {
    const rows = withScoreDeltas([s(4, 'completed', 90), s(3, 'failed', null), s(2, 'completed', 70), s(1, 'completed', 75)]);
    expect(rows.map((r) => r.delta)).toEqual([20, null, -5, null]);
  });
});
