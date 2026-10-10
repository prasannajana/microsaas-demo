import { vi } from 'vitest';
import type { TokenPair, User } from '../../types';

export const apiMock = {
  get: vi.fn(),
  post: vi.fn(),
  put: vi.fn(),
};

export const testUser: User = {
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

export const testTokens: TokenPair = {
  access_token: 'access-123',
  refresh_token: 'refresh-456',
  token_type: 'bearer',
};
