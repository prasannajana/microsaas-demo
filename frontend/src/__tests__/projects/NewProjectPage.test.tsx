import { screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import NewProjectPage from '../../pages/NewProjectPage';
import { projectService } from '../../services/projectService';
import { renderWithProviders } from '../test-utils';

vi.mock('../../services/projectService', () => ({
  projectService: { create: vi.fn() },
}));

describe('NewProjectPage', () => {
  beforeEach(() => {
    vi.mocked(projectService.create).mockReset();
  });

  it('shows a validation error for a non-GitHub URL and does not submit', async () => {
    const user = userEvent.setup();
    renderWithProviders(<NewProjectPage />, { route: '/projects/new' });

    await user.type(screen.getByLabelText(/github repository url/i), 'https://gitlab.com/owner/repo');
    await user.type(screen.getByLabelText(/project name/i), 'repo');
    await user.click(screen.getByRole('button', { name: /add project/i }));

    expect(await screen.findByText(/only github repositories are supported/i)).toBeInTheDocument();
    expect(projectService.create).not.toHaveBeenCalled();
  });

  it('auto-fills the project name from the repository URL', async () => {
    const user = userEvent.setup();
    renderWithProviders(<NewProjectPage />, { route: '/projects/new' });

    await user.type(screen.getByLabelText(/github repository url/i), 'https://github.com/acme/rocket.git');
    expect(screen.getByLabelText(/project name/i)).toHaveValue('rocket');
  });
});
