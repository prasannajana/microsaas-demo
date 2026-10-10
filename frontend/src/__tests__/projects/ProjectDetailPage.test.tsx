import { screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { Route, Routes } from 'react-router-dom';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import type { ProjectDetail, ScanDetail, ScanSummary } from '../../types';
import { httpError, makeFinding, makeProjectDetail, makeScan, makeScanDetail } from '../fixtures';
import { renderWithProviders } from '../test-utils';

const api = vi.hoisted(() => ({ get: vi.fn(), post: vi.fn(), put: vi.fn(), delete: vi.fn() }));
vi.mock('../../services/api', () => ({ default: api }));

const { default: ProjectDetailPage } = await import('../../pages/ProjectDetailPage');

interface State {
  project: ProjectDetail | Error;
  scans: ScanSummary[];
  scanDetails: Record<number, ScanDetail>;
}

let state: State;

function setup(route = '/projects/7') {
  api.get.mockImplementation((url: string) => {
    if (url === '/projects/7') {
      return state.project instanceof Error ? Promise.reject(state.project) : Promise.resolve({ data: state.project });
    }
    if (url === '/projects/7/scans') return Promise.resolve({ data: state.scans });
    const m = /^\/scans\/(\d+)$/.exec(url);
    if (m) {
      const detail = state.scanDetails[Number(m[1])];
      return detail ? Promise.resolve({ data: detail }) : Promise.reject(httpError(404, 'Scan not found'));
    }
    return Promise.reject(new Error(`unexpected GET ${url}`));
  });
  return renderWithProviders(
    <Routes>
      <Route path="/projects/:id" element={<ProjectDetailPage />} />
      <Route path="/projects" element={<p>projects list</p>} />
    </Routes>,
    { route },
  );
}

describe('ProjectDetailPage', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    const completed = makeScanDetail({ id: 3, score: 80, findings: [makeFinding({ id: 1, title: 'No README' })] });
    state = {
      project: makeProjectDetail({ latest_scan: completed }),
      scans: [makeScan({ id: 3, score: 80 }), makeScan({ id: 2, score: 60, created_at: '2026-09-30T10:00:00Z' })],
      scanDetails: { 3: completed },
    };
  });

  it('renders project header, report and history with an enabled Run scan button', async () => {
    setup();
    expect(await screen.findByRole('heading', { name: 'Hello World' })).toBeInTheDocument();
    expect(screen.getByRole('link', { name: /octocat\/Hello-World on GitHub/ })).toHaveAttribute(
      'href',
      'https://github.com/octocat/Hello-World',
    );
    expect(screen.getByText('Python')).toBeInTheDocument();
    expect(screen.getByText('Branch: default')).toBeInTheDocument();
    expect(await screen.findByText('No README')).toBeInTheDocument();
    expect(screen.getByRole('table', { name: 'Scan history' })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Run scan' })).toBeEnabled();
  });

  it('disables Run scan and shows progress while the newest scan is running', async () => {
    const running = makeScanDetail({ id: 4, status: 'running', score: null, findings: [] });
    state.scans = [makeScan({ id: 4, status: 'running', score: null }), ...state.scans];
    state.scanDetails[4] = running;
    setup();
    const button = await screen.findByRole('button', { name: 'Scan in progress' });
    expect(button).toBeDisabled();
    expect(await screen.findByText('Scanning repository…')).toBeInTheDocument();
  });

  it('disables Run scan while queued', async () => {
    state.scans = [makeScan({ id: 5, status: 'queued', score: null }), ...state.scans];
    state.scanDetails[5] = makeScanDetail({ id: 5, status: 'queued', score: null, findings: [] });
    setup();
    expect(await screen.findByRole('button', { name: 'Scan in progress' })).toBeDisabled();
    expect(await screen.findByText('Scan queued')).toBeInTheDocument();
  });

  it('shows a warning toast when starting a scan returns 409', async () => {
    api.post.mockRejectedValue(httpError(409, 'A scan is already in progress for this project'));
    setup();
    const user = userEvent.setup();
    await user.click(await screen.findByRole('button', { name: 'Run scan' }));
    expect(await screen.findByText('A scan is already in progress')).toBeInTheDocument();
    expect(screen.getByText('A scan is already in progress for this project')).toBeInTheDocument();
    expect(api.post).toHaveBeenCalledWith('/projects/7/scans');
  });

  it('shows a rate-limit toast on 429', async () => {
    api.post.mockRejectedValue(httpError(429, 'Scan limit reached (10 per hour). Please try again later.'));
    setup();
    const user = userEvent.setup();
    await user.click(await screen.findByRole('button', { name: 'Run scan' }));
    expect(await screen.findByText('Scan limit reached')).toBeInTheDocument();
  });

  it('starting a scan shows a toast and disables the button for the new queued scan', async () => {
    const queued = makeScan({ id: 9, status: 'queued', score: null });
    api.post.mockImplementation(() => {
      // The server now lists the new scan first (the page re-fetches history after starting).
      state.scans = [queued, ...state.scans];
      return Promise.resolve({ data: queued });
    });
    state.scanDetails[9] = makeScanDetail({ id: 9, status: 'queued', score: null, findings: [] });
    setup();
    const user = userEvent.setup();
    await user.click(await screen.findByRole('button', { name: 'Run scan' }));
    expect(await screen.findByText('Scan started')).toBeInTheDocument();
    await waitFor(() => expect(screen.getByRole('button', { name: 'Scan in progress' })).toBeDisabled());
  });

  it('shows the first-scan empty state when there are no scans', async () => {
    state.project = makeProjectDetail({ latest_scan: null, latest_score: null, last_scanned_at: null });
    state.scans = [];
    setup();
    expect(await screen.findByText('No scans yet')).toBeInTheDocument();
    expect(screen.getByText('Not scanned yet')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Run first scan' })).toBeEnabled();
    expect(screen.queryByRole('table', { name: 'Scan history' })).not.toBeInTheDocument();
  });

  it('shows a failed-scan banner with the error message and a retry button', async () => {
    state.scans = [makeScan({ id: 6, status: 'failed', score: null, error_message: 'Repository not found or is private' })];
    state.scanDetails[6] = makeScanDetail({
      id: 6,
      status: 'failed',
      score: null,
      error_message: 'Repository not found or is private',
      findings: [],
    });
    api.post.mockResolvedValue({ data: makeScan({ id: 10, status: 'queued', score: null }) });
    setup();
    expect(await screen.findByText('Scan failed')).toBeInTheDocument();
    expect(screen.getByText('Repository not found or is private')).toBeInTheDocument();
    const user = userEvent.setup();
    await user.click(screen.getByRole('button', { name: 'Retry scan' }));
    expect(api.post).toHaveBeenCalledWith('/projects/7/scans');
  });

  it('shows "Project not found" for an invalid id without calling the API', async () => {
    setup('/projects/abc');
    expect(await screen.findByText('Project not found')).toBeInTheDocument();
    expect(api.get).not.toHaveBeenCalled();
  });

  it('shows the API error when the project cannot be loaded (e.g. 404 for another user)', async () => {
    state.project = httpError(404, 'Project not found');
    setup();
    expect(await screen.findByText('Project not found')).toBeInTheDocument();
  });

  it('edits the project through the modal', async () => {
    api.put.mockResolvedValue({ data: { ...makeProjectDetail(), name: 'Renamed', default_branch: 'dev' } });
    setup();
    const user = userEvent.setup();
    await user.click(await screen.findByRole('button', { name: 'Edit' }));
    const dialog = await screen.findByRole('dialog');
    const name = within(dialog).getByLabelText(/Project name/);
    await user.clear(name);
    await user.type(name, 'Renamed');
    await user.type(within(dialog).getByLabelText(/Branch/), 'dev');
    await user.click(within(dialog).getByRole('button', { name: 'Save changes' }));
    await waitFor(() => expect(api.put).toHaveBeenCalledWith('/projects/7', { name: 'Renamed', default_branch: 'dev' }));
    expect(await screen.findByText('Project updated')).toBeInTheDocument();
  });

  it('validates the edit form before submitting', async () => {
    setup();
    const user = userEvent.setup();
    await user.click(await screen.findByRole('button', { name: 'Edit' }));
    const dialog = await screen.findByRole('dialog');
    await user.clear(within(dialog).getByLabelText(/Project name/));
    await user.type(within(dialog).getByLabelText(/Branch/), '..bad branch');
    await user.click(within(dialog).getByRole('button', { name: 'Save changes' }));
    expect(await within(dialog).findByText('Project name is required.')).toBeInTheDocument();
    expect(within(dialog).getByText(/Enter a valid branch name/)).toBeInTheDocument();
    expect(api.put).not.toHaveBeenCalled();
  });

  it('shows an error toast when the edit fails', async () => {
    api.put.mockRejectedValue(httpError(400, 'Invalid branch name'));
    setup();
    const user = userEvent.setup();
    await user.click(await screen.findByRole('button', { name: 'Edit' }));
    const dialog = await screen.findByRole('dialog');
    await user.click(within(dialog).getByRole('button', { name: 'Save changes' }));
    expect(await screen.findByText('Could not update project')).toBeInTheDocument();
  });

  it('deletes the project and navigates back to the list', async () => {
    api.delete.mockResolvedValue({ data: undefined });
    setup();
    const user = userEvent.setup();
    await user.click(await screen.findByRole('button', { name: 'Delete' }));
    const dialog = await screen.findByRole('dialog');
    await user.click(within(dialog).getByRole('button', { name: 'Delete project' }));
    expect(await screen.findByText('projects list')).toBeInTheDocument();
    expect(api.delete).toHaveBeenCalledWith('/projects/7');
  });

  it('shows an error toast when delete fails', async () => {
    api.delete.mockRejectedValue(httpError(500, 'boom'));
    setup();
    const user = userEvent.setup();
    await user.click(await screen.findByRole('button', { name: 'Delete' }));
    const dialog = await screen.findByRole('dialog');
    await user.click(within(dialog).getByRole('button', { name: 'Delete project' }));
    expect(await screen.findByText('Could not delete project')).toBeInTheDocument();
  });
});
