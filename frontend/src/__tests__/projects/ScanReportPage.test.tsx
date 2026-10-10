import { screen } from '@testing-library/react';
import { Route, Routes } from 'react-router-dom';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import type { ScanDetail } from '../../types';
import { httpError, makeFinding, makeProjectDetail, makeScanDetail } from '../fixtures';
import { renderWithProviders } from '../test-utils';

const api = vi.hoisted(() => ({ get: vi.fn() }));
vi.mock('../../services/api', () => ({ default: api }));

const { default: ScanReportPage } = await import('../../pages/ScanReportPage');

let scan: ScanDetail | Error;

function renderAt(route: string) {
  api.get.mockImplementation((url: string) => {
    if (url === '/projects/7') return Promise.resolve({ data: makeProjectDetail({ name: 'My Repo' }) });
    if (url === '/scans/3') return scan instanceof Error ? Promise.reject(scan) : Promise.resolve({ data: scan });
    return Promise.reject(httpError(404, 'Not found'));
  });
  return renderWithProviders(
    <Routes>
      <Route path="/projects/:id/scans/:scanId" element={<ScanReportPage />} />
    </Routes>,
    { route },
  );
}

describe('ScanReportPage', () => {
  beforeEach(() => {
    api.get.mockReset();
  });

  it('shows the report grouped by category with recommendations', async () => {
    scan = makeScanDetail({
      id: 3,
      score: 62,
      findings: [
        makeFinding({ id: 1, title: 'No tests', category: 'testing', severity: 'critical', recommendation: 'Add tests.' }),
        makeFinding({ id: 2, title: 'No CI', category: 'ci_cd', severity: 'high', recommendation: 'Add a workflow.' }),
      ],
    });
    renderAt('/projects/7/scans/3');
    expect(await screen.findByText('No tests')).toBeInTheDocument();
    expect(screen.getByText('Add tests.')).toBeInTheDocument();
    expect(screen.getByText('Add a workflow.')).toBeInTheDocument();
    expect(screen.getByText('Testing')).toBeInTheDocument();
    expect(screen.getByText('CI/CD')).toBeInTheDocument();
    expect(await screen.findByRole('link', { name: 'My Repo' })).toHaveAttribute('href', '/projects/7');
    expect(screen.getByText('Scan #3')).toBeInTheDocument();
  });

  it('shows the failure banner for a failed scan', async () => {
    scan = makeScanDetail({ id: 3, status: 'failed', score: null, error_message: 'Repository exceeds size limit (200 MB)', findings: [] });
    renderAt('/projects/7/scans/3');
    expect(await screen.findByText('Scan failed')).toBeInTheDocument();
    expect(screen.getByText('Repository exceeds size limit (200 MB)')).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: 'Retry scan' })).not.toBeInTheDocument();
  });

  it('rejects an invalid scan id without fetching it', async () => {
    renderAt('/projects/7/scans/zero');
    expect(await screen.findByText('This scan link looks invalid.')).toBeInTheDocument();
    expect(api.get).not.toHaveBeenCalledWith('/scans/zero');
  });

  it('shows the API error for a scan the user cannot see', async () => {
    scan = httpError(404, 'Scan not found');
    renderAt('/projects/7/scans/3');
    expect(await screen.findByText('Scan not found')).toBeInTheDocument();
  });
});
