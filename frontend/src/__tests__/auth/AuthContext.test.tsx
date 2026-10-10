import type { ReactNode } from 'react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { act, renderHook, waitFor } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { AuthProvider, useAuth } from '../../context/AuthContext';
import { getAccessToken, getRefreshToken, setTokens } from '../../lib/tokens';
import { httpError, makeUser } from '../fixtures';

const api = vi.hoisted(() => ({ get: vi.fn(), post: vi.fn() }));
vi.mock('../../services/api', () => ({ default: api }));

const pair = { access_token: 'acc', refresh_token: 'ref', token_type: 'bearer' as const };

function setup(client = new QueryClient()) {
  function wrapper({ children }: { children: ReactNode }) {
    return (
      <QueryClientProvider client={client}>
        <AuthProvider>{children}</AuthProvider>
      </QueryClientProvider>
    );
  }
  return renderHook(() => useAuth(), { wrapper });
}

describe('AuthContext', () => {
  beforeEach(() => {
    window.localStorage.clear();
    api.get.mockReset();
    api.post.mockReset();
  });

  it('throws when used outside the provider', () => {
    const spy = vi.spyOn(console, 'error').mockImplementation(() => undefined);
    expect(() => renderHook(() => useAuth())).toThrow('useAuth must be used within an AuthProvider');
    spy.mockRestore();
  });

  it('starts signed-out and not loading without a stored token', () => {
    const { result } = setup();
    expect(result.current.user).toBeNull();
    expect(result.current.isLoading).toBe(false);
    expect(api.get).not.toHaveBeenCalled();
  });

  it('loads /auth/me at boot when a token is stored', async () => {
    setTokens('stored', 'stored-r');
    api.get.mockResolvedValue({ data: makeUser({ email: 'boot@example.com' }) });
    const { result } = setup();
    expect(result.current.isLoading).toBe(true);
    await waitFor(() => expect(result.current.isLoading).toBe(false));
    expect(result.current.user?.email).toBe('boot@example.com');
    expect(api.get).toHaveBeenCalledWith('/auth/me');
  });

  it('clears stored tokens when the boot /auth/me fails', async () => {
    setTokens('stale', 'stale-r');
    api.get.mockRejectedValue(httpError(401, 'Not authenticated'));
    const { result } = setup();
    await waitFor(() => expect(result.current.isLoading).toBe(false));
    expect(result.current.user).toBeNull();
    expect(getAccessToken()).toBeNull();
    expect(getRefreshToken()).toBeNull();
  });

  it('login stores tokens and loads the user', async () => {
    api.post.mockResolvedValue({ data: pair });
    api.get.mockResolvedValue({ data: makeUser() });
    const { result } = setup();
    await act(() => result.current.login('dev@example.com', 'password123'));
    expect(api.post).toHaveBeenCalledWith('/auth/login', { email: 'dev@example.com', password: 'password123' });
    expect(getAccessToken()).toBe('acc');
    expect(getRefreshToken()).toBe('ref');
    expect(result.current.user?.email).toBe('dev@example.com');
  });

  it('login failure propagates and leaves the user signed out', async () => {
    api.post.mockRejectedValue(httpError(401, 'Invalid email or password'));
    const { result } = setup();
    await expect(act(() => result.current.login('x@example.com', 'bad'))).rejects.toBeDefined();
    expect(result.current.user).toBeNull();
    expect(getAccessToken()).toBeNull();
  });

  it('register trims the optional full name and omits it when blank', async () => {
    api.post.mockResolvedValue({ data: pair });
    api.get.mockResolvedValue({ data: makeUser() });
    const { result } = setup();
    await act(() => result.current.register('a@example.com', 'password123', '  Ada  '));
    expect(api.post).toHaveBeenLastCalledWith('/auth/register', {
      email: 'a@example.com',
      password: 'password123',
      full_name: 'Ada',
    });
    await act(() => result.current.register('b@example.com', 'password123', '   '));
    expect(api.post).toHaveBeenLastCalledWith('/auth/register', { email: 'b@example.com', password: 'password123' });
  });

  it('setTokens clears tokens and rethrows if /auth/me fails', async () => {
    api.get.mockRejectedValue(httpError(401, 'nope'));
    const { result } = setup();
    await expect(act(() => result.current.setTokens('a', 'r'))).rejects.toBeDefined();
    expect(getAccessToken()).toBeNull();
    expect(result.current.user).toBeNull();
  });

  it('logout revokes the refresh token, clears tokens, user and query cache', async () => {
    const client = new QueryClient();
    client.setQueryData(['projects'], ['cached']);
    api.post.mockResolvedValueOnce({ data: pair });
    api.get.mockResolvedValue({ data: makeUser() });
    const { result } = setup(client);
    await act(() => result.current.login('dev@example.com', 'password123'));

    api.post.mockResolvedValueOnce({ data: undefined });
    await act(() => result.current.logout());
    expect(api.post).toHaveBeenLastCalledWith('/auth/logout', { refresh_token: 'ref' });
    expect(result.current.user).toBeNull();
    expect(getAccessToken()).toBeNull();
    expect(client.getQueryData(['projects'])).toBeUndefined();
  });

  it('logout still clears local state when the server call fails', async () => {
    setTokens('a', 'r');
    api.get.mockResolvedValue({ data: makeUser() });
    const { result } = setup();
    await waitFor(() => expect(result.current.user).not.toBeNull());
    api.post.mockRejectedValue(new Error('network'));
    await act(() => result.current.logout());
    expect(result.current.user).toBeNull();
    expect(getRefreshToken()).toBeNull();
  });

  it('logout without a refresh token skips the API call', async () => {
    const { result } = setup();
    await act(() => result.current.logout());
    expect(api.post).not.toHaveBeenCalled();
  });

  it('refreshUser re-fetches the current user', async () => {
    api.get.mockResolvedValue({ data: makeUser({ full_name: 'Updated' }) });
    const { result } = setup();
    await act(() => result.current.refreshUser());
    expect(result.current.user?.full_name).toBe('Updated');
  });
});
