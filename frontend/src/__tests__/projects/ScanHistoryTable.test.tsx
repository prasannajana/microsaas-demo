import { screen, within } from '@testing-library/react';
import { describe, expect, it } from 'vitest';
import { ScanHistoryTable } from '../../components/projects/ScanHistoryTable';
import { makeScan } from '../fixtures';
import { renderWithProviders } from '../test-utils';

function rows(): HTMLElement[] {
  const table = screen.getByRole('table', { name: 'Scan history' });
  // skip header row
  return within(table).getAllByRole('row').slice(1);
}

function row(index: number): HTMLElement {
  const el = rows()[index];
  if (!el) throw new Error(`no row ${index}`);
  return el;
}

describe('ScanHistoryTable', () => {
  it('shows up/down/zero deltas against the previous completed scan (newest first)', () => {
    const scans = [
      makeScan({ id: 5, score: 70, created_at: '2026-10-05T10:00:00Z' }), // -20 vs 90
      makeScan({ id: 4, status: 'failed', score: null, created_at: '2026-10-04T10:00:00Z' }),
      makeScan({ id: 3, score: 90, created_at: '2026-10-03T10:00:00Z' }), // +30 vs 60
      makeScan({ id: 2, score: 60, created_at: '2026-10-02T10:00:00Z' }), // ±0 vs 60
      makeScan({ id: 1, score: 60, created_at: '2026-10-01T10:00:00Z' }), // first: —
    ];
    renderWithProviders(<ScanHistoryTable projectId={7} scans={scans} />);
    expect(rows()).toHaveLength(5);

    expect(within(row(0)).getByLabelText('Down 20 points from previous scan')).toHaveTextContent('▼ -20');
    expect(within(row(1)).getByText('failed')).toBeInTheDocument();
    expect(within(row(2)).getByLabelText('Up 30 points from previous scan')).toHaveTextContent('▲ +30');
    expect(within(row(3)).getByText('±0')).toBeInTheDocument();
    // first-ever scan has nothing to compare against
    expect(within(row(4)).queryByText(/▲|▼|±0/)).not.toBeInTheDocument();
  });

  it('shows a dash instead of a score for non-completed scans and links each report', () => {
    renderWithProviders(
      <ScanHistoryTable
        projectId={7}
        scans={[makeScan({ id: 9, status: 'running', score: null }), makeScan({ id: 8, score: 55 })]}
      />,
    );
    const running = row(0);
    const done = row(1);
    expect(within(running).getByText('running')).toBeInTheDocument();
    expect(within(running).getAllByText('—').length).toBeGreaterThanOrEqual(1);
    expect(within(done).getByText('55/100')).toBeInTheDocument();
    expect(within(running).getByRole('link', { name: /View scan from/ })).toHaveAttribute('href', '/projects/7/scans/9');
    expect(within(done).getByRole('link', { name: /View scan from/ })).toHaveAttribute('href', '/projects/7/scans/8');
  });

  it('renders an empty body for no scans', () => {
    renderWithProviders(<ScanHistoryTable projectId={7} scans={[]} />);
    expect(rows()).toHaveLength(0);
  });
});
