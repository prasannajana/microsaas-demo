import type { ReactNode } from 'react';
import { Navigate, Outlet, useLocation } from 'react-router-dom';
import { useAuth } from '../../context/AuthContext';
import { LoadingScreen } from '../ui/LoadingScreen';

export interface ProtectedRouteProps {
  /** Optional explicit children; otherwise renders nested routes via <Outlet />. */
  children?: ReactNode;
}

/** Redirects to /login (preserving the intended location in `state.from`) when signed out. */
export function ProtectedRoute({ children }: ProtectedRouteProps) {
  const { user, isLoading } = useAuth();
  const location = useLocation();

  if (isLoading) return <LoadingScreen />;
  if (!user) return <Navigate to="/login" replace state={{ from: location }} />;
  return <>{children ?? <Outlet />}</>;
}
