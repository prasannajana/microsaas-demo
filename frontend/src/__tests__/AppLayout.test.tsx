import { screen } from '@testing-library/react';
import { Route, Routes } from 'react-router-dom';
import { describe, expect, it, vi } from 'vitest';
import type { AuthContextValue } from '../context/AuthContext';
import type { User } from '../types';
import { renderWithProviders } from './test-utils';

const baseUser: User = {
  id: 1,
  email: 'dev@example.com',
  full_name: 'Dev User',
  is_active: true,
  is_verified: true,
  is_admin: false,
  oauth_provider: null,
  avatar_url: null,
  created_at: '2026-10-10T00:00:00Z',
};

const authState: { user: User | null } = { user: baseUser };

vi.mock('../context/AuthContext', () => ({
  useAuth: (): AuthContextValue => ({
    user: authState.user,
    isLoading: false,
    login: vi.fn(),
    register: vi.fn(),
    logout: vi.fn(),
    setTokens: vi.fn(),
    refreshUser: vi.fn(),
  }),
}));

const { AppLayout } = await import('../components/layout/AppLayout');
const { ProtectedRoute } = await import('../components/auth/ProtectedRoute');

function renderShell(route: string) {
  return renderWithProviders(
    <Routes>
      <Route path="/login" element={<p>login page</p>} />
      <Route element={<ProtectedRoute />}>
        <Route element={<AppLayout />}>
          <Route path="/dashboard" element={<p>dashboard body</p>} />
        </Route>
      </Route>
    </Routes>,
    { route },
  );
}

describe('AppLayout', () => {
  it('shows brand and nav, hides Admin for non-admins', () => {
    authState.user = baseUser;
    renderShell('/dashboard');
    expect(screen.getByText('Project Verification')).toBeInTheDocument();
    expect(screen.getByText('dashboard body')).toBeInTheDocument();
    expect(screen.queryAllByText('Admin')).toHaveLength(0);
  });

  it('shows Admin link for admins', () => {
    authState.user = { ...baseUser, is_admin: true };
    renderShell('/dashboard');
    expect(screen.getAllByText('Admin').length).toBeGreaterThan(0);
  });

  it('redirects signed-out users to /login', () => {
    authState.user = null;
    renderShell('/dashboard');
    expect(screen.getByText('login page')).toBeInTheDocument();
  });
});
