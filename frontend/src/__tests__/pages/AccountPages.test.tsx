import { screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { Route, Routes } from 'react-router-dom';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import type { AuthContextValue } from '../../context/AuthContext';
import { authValue, httpError, makeUser } from '../fixtures';
import { renderWithProviders } from '../test-utils';

const auth = vi.hoisted(() => ({ value: null as AuthContextValue | null }));
vi.mock('../../context/AuthContext', () => ({
  useAuth: (): AuthContextValue => auth.value as AuthContextValue,
}));

const api = vi.hoisted(() => ({ get: vi.fn(), put: vi.fn() }));
vi.mock('../../services/api', () => ({ default: api, API_BASE_URL: 'http://api/api/v1' }));

const { default: ProfilePage } = await import('../../pages/ProfilePage');
const { default: SettingsPage } = await import('../../pages/SettingsPage');
const { default: ForgotPasswordPage } = await import('../../pages/ForgotPasswordPage');
const { default: NotFoundPage } = await import('../../pages/NotFoundPage');
const { default: AdminDashboardPage } = await import('../../pages/AdminDashboardPage');

function renderRoutes(route: string) {
  return renderWithProviders(
    <Routes>
      <Route path="/" element={<p>home page</p>} />
      <Route path="/login" element={<p>login page</p>} />
      <Route path="/profile" element={<ProfilePage />} />
      <Route path="/settings" element={<SettingsPage />} />
      <Route path="/forgot-password" element={<ForgotPasswordPage />} />
      <Route path="/admin" element={<AdminDashboardPage />} />
      <Route path="/admin/users" element={<p>admin users page</p>} />
      <Route path="*" element={<NotFoundPage />} />
    </Routes>,
    { route },
  );
}

describe('ProfilePage', () => {
  const refreshUser = vi.fn(() => Promise.resolve());

  beforeEach(() => {
    vi.clearAllMocks();
    auth.value = authValue(makeUser({ full_name: 'Ada', is_admin: true, oauth_provider: 'google' }), { refreshUser });
  });

  it('shows account details', () => {
    renderRoutes('/profile');
    expect(screen.getByText('dev@example.com')).toBeInTheDocument();
    expect(screen.getByText('Google')).toBeInTheDocument();
    expect(screen.getByText('Admin')).toBeInTheDocument();
    expect(screen.getByText('Verified')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Save changes' })).toBeDisabled(); // unchanged
  });

  it('saves a new name and refreshes the user', async () => {
    api.put.mockResolvedValue({ data: makeUser({ full_name: 'Ada L' }) });
    renderRoutes('/profile');
    const user = userEvent.setup();
    const input = screen.getByLabelText(/Full name/);
    await user.clear(input);
    await user.type(input, '  Ada L ');
    await user.click(screen.getByRole('button', { name: 'Save changes' }));
    await waitFor(() => expect(api.put).toHaveBeenCalledWith('/auth/me', { full_name: 'Ada L' }));
    expect(await screen.findByText('Profile updated')).toBeInTheDocument();
    expect(refreshUser).toHaveBeenCalled();
  });

  it('validates an empty name and shows API errors', async () => {
    renderRoutes('/profile');
    const user = userEvent.setup();
    const input = screen.getByLabelText(/Full name/);
    await user.clear(input);
    await user.type(input, '   ');
    await user.click(screen.getByRole('button', { name: 'Save changes' }));
    expect(await screen.findByText('Full name cannot be empty')).toBeInTheDocument();
    expect(api.put).not.toHaveBeenCalled();

    api.put.mockRejectedValue(httpError(422, [{ msg: 'String should have at most 255 characters' }]));
    await user.clear(input);
    await user.type(input, 'Valid');
    await user.click(screen.getByRole('button', { name: 'Save changes' }));
    expect(await screen.findByText('Could not update profile')).toBeInTheDocument();
  });

  it('renders nothing when signed out', () => {
    auth.value = authValue(null);
    const { container } = renderRoutes('/profile');
    expect(container.textContent).toBe('');
  });
});

describe('SettingsPage', () => {
  it('signs out and goes to /login', async () => {
    const logout = vi.fn(() => Promise.resolve());
    auth.value = authValue(makeUser(), { logout });
    renderRoutes('/settings');
    expect(screen.getByText('dev@example.com')).toBeInTheDocument();
    await userEvent.setup().click(screen.getByRole('button', { name: 'Sign out' }));
    expect(await screen.findByText('login page')).toBeInTheDocument();
    expect(logout).toHaveBeenCalledOnce();
  });
});

describe('ForgotPasswordPage', () => {
  it('validates the email and never calls the API', async () => {
    auth.value = authValue(null);
    renderRoutes('/forgot-password');
    const user = userEvent.setup();
    await user.type(screen.getByLabelText(/Email/), 'nope');
    await user.click(screen.getByRole('button', { name: 'Continue' }));
    expect(await screen.findByText('Enter a valid email address')).toBeInTheDocument();
    await user.clear(screen.getByLabelText(/Email/));
    await user.type(screen.getByLabelText(/Email/), 'me@example.com');
    await user.click(screen.getByRole('button', { name: 'Continue' }));
    expect(await screen.findByText(/contact\s+support from me@example.com/)).toBeInTheDocument();
    expect(api.get).not.toHaveBeenCalled();
    expect(api.put).not.toHaveBeenCalled();
  });
});

describe('NotFoundPage', () => {
  it('links back home', async () => {
    auth.value = authValue(null);
    renderRoutes('/does/not/exist');
    expect(screen.getByText('The page you are looking for does not exist.')).toBeInTheDocument();
    await userEvent.setup().click(screen.getByRole('button', { name: 'Go home' }));
    expect(await screen.findByText('home page')).toBeInTheDocument();
  });
});

describe('AdminDashboardPage', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    auth.value = authValue(makeUser({ is_admin: true }));
  });

  it('shows platform stats and navigates to sub-pages', async () => {
    api.get.mockResolvedValue({
      data: { user_count: 12, project_count: 30, scan_count: 99, scans_last_24h: 4, failure_rate: 0.25 },
    });
    renderRoutes('/admin');
    expect(await screen.findByText('25.0%')).toBeInTheDocument();
    expect(screen.getByText('99')).toBeInTheDocument();
    expect(api.get).toHaveBeenCalledWith('/admin/stats');
    await userEvent.setup().click(screen.getByRole('button', { name: 'Manage users' }));
    expect(await screen.findByText('admin users page')).toBeInTheDocument();
  });

  it('shows an error alert on failure', async () => {
    api.get.mockRejectedValue(httpError(403, 'Admin access required'));
    renderRoutes('/admin');
    expect(await screen.findByText('Admin access required')).toBeInTheDocument();
  });
});
