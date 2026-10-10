import { screen } from '@testing-library/react';
import { Route, Routes, useLocation } from 'react-router-dom';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { AdminRoute } from '../../components/auth/AdminRoute';
import { ProtectedRoute } from '../../components/auth/ProtectedRoute';
import type { AuthContextValue } from '../../context/AuthContext';
import { authValue, makeUser } from '../fixtures';
import { renderWithProviders } from '../test-utils';

const auth = vi.hoisted(() => ({ value: null as AuthContextValue | null }));
vi.mock('../../context/AuthContext', () => ({
  useAuth: (): AuthContextValue => {
    if (!auth.value) throw new Error('auth not set');
    return auth.value;
  },
}));

function LoginProbe() {
  const location = useLocation();
  const from = (location.state as { from?: { pathname: string } } | null)?.from?.pathname ?? 'none';
  return <p>login page (from: {from})</p>;
}

function renderAt(route: string) {
  return renderWithProviders(
    <Routes>
      <Route path="/login" element={<LoginProbe />} />
      <Route path="/dashboard" element={<p>dashboard page</p>} />
      <Route element={<ProtectedRoute />}>
        <Route path="/projects" element={<p>projects page</p>} />
        <Route element={<AdminRoute />}>
          <Route path="/admin" element={<p>admin page</p>} />
        </Route>
      </Route>
      <Route
        path="/explicit"
        element={
          <ProtectedRoute>
            <p>explicit child</p>
          </ProtectedRoute>
        }
      />
      <Route
        path="/explicit-admin"
        element={
          <AdminRoute>
            <p>explicit admin child</p>
          </AdminRoute>
        }
      />
    </Routes>,
    { route },
  );
}

describe('route guards', () => {
  beforeEach(() => {
    auth.value = null;
  });

  it('ProtectedRoute redirects signed-out users to /login, remembering where they came from', () => {
    auth.value = authValue(null);
    renderAt('/projects');
    expect(screen.getByText('login page (from: /projects)')).toBeInTheDocument();
    expect(screen.queryByText('projects page')).not.toBeInTheDocument();
  });

  it('ProtectedRoute shows a loading screen while the session is restored', () => {
    auth.value = authValue(null, { isLoading: true });
    renderAt('/projects');
    expect(screen.queryByText(/login page/)).not.toBeInTheDocument();
    expect(screen.queryByText('projects page')).not.toBeInTheDocument();
  });

  it('ProtectedRoute renders nested routes and explicit children for signed-in users', () => {
    auth.value = authValue(makeUser());
    renderAt('/projects');
    expect(screen.getByText('projects page')).toBeInTheDocument();
  });

  it('ProtectedRoute renders explicit children', () => {
    auth.value = authValue(makeUser());
    renderAt('/explicit');
    expect(screen.getByText('explicit child')).toBeInTheDocument();
  });

  it('AdminRoute sends signed-out users to /login', () => {
    auth.value = authValue(null);
    renderAt('/explicit-admin');
    expect(screen.getByText('login page (from: /explicit-admin)')).toBeInTheDocument();
  });

  it('AdminRoute sends non-admins to /dashboard', () => {
    auth.value = authValue(makeUser({ is_admin: false }));
    renderAt('/admin');
    expect(screen.getByText('dashboard page')).toBeInTheDocument();
    expect(screen.queryByText('admin page')).not.toBeInTheDocument();
  });

  it('AdminRoute renders for admins (nested and explicit children)', () => {
    auth.value = authValue(makeUser({ is_admin: true }));
    renderAt('/admin');
    expect(screen.getByText('admin page')).toBeInTheDocument();
  });

  it('AdminRoute renders explicit children for admins', () => {
    auth.value = authValue(makeUser({ is_admin: true }));
    renderAt('/explicit-admin');
    expect(screen.getByText('explicit admin child')).toBeInTheDocument();
  });

  it('AdminRoute waits while loading', () => {
    auth.value = authValue(null, { isLoading: true });
    renderAt('/explicit-admin');
    expect(screen.queryByText(/login page/)).not.toBeInTheDocument();
    expect(screen.queryByText('explicit admin child')).not.toBeInTheDocument();
  });
});
