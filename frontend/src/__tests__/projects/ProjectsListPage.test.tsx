import { screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { Route, Routes } from 'react-router-dom';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import type { Page, ProjectOut } from '../../types';
import { httpError, makeProject } from '../fixtures';
import { renderWithProviders } from '../test-utils';

const api = vi.hoisted(() => ({ get: vi.fn() }));
vi.mock('../../services/api', () => ({ default: api }));

const { default: ProjectsListPage } = await import('../../pages/ProjectsListPage');

function page(items: ProjectOut[], total = items.length, pageNo = 1, size = 12): Page<ProjectOut> {
  return { items, total, page: pageNo, size };
}

function renderPage() {
  return renderWithProviders(
    <Routes>
      <Route path="/projects" element={<ProjectsListPage />} />
      <Route path="/projects/new" element={<p>new project form</p>} />
    </Routes>,
    { route: '/projects' },
  );
}

describe('ProjectsListPage', () => {
  beforeEach(() => {
    api.get.mockReset();
  });

  it('shows the empty state with a CTA that opens the new-project page', async () => {
    api.get.mockResolvedValue({ data: page([]) });
    renderPage();
    expect(await screen.findByText('No projects yet')).toBeInTheDocument();
    await userEvent.setup().click(screen.getByRole('button', { name: 'Add your first project' }));
    expect(await screen.findByText('new project form')).toBeInTheDocument();
  });

  it('renders a card per project with score, language and scan time', async () => {
    api.get.mockResolvedValue({
      data: page([
        makeProject({ id: 1, name: 'Alpha', latest_score: 92 }),
        makeProject({ id: 2, name: 'Beta', primary_language: null, latest_score: null, last_scanned_at: null }),
      ]),
    });
    renderPage();
    expect(await screen.findByRole('link', { name: 'Alpha' })).toHaveAttribute('href', '/projects/1');
    expect(screen.getByRole('link', { name: 'Beta' })).toHaveAttribute('href', '/projects/2');
    expect(screen.getAllByTestId('project-card')).toHaveLength(2);
    expect(screen.getByText('Language unknown')).toBeInTheDocument();
    expect(screen.getByText('Never scanned')).toBeInTheDocument();
    expect(api.get).toHaveBeenCalledWith('/projects', { params: { page: 1, size: 12 } });
    // a single page -> no pager
    expect(screen.queryByRole('navigation', { name: 'Pagination' })).not.toBeInTheDocument();
  });

  it('paginates', async () => {
    api.get.mockImplementation((_url: string, opts: { params: { page: number } }) =>
      Promise.resolve({
        data: page([makeProject({ id: opts.params.page, name: `Project p${opts.params.page}` })], 30, opts.params.page),
      }),
    );
    renderPage();
    expect(await screen.findByText('Page 1 of 3')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Previous' })).toBeDisabled();
    await userEvent.setup().click(screen.getByRole('button', { name: 'Next' }));
    expect(await screen.findByText('Page 2 of 3')).toBeInTheDocument();
    await waitFor(() => expect(screen.getByRole('link', { name: 'Project p2' })).toBeInTheDocument());
  });

  it('shows an error alert when loading fails', async () => {
    api.get.mockRejectedValue(httpError(500, 'Database unavailable'));
    renderPage();
    expect(await screen.findByText('Database unavailable')).toBeInTheDocument();
  });

  it('header button navigates to the new-project page', async () => {
    api.get.mockResolvedValue({ data: page([makeProject()]) });
    renderPage();
    await screen.findByTestId('project-card');
    await userEvent.setup().click(screen.getByRole('button', { name: 'Add project' }));
    expect(await screen.findByText('new project form')).toBeInTheDocument();
  });
});
