import api, { API_BASE_URL } from './api';
import { createOAuthNonce } from '../lib/oauthNonce';
import type { UpdateMeRequest, User } from '../types';

/** PUT /auth/me — update the current user's profile. */
export async function updateMe(payload: UpdateMeRequest): Promise<User> {
  const { data } = await api.put<User>('/auth/me', payload);
  return data;
}

/** Absolute URL that starts the Google OAuth flow (backend redirects to Google). */
export const GOOGLE_LOGIN_URL = `${API_BASE_URL}/auth/google`;

/** Build the Google login URL carrying the login-CSRF nonce. */
export function buildGoogleLoginUrl(nonce: string): string {
  return `${GOOGLE_LOGIN_URL}?${new URLSearchParams({ nonce }).toString()}`;
}

/** Create + store a fresh nonce and return the URL that starts the Google flow. */
export function startGoogleLoginUrl(): string {
  return buildGoogleLoginUrl(createOAuthNonce());
}

export interface OAuthFragment {
  accessToken: string | null;
  refreshToken: string | null;
  error: string | null;
  nonce: string | null;
}

/** Parse `#access_token=…&refresh_token=…&nonce=…` or `#error=…` from a URL fragment. */
export function parseOAuthFragment(hash: string): OAuthFragment {
  const params = new URLSearchParams(hash.startsWith('#') ? hash.slice(1) : hash);
  return {
    accessToken: params.get('access_token'),
    refreshToken: params.get('refresh_token'),
    error: params.get('error'),
    nonce: params.get('nonce'),
  };
}

const EMAIL_PATTERN = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;

export function isValidEmail(value: string): boolean {
  return EMAIL_PATTERN.test(value.trim());
}

export const MIN_PASSWORD_LENGTH = 8;
