/**
 * Login-CSRF protection for the Google OAuth redirect flow.
 *
 * Before leaving for Google the SPA stores a random nonce in sessionStorage (scoped to
 * this tab) and passes it to the backend, which binds it to its HttpOnly state cookie
 * and echoes it back in the callback fragment. The callback page only accepts tokens
 * whose nonce matches, so an attacker cannot force a victim's browser to sign in to the
 * attacker's account by sending them a crafted callback link.
 */
export const OAUTH_NONCE_KEY = 'pv_oauth_nonce';

/** Matches the backend's accepted format: URL-safe base64 alphabet, 16-128 chars. */
export const NONCE_PATTERN = /^[A-Za-z0-9_-]{16,128}$/;

function toBase64Url(bytes: Uint8Array): string {
  let binary = '';
  bytes.forEach((b) => {
    binary += String.fromCharCode(b);
  });
  return btoa(binary).replace(/\+/g, '-').replace(/\//g, '_').replace(/=+$/, '');
}

/** Generate a 256-bit random nonce (43 URL-safe characters). */
export function generateNonce(): string {
  const bytes = new Uint8Array(32);
  crypto.getRandomValues(bytes);
  return toBase64Url(bytes);
}

/** Create a nonce, remember it for this tab and return it. */
export function createOAuthNonce(): string {
  const nonce = generateNonce();
  try {
    window.sessionStorage.setItem(OAUTH_NONCE_KEY, nonce);
  } catch {
    // Storage unavailable: the callback will reject the response (fail closed).
  }
  return nonce;
}

/** Read the stored nonce without clearing it. */
export function peekOAuthNonce(): string | null {
  try {
    return window.sessionStorage.getItem(OAUTH_NONCE_KEY);
  } catch {
    return null;
  }
}

/** Forget the stored nonce (it is single use). */
export function clearOAuthNonce(): void {
  try {
    window.sessionStorage.removeItem(OAUTH_NONCE_KEY);
  } catch {
    // ignore
  }
}

/** Constant-time-ish comparison; both values must be present and well-formed. */
export function nonceMatches(expected: string | null, received: string | null): boolean {
  if (!expected || !received || !NONCE_PATTERN.test(expected) || expected.length !== received.length) {
    return false;
  }
  let diff = 0;
  for (let i = 0; i < expected.length; i += 1) {
    diff |= expected.charCodeAt(i) ^ received.charCodeAt(i);
  }
  return diff === 0;
}
