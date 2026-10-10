import axios, { AxiosError, AxiosHeaders, type AxiosAdapter, type AxiosResponse, type InternalAxiosRequestConfig } from 'axios';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import api from '../../services/api';
import { ACCESS_TOKEN_KEY, REFRESH_TOKEN_KEY, getAccessToken, getRefreshToken, setTokens } from '../../lib/tokens';

type Handler = (config: InternalAxiosRequestConfig) => { status: number; data?: unknown };

const calls: InternalAxiosRequestConfig[] = [];
let handler: Handler;

function respond(config: InternalAxiosRequestConfig, status: number, data: unknown): Promise<AxiosResponse> {
  const response: AxiosResponse = { data, status, statusText: String(status), headers: {}, config };
  if (status >= 400) {
    return Promise.reject(new AxiosError(`Request failed with status code ${status}`, 'ERR_BAD_REQUEST', config, null, response));
  }
  return Promise.resolve(response);
}

const adapter: AxiosAdapter = (config) => {
  calls.push(config);
  const { status, data } = handler(config);
  return respond(config, status, data ?? {});
};

function authHeader(config: InternalAxiosRequestConfig): string | undefined {
  const value = AxiosHeaders.from(config.headers).get('Authorization');
  return typeof value === 'string' ? value : undefined;
}

function firstCall(): InternalAxiosRequestConfig {
  const call = calls[0];
  if (!call) throw new Error('no request was made');
  return call;
}

function isRefresh(config: InternalAxiosRequestConfig): boolean {
  return (config.url ?? '').endsWith('/auth/refresh');
}

const assignMock = vi.fn();
const originalLocation = window.location;

