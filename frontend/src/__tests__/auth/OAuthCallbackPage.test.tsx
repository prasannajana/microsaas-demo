import { screen, waitFor } from '@testing-library/react';
import { Route, Routes } from 'react-router-dom';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { renderWithProviders } from '../test-utils';
import { apiMock, testUser } from './mockApi';

vi.mock('../../services/api', async () => {
  const { apiMock: mock } = await import('./mockApi');
  return { default: mock, API_BASE_URL: 'http://api.test/api/v1' };
});

const { AuthProvider } = await import('../../context/AuthContext');
const { default: OAuthCallbackPage } = await import('../../pages/OAuthCallbackPage');
const { ACCESS_TOKEN_KEY, REFRESH_TOKEN_KEY } = await import('../../lib/tokens');
const { OAUTH_NONCE_KEY } = await import('../../lib/oauthNonce');

const NONCE = 'Abc_123-xyzXYZ_0987654321';

function renderCallback() {
  return renderWithProviders(
    <AuthProvider>
      <Routes>
        <Route path="/auth/callback" element={<OAuthCallbackPage />} />
        <Route path="/dashboard" element={<p>dashboard page</p>} />
        <Route path="/login" element={<p>login page</p>} />
      </Routes>
    </AuthProvider>,
    { route: '/auth/callback' },
  );
}

describe('OAuthCallbackPage', () => {
  beforeEach(() => {
    window.localStorage.clear();
    window.sessionStorage.clear();
    vi.clearAllMocks();
  });

  afterEach(() => {
    window.history.replaceState(null, '', '/');
  });

  it('stores tokens from the URL fragment, clears it and navigates to /dashboard', async () => {
    window.sessionStorage.setItem(OAUTH_NONCE_KEY, NONCE);
    window.history.replaceState(
      null,
      '',
      `/auth/callback#access_token=oauth-access&refresh_token=oauth-refresh&nonce=${NONCE}`,
    );
    apiMock.get.mockResolvedValue({ data: testUser });

    renderCallback();

    expect(await screen.findByText('dashboard page')).toBeInTheDocument();
    expect(window.localStorage.getItem(ACCESS_TOKEN_KEY)).toBe('oauth-access');
    expect(window.localStorage.getItem(REFRESH_TOKEN_KEY)).toBe('oauth-refresh');
    expect(window.location.hash).toBe('');
    expect(apiMock.get).toHaveBeenCalledTimes(1);
    expect(window.sessionStorage.getItem(OAUTH_NONCE_KEY)).toBeNull(); // single use
  });

  it('rejects tokens whose nonce does not match the one stored by this tab', async () => {
    window.sessionStorage.setItem(OAUTH_NONCE_KEY, NONCE);
    window.history.replaceState(
      null,
      '',
      '/auth/callback#access_token=attacker-access&refresh_token=attacker-refresh&nonce=AttackerNonce_0123456789',
    );

    renderCallback();

    expect(await screen.findByText(/not started from this browser tab/i)).toBeInTheDocument();
    expect(window.localStorage.getItem(ACCESS_TOKEN_KEY)).toBeNull();
    expect(window.localStorage.getItem(REFRESH_TOKEN_KEY)).toBeNull();
    expect(apiMock.get).not.toHaveBeenCalled();
    await waitFor(() => expect(window.sessionStorage.getItem(OAUTH_NONCE_KEY)).toBeNull());
    await waitFor(() => expect(window.location.hash).toBe(''));
  });

  it('rejects tokens when this tab never started a Google sign-in (no stored nonce)', async () => {
    window.history.replaceState(
      null,
      '',
      `/auth/callback#access_token=attacker-access&refresh_token=attacker-refresh&nonce=${NONCE}`,
    );

    renderCallback();

    expect(await screen.findByText(/not started from this browser tab/i)).toBeInTheDocument();
    expect(window.localStorage.getItem(ACCESS_TOKEN_KEY)).toBeNull();
  });

  it('rejects tokens without a nonce in the fragment', async () => {
    window.sessionStorage.setItem(OAUTH_NONCE_KEY, NONCE);
    window.history.replaceState(null, '', '/auth/callback#access_token=a&refresh_token=r');

    renderCallback();

    expect(await screen.findByText(/not started from this browser tab/i)).toBeInTheDocument();
    expect(window.localStorage.getItem(ACCESS_TOKEN_KEY)).toBeNull();
  });

  it('shows a generic message for unknown error codes instead of echoing them', async () => {
    window.history.replaceState(null, '', '/auth/callback#error=Your_account_is_hacked_call_555');

    renderCallback();

    expect(await screen.findByText('Google sign-in failed. Please try again.')).toBeInTheDocument();
    expect(screen.queryByText(/hacked/i)).not.toBeInTheDocument();
    expect(screen.queryByText(/555/)).not.toBeInTheDocument();
  });

  it('maps known backend error codes to friendly messages', async () => {
    window.history.replaceState(null, '', '/auth/callback#error=account_disabled');

    renderCallback();

    expect(await screen.findByText('This account has been disabled.')).toBeInTheDocument();
  });

  it('shows an error and a way back to /login when the fragment contains #error', async () => {
    window.history.replaceState(null, '', '/auth/callback#error=access_denied');

    renderCallback();

    expect(await screen.findByText('Google sign-in was cancelled.')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /back to sign in/i })).toBeInTheDocument();
    expect(window.localStorage.getItem(ACCESS_TOKEN_KEY)).toBeNull();
    await waitFor(() => expect(window.location.hash).toBe(''));
    expect(apiMock.get).not.toHaveBeenCalled();
  });

  it('shows an error when no tokens are present', async () => {
    window.history.replaceState(null, '', '/auth/callback');

    renderCallback();

    expect(await screen.findByText(/no sign-in credentials were received/i)).toBeInTheDocument();
  });
});
