import { screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import type { AuthContextValue } from '../../context/AuthContext';
import type { Page, User } from '../../types';
import { renderWithProviders } from '../test-utils';

const admin: User = {
  id: 1,
  email: 'admin@example.com',
  full_name: 'Admin User',
  is_active: true,
  is_verified: true,
  is_admin: true,
  oauth_provider: null,
  avatar_url: null,
  created_at: '2026-10-01T00:00:00Z',
};

const other: User = {
  ...admin,
  id: 2,
  email: 'dev@example.com',
  full_name: 'Dev User',
  is_admin: false,
  oauth_provider: 'google',
};

vi.mock('../../context/AuthContext', () => ({
  useAuth: (): AuthContextValue => ({
    user: admin,
    isLoading: false,
    login: vi.fn(),
    register: vi.fn(),
    logout: vi.fn(),
    setTokens: vi.fn(),
    refreshUser: vi.fn(),
  }),
}));

const usersPage: Page<User> = { items: [admin, other], total: 2, page: 1, size: 20 };

vi.mock('../../services/api', () => ({
  default: {
    get: () => Promise.resolve({ data: usersPage }),
    put: () => Promise.resolve({ data: other }),
  },
}));

const { default: AdminUsersPage } = await import('../../pages/AdminUsersPage');

describe('AdminUsersPage', () => {
  it("disables the switches on the current admin's own row only", async () => {
    renderWithProviders(<AdminUsersPage />);

    const ownActive = await screen.findByRole('checkbox', { name: 'Active status for admin@example.com' });
    const ownAdmin = screen.getByRole('checkbox', { name: 'Admin access for admin@example.com' });
    expect(ownActive).toBeDisabled();
    expect(ownAdmin).toBeDisabled();

    expect(screen.getByRole('checkbox', { name: 'Active status for dev@example.com' })).toBeEnabled();
    expect(screen.getByRole('checkbox', { name: 'Admin access for dev@example.com' })).toBeEnabled();
  });
});
