import { fireEvent, screen } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { renderWithProviders } from '../test-utils';

vi.mock('../../services/api', async () => {
  const { apiMock: mock } = await import('./mockApi');
  return { default: mock, API_BASE_URL: 'http://api.test/api/v1' };
});

const { GoogleLoginButton } = await import('../../components/auth/GoogleLoginButton');
const { NONCE_PATTERN, OAUTH_NONCE_KEY, clearOAuthNonce, createOAuthNonce, generateNonce, nonceMatches, peekOAuthNonce } =
  await import('../../lib/oauthNonce');
const { GENERIC_OAUTH_ERROR, describeOAuthError } = await import('../../lib/oauthErrors');
const { buildGoogleLoginUrl, parseOAuthFragment } = await import('../../services/authService');

describe('OAuth login-CSRF nonce', () => {
  beforeEach(() => window.sessionStorage.clear());

  it('generates distinct URL-safe nonces accepted by the backend format', () => {
    const a = generateNonce();
    const b = generateNonce();
    expect(a).not.toBe(b);
    expect(a).toMatch(NONCE_PATTERN);
    expect(a).toHaveLength(43);
  });

  it('stores the nonce in sessionStorage until cleared', () => {
    const nonce = createOAuthNonce();
    expect(window.sessionStorage.getItem(OAUTH_NONCE_KEY)).toBe(nonce);
    expect(peekOAuthNonce()).toBe(nonce);
    clearOAuthNonce();
    expect(peekOAuthNonce()).toBeNull();
  });

  it('compares nonces strictly', () => {
    const n = generateNonce();
    expect(nonceMatches(n, n)).toBe(true);
    const flipped = `${n.slice(0, -1)}${n.endsWith('A') ? 'B' : 'A'}`;
    expect(nonceMatches(n, flipped)).toBe(false);
    expect(nonceMatches(n, null)).toBe(false);
    expect(nonceMatches(null, n)).toBe(false);
    expect(nonceMatches('short', 'short')).toBe(false);
  });

  it('builds the login URL with the nonce and parses it back from the fragment', () => {
    expect(buildGoogleLoginUrl('abcdefghijklmnop_-')).toBe(
      'http://api.test/api/v1/auth/google?nonce=abcdefghijklmnop_-',
    );
    expect(parseOAuthFragment('#access_token=a&refresh_token=r&nonce=xyz').nonce).toBe('xyz');
  });

  it('never echoes unknown error codes', () => {
    expect(describeOAuthError('<script>alert(1)</script>')).toBe(GENERIC_OAUTH_ERROR);
    expect(describeOAuthError('toString')).toBe(GENERIC_OAUTH_ERROR);
    expect(describeOAuthError('access_denied')).toBe('Google sign-in was cancelled.');
    expect(describeOAuthError('google_not_configured')).toMatch(/isn't set up on this server/);
  });
});

describe('GoogleLoginButton', () => {
  const original = window.location;

  beforeEach(() => {
    window.sessionStorage.clear();
    Object.defineProperty(window, 'location', {
      configurable: true,
      value: { ...original, href: 'http://app.test/login' },
    });
  });

  afterEach(() => {
    Object.defineProperty(window, 'location', { configurable: true, value: original });
  });

  it('stores a nonce and navigates to /auth/google?nonce=<nonce>', () => {
    renderWithProviders(<GoogleLoginButton />);
    fireEvent.click(screen.getByRole('button', { name: /continue with google/i }));
    const stored = window.sessionStorage.getItem(OAUTH_NONCE_KEY);
    expect(stored).toMatch(NONCE_PATTERN);
    expect(window.location.href).toBe(`http://api.test/api/v1/auth/google?nonce=${stored}`);
  });
});
