import { screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import type { AdminScan, Page } from '../../types';
import { httpError, makeScan } from '../fixtures';
import { renderWithProviders } from '../test-utils';

const api = vi.hoisted(() => ({ get: vi.fn() }));
vi.mock('../../services/api', () => ({ default: api }));

const { default: AdminScansPage } = await import('../../pages/AdminScansPage');

const ALL: AdminScan[] = [
  { ...makeScan({ id: 1, status: 'completed', score: 88 }), project_name: 'alpha', user_email: 'a@example.com' },
  {
    ...makeScan({ id: 2, status: 'failed', score: null, error_message: 'Repository not found or is private' }),
    project_name: 'beta',
    user_email: 'b@example.com',
  },
  { ...makeScan({ id: 3, status: 'running', score: null }), project_name: 'gamma', user_email: 'c@example.com' },
];

interface Params {
  status?: string;
  page?: number;
  size?: number;
}

describe('AdminScansPage', () => {
  beforeEach(() => {
    api.get.mockReset();
    api.get.mockImplementation((_url: string, opts: { params: Params }) => {
      const items = opts.params.status ? ALL.filter((s) => s.status === opts.params.status) : ALL;
      const data: Page<AdminScan> = { items, total: items.length, page: opts.params.page ?? 1, size: 20 };
      return Promise.resolve({ data });
    });
  });

  it('lists all scans across users by default without a status param', async () => {
    renderWithProviders(<AdminScansPage />);
    expect(await screen.findByText('alpha')).toBeInTheDocument();
    expect(screen.getByText('b@example.com')).toBeInTheDocument();
    expect(screen.getByText('Repository not found or is private')).toBeInTheDocument();
    expect(screen.getByText('88/100')).toBeInTheDocument();
    expect(screen.getByText('3 results · Page 1 of 1')).toBeInTheDocument();
    expect(api.get).toHaveBeenLastCalledWith('/admin/scans', { params: { page: 1, size: 20 } });
  });

  it('filters by status and sends the status query param', async () => {
    renderWithProviders(<AdminScansPage />);
    await screen.findByText('alpha');
    const user = userEvent.setup();
    await user.selectOptions(screen.getByLabelText('Status'), 'failed');

    await waitFor(() =>
      expect(api.get).toHaveBeenLastCalledWith('/admin/scans', { params: { status: 'failed', page: 1, size: 20 } }),
    );
    await waitFor(() => expect(screen.queryByText('alpha')).not.toBeInTheDocument());
    expect(screen.getByText('beta')).toBeInTheDocument();
    expect(screen.getByText('1 result · Page 1 of 1')).toBeInTheDocument();

    await user.selectOptions(screen.getByLabelText('Status'), 'all');
    expect(await screen.findByText('alpha')).toBeInTheDocument();
    expect(api.get).toHaveBeenLastCalledWith('/admin/scans', { params: { page: 1, size: 20 } });
  });

  it('shows "No scans found." for an empty filter result', async () => {
    renderWithProviders(<AdminScansPage />);
    await screen.findByText('alpha');
    await userEvent.setup().selectOptions(screen.getByLabelText('Status'), 'queued');
    expect(await screen.findByText('No scans found.')).toBeInTheDocument();
  });

  it('shows the error from a forbidden request', async () => {
    api.get.mockReset();
    api.get.mockRejectedValue(httpError(403, 'Admin access required'));
    renderWithProviders(<AdminScansPage />);
    expect(await screen.findByText('Admin access required')).toBeInTheDocument();
  });

  it('pages through results', async () => {
    api.get.mockImplementation((_url: string, opts: { params: Params }) =>
      Promise.resolve({
        data: { items: [{ ...ALL[0], id: opts.params.page ?? 1, project_name: `proj-${opts.params.page}` }], total: 45, page: 1, size: 20 },
      }),
    );
    renderWithProviders(<AdminScansPage />);
    expect(await screen.findByText('proj-1')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Previous' })).toBeDisabled();
    await userEvent.setup().click(screen.getByRole('button', { name: 'Next' }));
    expect(await screen.findByText('proj-2')).toBeInTheDocument();
    expect(screen.getByText('45 results · Page 2 of 3')).toBeInTheDocument();
  });
});
