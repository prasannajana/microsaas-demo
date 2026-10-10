export const ACCESS_TOKEN_KEY = 'pv_access_token';
export const REFRESH_TOKEN_KEY = 'pv_refresh_token';

function safeGet(key: string): string | null {
  try {
    return window.localStorage.getItem(key);
  } catch {
    return null;
  }
}

export function getAccessToken(): string | null {
  return safeGet(ACCESS_TOKEN_KEY);
}

export function getRefreshToken(): string | null {
  return safeGet(REFRESH_TOKEN_KEY);
}

export function setTokens(accessToken: string, refreshToken: string): void {
  try {
    window.localStorage.setItem(ACCESS_TOKEN_KEY, accessToken);
    window.localStorage.setItem(REFRESH_TOKEN_KEY, refreshToken);
  } catch {
    // Storage unavailable (private mode); tokens live only for this request cycle.
  }
}

export function clearTokens(): void {
  try {
    window.localStorage.removeItem(ACCESS_TOKEN_KEY);
    window.localStorage.removeItem(REFRESH_TOKEN_KEY);
  } catch {
    // ignore
  }
}

export function hasTokens(): boolean {
  return getAccessToken() !== null;
}
