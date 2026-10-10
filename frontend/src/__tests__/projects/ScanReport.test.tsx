import { screen, within } from '@testing-library/react';
import { describe, expect, it } from 'vitest';
import { ScanReport } from '../../components/projects/ScanReport';
import type { FindingOut, ScanDetail } from '../../types';
import { renderWithProviders } from '../test-utils';

function finding(overrides: Partial<FindingOut> & Pick<FindingOut, 'id'>): FindingOut {
  return {
    check_id: `check_${overrides.id}`,
    category: 'documentation',
    severity: 'low',
    title: `Finding ${overrides.id}`,
    recommendation: 'Fix it.',
    file_path: null,
    ...overrides,
  };
}

function scan(overrides: Partial<ScanDetail> = {}): ScanDetail {
  return {
    id: 7,
    project_id: 1,
    status: 'completed',
    score: 42,
    commit_sha: 'abcdef1234567890',
    error_message: null,
    started_at: '2026-10-01T10:00:00Z',
    completed_at: '2026-10-01T10:00:05Z',
    created_at: '2026-10-01T10:00:00Z',
    findings: [],
    ...overrides,
  };
}

describe('ScanReport', () => {
  it('groups findings by category with human labels, sorted by severity', () => {
    const findings = [
      finding({ id: 1, category: 'documentation', severity: 'medium', title: 'Missing LICENSE' }),
      finding({ id: 2, category: 'documentation', severity: 'high', title: 'Missing README' }),
      finding({ id: 3, category: 'ci_cd', severity: 'high', title: 'No CI workflow' }),
      finding({ id: 4, category: 'testing', severity: 'critical', title: 'No tests' }),
    ];
    renderWithProviders(<ScanReport scan={scan({ findings })} />);

    const docs = screen.getByTestId('category-documentation');
    expect(within(docs).getByText('Documentation')).toBeInTheDocument();
    const titles = within(docs)
      .getAllByTestId('finding-card')
      .map((card) => card.textContent ?? '');
    expect(titles[0]).toContain('Missing README');
    expect(titles[1]).toContain('Missing LICENSE');

    expect(within(screen.getByTestId('category-ci_cd')).getByText('CI/CD')).toBeInTheDocument();
    expect(within(screen.getByTestId('category-testing')).getByText('No tests')).toBeInTheDocument();
    expect(screen.queryByTestId('category-deployment')).not.toBeInTheDocument();

    expect(screen.getByTestId('severity-count-high')).toHaveTextContent('2');
    expect(screen.getByTestId('severity-count-critical')).toHaveTextContent('1');
    expect(screen.getByText('abcdef1')).toBeInTheDocument();
  });

  it('shows the celebratory empty state for a perfect score', () => {
    renderWithProviders(<ScanReport scan={scan({ score: 100, findings: [] })} />);
    expect(screen.getByText(/no missing essentials found/i)).toBeInTheDocument();
    expect(screen.queryByTestId('findings-by-category')).not.toBeInTheDocument();
    expect(screen.getByTestId('score-gauge')).toHaveAttribute('aria-label', 'Readiness score 100 out of 100');
  });
});
