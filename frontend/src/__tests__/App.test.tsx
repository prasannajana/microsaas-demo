import { ChakraProvider } from '@chakra-ui/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { render, screen } from '@testing-library/react';
import { MemoryRouter, Route, Routes, useLocation } from 'react-router-dom';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import type { AuthContextValue } from '../context/AuthContext';
import { theme } from '../theme';
import { authValue, makeUser } from './fixtures';
import { renderWithProviders } from './test-utils';

const auth = vi.hoisted(() => ({ value: null as AuthContextValue | null }));
vi.mock('../context/AuthContext', () => ({
  useAuth: (): AuthContextValue => auth.value as AuthContextValue,
}));

const api = vi.hoisted(() => ({ get: vi.fn(), post: vi.fn(), put: vi.fn() }));
vi.mock('../services/api', () => ({ default: api, API_BASE_URL: 'http://api/api/v1' }));

const { default: App } = await import('../App');
const { default: LoginPage } = await import('../pages/LoginPage');

function emptyResponse(url: string) {
  if (url === '/analytics/summary') {
    return { data: { project_count: 0, scan_count: 0, avg_latest_score: null, open_critical_findings: 0 } };
  }
  if (url === '/admin/stats') {
    return { data: { user_count: 1, project_count: 0, scan_count: 0, scans_last_24h: 0, failure_rate: 0 } };
  }
  if (url === '/projects' || url.startsWith('/admin/')) return { data: { items: [], total: 0, page: 1, size: 20 } };
  return { data: [] };
}

describe('App routing (end-to-end through the real route tree)', () => {
  beforeEach(() => {
    api.get.mockReset();
    api.get.mockImplementation((url: string) => Promise.resolve(emptyResponse(url)));
  });

  it.each(['/dashboard', '/projects', '/projects/7', '/admin', '/admin/users', '/settings'])(
    'signed-out visit to %s lands on the login page',
    async (path) => {
      auth.value = authValue(null);
      renderWithProviders(<App />, { route: path });
      expect(await screen.findByText('Sign in to keep your projects ship-ready.')).toBeInTheDocument();
      expect(api.get).not.toHaveBeenCalled();
    },
  );

  it.each(['/admin', '/admin/users', '/admin/scans'])('a non-admin visiting %s is sent to the dashboard', async (path) => {
    auth.value = authValue(makeUser({ is_admin: false }));
    renderWithProviders(<App />, { route: path });
    expect(await screen.findByText('Add your first project')).toBeInTheDocument();
    expect(api.get).not.toHaveBeenCalledWith(expect.stringMatching(/^\/admin/), expect.anything());
    expect(api.get).not.toHaveBeenCalledWith('/admin/stats');
  });

  it('an admin can open /admin', async () => {
    auth.value = authValue(makeUser({ is_admin: true }));
    renderWithProviders(<App />, { route: '/admin' });
    expect(await screen.findByText('Platform-wide statistics.')).toBeInTheDocument();
    expect(api.get).toHaveBeenCalledWith('/admin/stats');
  });

  it('unknown routes render the 404 page', async () => {
    auth.value = authValue(null);
    renderWithProviders(<App />, { route: '/nope' });
    expect(await screen.findByText('The page you are looking for does not exist.')).toBeInTheDocument();
  });
});

function WhereAmI() {
  const { pathname, search } = useLocation();
  return <p>at {pathname + search}</p>;
}

describe('LoginPage post-login redirect (open-redirect guard)', () => {
  function renderLogin(state: unknown) {
    auth.value = authValue(makeUser());
    const client = new QueryClient();
    return render(
      <ChakraProvider theme={theme}>
        <QueryClientProvider client={client}>
          <MemoryRouter initialEntries={[{ pathname: '/login', state }]}>
            <Routes>
              <Route path="/login" element={<LoginPage />} />
              <Route path="*" element={<WhereAmI />} />
            </Routes>
          </MemoryRouter>
        </QueryClientProvider>
      </ChakraProvider>,
    );
  }

  it.each([
    [undefined, '/dashboard'],
    [{ from: { pathname: '/projects/7', search: '?tab=1', hash: '' } }, '/projects/7?tab=1'],
    [{ from: '/settings' }, '/settings'],
    [{ from: '//evil.example.com/phish' }, '/dashboard'],
    [{ from: 'https://evil.example.com' }, '/dashboard'],
    [{ from: { pathname: '/login' } }, '/dashboard'],
    [{ from: 42 }, '/dashboard'],
  ])('state %j redirects to %s', async (state, expected) => {
    renderLogin(state);
    expect(await screen.findByText(`at ${expected}`)).toBeInTheDocument();
  });
});
