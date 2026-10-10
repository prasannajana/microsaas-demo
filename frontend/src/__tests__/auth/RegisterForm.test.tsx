import { screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { Route, Routes } from 'react-router-dom';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { renderWithProviders } from '../test-utils';
import { apiMock, testTokens, testUser } from './mockApi';

vi.mock('../../services/api', async () => {
  const { apiMock: mock } = await import('./mockApi');
  return { default: mock, API_BASE_URL: 'http://api.test/api/v1' };
});

const { RegisterForm } = await import('../../components/auth/RegisterForm');
const { AuthProvider } = await import('../../context/AuthContext');
const { default: RegisterPage } = await import('../../pages/RegisterPage');

async function fillForm(password: string, confirm: string) {
  await userEvent.type(screen.getByLabelText('Email'), 'new@example.com');
  await userEvent.type(screen.getByLabelText('Password'), password);
  await userEvent.type(screen.getByLabelText('Confirm password'), confirm);
  await userEvent.click(screen.getByRole('button', { name: /create account/i }));
}

describe('RegisterForm', () => {
  beforeEach(() => {
    window.localStorage.clear();
    vi.clearAllMocks();
  });

  it('blocks submission when passwords do not match', async () => {
    const onSubmit = vi.fn().mockResolvedValue(undefined);
    renderWithProviders(<RegisterForm onSubmit={onSubmit} />);

    await fillForm('password123', 'password124');

    expect(await screen.findByText('Passwords do not match')).toBeInTheDocument();
    expect(onSubmit).not.toHaveBeenCalled();
  });

  it('enforces the minimum password length', async () => {
    const onSubmit = vi.fn().mockResolvedValue(undefined);
    renderWithProviders(<RegisterForm onSubmit={onSubmit} />);

    await fillForm('short', 'short');

    expect(await screen.findByText('Password must be at least 8 characters')).toBeInTheDocument();
    expect(onSubmit).not.toHaveBeenCalled();
  });

  it('registers and sends the new user to /projects/new', async () => {
    apiMock.post.mockResolvedValue({ data: testTokens });
    apiMock.get.mockResolvedValue({ data: { ...testUser, email: 'new@example.com' } });

    renderWithProviders(
      <AuthProvider>
        <Routes>
          <Route path="/register" element={<RegisterPage />} />
          <Route path="/projects/new" element={<p>new project page</p>} />
          <Route path="/dashboard" element={<p>dashboard page</p>} />
        </Routes>
      </AuthProvider>,
      { route: '/register' },
    );

    await fillForm('password123', 'password123');

    expect(await screen.findByText('new project page')).toBeInTheDocument();
    expect(apiMock.post).toHaveBeenCalledWith('/auth/register', {
      email: 'new@example.com',
      password: 'password123',
    });
  });
});