describe('api client interceptors', () => {
  const originalApiAdapter = api.defaults.adapter;
  const originalAxiosAdapter = axios.defaults.adapter;

  beforeEach(() => {
    calls.length = 0;
    window.localStorage.clear();
    api.defaults.adapter = adapter;
    axios.defaults.adapter = adapter; // refresh uses the bare axios instance
    assignMock.mockReset();
    Object.defineProperty(window, 'location', {
      configurable: true,
      value: { ...originalLocation, pathname: '/projects', assign: assignMock },
    });
  });

  afterEach(() => {
    api.defaults.adapter = originalApiAdapter;
    axios.defaults.adapter = originalAxiosAdapter;
    Object.defineProperty(window, 'location', { configurable: true, value: originalLocation });
  });

  it('attaches the access token as a Bearer header', async () => {
    setTokens('acc-1', 'ref-1');
    handler = () => ({ status: 200, data: { ok: true } });
    const res = await api.get('/auth/me');
    expect(res.data).toEqual({ ok: true });
    expect(authHeader(firstCall())).toBe('Bearer acc-1');
  });

  it('sends no Authorization header when signed out', async () => {
    handler = () => ({ status: 200 });
    await api.get('/health');
    expect(authHeader(firstCall())).toBeUndefined();
  });

  it('on 401 refreshes once, stores the new pair and retries with the new token', async () => {
    setTokens('old-access', 'old-refresh');
    handler = (config) => {
      if (isRefresh(config)) {
        return { status: 200, data: { access_token: 'new-access', refresh_token: 'new-refresh', token_type: 'bearer' } };
      }
      return authHeader(config) === 'Bearer new-access' ? { status: 200, data: { id: 1 } } : { status: 401, data: { detail: 'expired' } };
    };

    const res = await api.get('/projects');

    expect(res.data).toEqual({ id: 1 });
    expect(calls.filter(isRefresh)).toHaveLength(1);
    expect(JSON.parse(String(calls.find(isRefresh)?.data))).toEqual({ refresh_token: 'old-refresh' });
    expect(getAccessToken()).toBe('new-access');
    expect(getRefreshToken()).toBe('new-refresh');
    expect(calls).toHaveLength(3); // original, refresh, retry
    expect(assignMock).not.toHaveBeenCalled();
  });

  it('concurrent 401s share a single refresh request', async () => {
    setTokens('old-access', 'old-refresh');
    let refreshResolve: (() => void) | null = null;
    const refreshGate = new Promise<void>((resolve) => {
      refreshResolve = resolve;
    });
    let refreshCount = 0;
    const gatedAdapter: AxiosAdapter = async (config) => {
      calls.push(config);
      if (isRefresh(config)) {
        refreshCount += 1;
        await refreshGate;
        return respond(config, 200, { access_token: 'shared', refresh_token: 'shared-r', token_type: 'bearer' });
      }
      return authHeader(config) === 'Bearer shared' ? respond(config, 200, { url: config.url }) : respond(config, 401, {});
    };
    api.defaults.adapter = gatedAdapter;
    axios.defaults.adapter = gatedAdapter;

    const pending = Promise.all([api.get('/a'), api.get('/b'), api.get('/c')]);
    await vi.waitFor(() => expect(refreshCount).toBe(1));
    refreshResolve!();
    const results = await pending;

    expect(results.map((r) => (r.data as { url: string }).url)).toEqual(['/a', '/b', '/c']);
    expect(refreshCount).toBe(1);
  });

  it('a second refresh happens later once the first one settled', async () => {
    setTokens('a0', 'r0');
    let n = 0;
    handler = (config) => {
      if (isRefresh(config)) {
        n += 1;
        return { status: 200, data: { access_token: `a${n}`, refresh_token: `r${n}`, token_type: 'bearer' } };
      }
      const h = authHeader(config);
      return h === `Bearer a${n}` && n > 0 && config.headers['x-round'] === String(n) ? { status: 200 } : { status: 401 };
    };
    await api.get('/x', { headers: { 'x-round': '1' } });
    await api.get('/x', { headers: { 'x-round': '2' } });
    expect(calls.filter(isRefresh)).toHaveLength(2);
  });

  it('refresh failure clears tokens, redirects to /login and rejects', async () => {
    setTokens('old-access', 'old-refresh');
    handler = (config) => (isRefresh(config) ? { status: 401, data: { detail: 'Invalid or expired refresh token' } } : { status: 401 });

    await expect(api.get('/projects')).rejects.toBeInstanceOf(AxiosError);

    expect(window.localStorage.getItem(ACCESS_TOKEN_KEY)).toBeNull();
    expect(window.localStorage.getItem(REFRESH_TOKEN_KEY)).toBeNull();
    expect(assignMock).toHaveBeenCalledWith('/login');
    expect(calls.filter(isRefresh)).toHaveLength(1);
  });

  it('without a refresh token it clears state without calling /auth/refresh', async () => {
    window.localStorage.setItem(ACCESS_TOKEN_KEY, 'only-access');
    handler = () => ({ status: 401 });
    await expect(api.get('/projects')).rejects.toThrow('No refresh token');
    expect(calls.filter(isRefresh)).toHaveLength(0);
    expect(getAccessToken()).toBeNull();
    expect(assignMock).toHaveBeenCalledWith('/login');
  });

  it('does not redirect when already on a public page', async () => {
    Object.defineProperty(window, 'location', {
      configurable: true,
      value: { ...originalLocation, pathname: '/login', assign: assignMock },
    });
    setTokens('a', 'r');
    handler = () => ({ status: 401 });
    await expect(api.get('/projects')).rejects.toBeDefined();
    expect(assignMock).not.toHaveBeenCalled();
    expect(getAccessToken()).toBeNull();
  });

  it.each(['/auth/login', '/auth/register', '/auth/refresh', '/auth/logout'])(
    'a 401 from %s is returned as-is (no refresh)',
    async (path) => {
      setTokens('a', 'r');
      handler = () => ({ status: 401, data: { detail: 'Invalid email or password' } });
      await expect(api.post(path, {})).rejects.toMatchObject({ response: { status: 401 } });
      expect(calls).toHaveLength(1);
      expect(getAccessToken()).toBe('a'); // untouched
    },
  );

  it('does not retry a request twice if the retried call is also 401', async () => {
    setTokens('a', 'r');
    handler = (config) =>
      isRefresh(config) ? { status: 200, data: { access_token: 'b', refresh_token: 's', token_type: 'bearer' } } : { status: 401 };
    await expect(api.get('/projects')).rejects.toMatchObject({ response: { status: 401 } });
    expect(calls.filter(isRefresh)).toHaveLength(1);
    expect(calls).toHaveLength(3);
  });

  it.each([403, 404, 409, 500])('non-401 errors (%i) are passed through untouched', async (status) => {
    setTokens('a', 'r');
    handler = () => ({ status, data: { detail: 'nope' } });
    await expect(api.get('/projects')).rejects.toMatchObject({ response: { status } });
    expect(calls).toHaveLength(1);
    expect(getAccessToken()).toBe('a');
  });
});
