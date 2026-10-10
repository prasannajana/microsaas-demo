import axios, { AxiosError, type AxiosRequestConfig, type InternalAxiosRequestConfig } from 'axios';
import type { TokenPair } from '../types';
import { clearTokens, getAccessToken, getRefreshToken, setTokens } from '../lib/tokens';

export const API_BASE_URL = `${import.meta.env.VITE_API_URL ?? 'http://localhost:8000'}/api/v1`;

const api = axios.create({
  baseURL: API_BASE_URL,
  headers: { 'Content-Type': 'application/json' },
});

interface RetriableConfig extends InternalAxiosRequestConfig {
  _retry?: boolean;
}

/** Endpoints for which a 401 must NOT trigger a refresh attempt. */
const NO_REFRESH_PATHS = ['/auth/login', '/auth/register', '/auth/refresh', '/auth/logout'];

const PUBLIC_PATHS = ['/login', '/register', '/forgot-password', '/auth/callback'];

api.interceptors.request.use((config) => {
  const token = getAccessToken();
  if (token) {
    config.headers.set('Authorization', `Bearer ${token}`);
  }
  return config;
});

let refreshPromise: Promise<string> | null = null;

/** Refresh the token pair once; concurrent callers share the same in-flight promise. */
async function refreshAccessToken(): Promise<string> {
  if (!refreshPromise) {
    const refreshToken = getRefreshToken();
    if (!refreshToken) {
      return Promise.reject(new Error('No refresh token'));
    }
    refreshPromise = axios
      .post<TokenPair>(`${API_BASE_URL}/auth/refresh`, { refresh_token: refreshToken })
      .then(({ data }) => {
        setTokens(data.access_token, data.refresh_token);
        return data.access_token;
      })
      .finally(() => {
        refreshPromise = null;
      });
  }
  return refreshPromise;
}

function handleAuthFailure(): void {
  clearTokens();
  if (!PUBLIC_PATHS.some((p) => window.location.pathname.startsWith(p))) {
    window.location.assign('/login');
  }
}

api.interceptors.response.use(
  (response) => response,
  async (error: AxiosError) => {
    const original = error.config as RetriableConfig | undefined;
    const status = error.response?.status;
    const url = original?.url ?? '';

    if (
      status !== 401 ||
      !original ||
      original._retry ||
      NO_REFRESH_PATHS.some((p) => url.includes(p))
    ) {
      return Promise.reject(error);
    }

    original._retry = true;
    try {
      const newToken = await refreshAccessToken();
      original.headers.set('Authorization', `Bearer ${newToken}`);
      return api(original as AxiosRequestConfig);
    } catch (refreshError) {
      handleAuthFailure();
      return Promise.reject(refreshError);
    }
  },
);

export default api;
