/** Known backend error codes. Anything else gets a generic message (never echoed). */
const OAUTH_ERROR_MESSAGES: Record<string, string> = {
  access_denied: 'Google sign-in was cancelled.',
  invalid_state: 'Your sign-in session expired. Please try again.',
  oauth_failed: 'Google sign-in failed. Please try again.',
  email_not_verified: 'Your Google email address is not verified.',
  account_disabled: 'This account has been disabled.',
  google_not_configured:
    "Google sign-in isn't set up on this server yet. Please sign in with your email and password.",
};

export const GENERIC_OAUTH_ERROR = 'Google sign-in failed. Please try again.';
export const NONCE_MISMATCH_ERROR =
  'This sign-in was not started from this browser tab. Please try again.';

/** Map a backend `#error=` code to a user-facing message; unknown codes are not echoed. */
export function describeOAuthError(code: string): string {
  const known = Object.prototype.hasOwnProperty.call(OAUTH_ERROR_MESSAGES, code)
    ? OAUTH_ERROR_MESSAGES[code]
    : undefined;
  return known ?? GENERIC_OAUTH_ERROR;
}
