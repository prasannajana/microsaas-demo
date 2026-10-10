import { screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { Route, Routes } from 'react-router-dom';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { renderWithProviders } from '../test-utils';
import { apiMock, testTokens, testUser } from './mockApi';
import { httpError } from '../fixtures';

vi.mock('../../services/api', async () => {
  const { apiMock: mock } = await import('./mockApi');
  return { default: mock, API_BASE_URL: 'http://api.test/api/v1' };
});

const { LoginForm } = await import('../../components/auth/LoginForm');
const { AuthProvider } = await import('../../context/AuthContext');
const { default: LoginPage } = await import('../../pages/LoginPage');
const { default: RegisterPage } = await import('../../pages/RegisterPage');
const { ACCESS_TOKEN_KEY, REFRESH_TOKEN_KEY } = await import('../../lib/tokens');

describe('LoginForm', () => {
  beforeEach(() => {
    window.localStorage.clear();
    vi.clearAllMocks();
  });

  it('shows validation errors and does not submit when fields are empty', async () => {
    const onSubmit = vi.fn().mockResolvedValue(undefined);
    renderWithProviders(<LoginForm onSubmit={onSubmit} />);

    await userEvent.click(screen.getByRole('button', { name: /sign in/i }));

    expect(await screen.findByText('Email is required')).toBeInTheDocument();
    expect(screen.getByText('Password is required')).toBeInTheDocument();
    expect(onSubmit).not.toHaveBeenCalled();
  });

  it('rejects a malformed email', async () => {
    const onSubmit = vi.fn().mockResolvedValue(undefined);
    renderWithProviders(<LoginForm onSubmit={onSubmit} />);

    await userEvent.type(screen.getByLabelText('Email'), 'not-an-email');
    await userEvent.type(screen.getByLabelText('Password'), 'secret123');
    await userEvent.click(screen.getByRole('button', { name: /sign in/i }));

    expect(await screen.findByText('Enter a valid email address')).toBeInTheDocument();
    expect(onSubmit).not.toHaveBeenCalled();
  });

  it('logs in, stores tokens and navigates to /dashboard', async () => {
    apiMock.post.mockResolvedValue({ data: testTokens });
    apiMock.get.mockResolvedValue({ data: testUser });

    renderWithProviders(
      <AuthProvider>
        <Routes>
          <Route path="/login" element={<LoginPage />} />
          <Route path="/dashboard" element={<p>dashboard page</p>} />
        </Routes>
      </AuthProvider>,
      { route: '/login' },
    );

    await userEvent.type(screen.getByLabelText('Email'), 'dev@example.com');
    await userEvent.type(screen.getByLabelText('Password'), 'secret123');
    await userEvent.click(screen.getByRole('button', { name: /sign in/i }));

    expect(await screen.findByText('dashboard page')).toBeInTheDocument();
    expect(apiMock.post).toHaveBeenCalledWith('/auth/login', { email: 'dev@example.com', password: 'secret123' });
    expect(apiMock.get).toHaveBeenCalledWith('/auth/me');
    expect(window.localStorage.getItem(ACCESS_TOKEN_KEY)).toBe(testTokens.access_token);
    expect(window.localStorage.getItem(REFRESH_TOKEN_KEY)).toBe(testTokens.refresh_token);
  });

  it('shows the server error and stays on the page when credentials are wrong', async () => {
    apiMock.post.mockRejectedValue(new Error('Incorrect email or password'));

    renderWithProviders(
      <AuthProvider>
        <Routes>
          <Route path="/login" element={<LoginPage />} />
          <Route path="/dashboard" element={<p>dashboard page</p>} />
        </Routes>
      </AuthProvider>,
      { route: '/login' },
    );

    await userEvent.type(screen.getByLabelText('Email'), 'dev@example.com');
    await userEvent.type(screen.getByLabelText('Password'), 'wrongpass');
    await userEvent.click(screen.getByRole('button', { name: /sign in/i }));

    expect(await screen.findByText('Incorrect email or password')).toBeInTheDocument();
    await waitFor(() => expect(screen.getByRole('button', { name: /^sign in$/i })).not.toBeDisabled());
    expect(screen.queryByText('dashboard page')).not.toBeInTheDocument();
  });

  it('explains a 401 inline and offers to register with the same email', async () => {
    apiMock.post.mockRejectedValue(httpError(401, 'Invalid email or password'));

    renderWithProviders(
      <AuthProvider>
        <Routes>
          <Route path="/login" element={<LoginPage />} />
          <Route path="/register" element={<RegisterPage />} />
        </Routes>
      </AuthProvider>,
      { route: '/login' },
    );

    await userEvent.type(screen.getByLabelText('Email'), 'new@example.com');
    await userEvent.type(screen.getByLabelText('Password'), 'whatever1');
    await userEvent.click(screen.getByRole('button', { name: /^sign in$/i }));

    expect(await screen.findByRole('alert')).toHaveTextContent('Incorrect email or password.');
    await userEvent.click(screen.getByRole('link', { name: /create one with this email/i }));
    expect(await screen.findByLabelText('Email')).toHaveValue('new@example.com');
  });

  it('clears the inline error when the form is resubmitted', async () => {
    const onSubmit = vi.fn().mockRejectedValueOnce(httpError(401)).mockResolvedValueOnce(undefined);
    renderWithProviders(<LoginForm onSubmit={onSubmit} />);

    await userEvent.type(screen.getByLabelText('Email'), 'dev@example.com');
    await userEvent.type(screen.getByLabelText('Password'), 'password1');
    await userEvent.click(screen.getByRole('button', { name: /^sign in$/i }));
    expect(await screen.findByRole('alert')).toBeInTheDocument();

    await userEvent.click(screen.getByRole('button', { name: /^sign in$/i }));
    await waitFor(() => expect(screen.queryByRole('alert')).not.toBeInTheDocument());
  });
});
