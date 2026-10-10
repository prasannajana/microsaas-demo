import { screen } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import type { AuthContextValue } from '../../context/AuthContext';
import type { AnalyticsSummary, Page, ProjectOut, User } from '../../types';
import { renderWithProviders } from '../test-utils';

const me: User = {
  id: 1,
  email: 'ada@example.com',
  full_name: 'Ada Lovelace',
  is_active: true,
  is_verified: true,
  is_admin: false,
  oauth_provider: null,
  avatar_url: null,
  created_at: '2026-10-10T00:00:00Z',
};

vi.mock('../../context/AuthContext', () => ({
  useAuth: (): AuthContextValue => ({
    user: me,
    isLoading: false,
    login: vi.fn(),
    register: vi.fn(),
    logout: vi.fn(),
    setTokens: vi.fn(),
    refreshUser: vi.fn(),
  }),
}));

const summaryState: { value: AnalyticsSummary } = {
  value: { project_count: 0, scan_count: 0, avg_latest_score: null, open_critical_findings: 0 },
};

const emptyProjects: Page<ProjectOut> = { items: [], total: 0, page: 1, size: 5 };

const getMock = vi.fn((url: string) => {
  switch (url) {
    case '/analytics/summary':
      return Promise.resolve({ data: summaryState.value });
    case '/projects':
      return Promise.resolve({ data: emptyProjects });
    default:
      return Promise.resolve({ data: [] });
  }
});

vi.mock('../../services/api', () => ({
  default: { get: (url: string) => getMock(url) },
}));

const { default: DashboardPage } = await import('../../pages/DashboardPage');

describe('DashboardPage', () => {
  beforeEach(() => {
    getMock.mockClear();
  });

  it('shows the first-run empty state when the user has no projects', async () => {
    summaryState.value = { project_count: 0, scan_count: 0, avg_latest_score: null, open_critical_findings: 0 };
    renderWithProviders(<DashboardPage />);
    expect(await screen.findByText('Add your first project')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Add a project' })).toBeInTheDocument();
    expect(screen.queryByText('Average score')).not.toBeInTheDocument();
  });

  it('shows stat cards when the user has projects', async () => {
    summaryState.value = { project_count: 3, scan_count: 7, avg_latest_score: 82, open_critical_findings: 1 };
    renderWithProviders(<DashboardPage />);
    expect(await screen.findByText('82')).toBeInTheDocument();
    expect(screen.getByText('Average score')).toBeInTheDocument();
    expect(screen.getByText('Open critical findings')).toBeInTheDocument();
    expect(screen.queryByText('Add your first project')).not.toBeInTheDocument();
  });
});
