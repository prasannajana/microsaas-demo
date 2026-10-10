import type { ReactNode } from 'react';
import { Navigate, Outlet, useLocation } from 'react-router-dom';
import { useAuth } from '../../context/AuthContext';
import { LoadingScreen } from '../ui/LoadingScreen';

export interface AdminRouteProps {
  children?: ReactNode;
}

/** Signed-out users go to /login; signed-in non-admins go to /dashboard. */
export function AdminRoute({ children }: AdminRouteProps) {
  const { user, isLoading } = useAuth();
  const location = useLocation();

  if (isLoading) return <LoadingScreen />;
  if (!user) return <Navigate to="/login" replace state={{ from: location }} />;
  if (!user.is_admin) return <Navigate to="/dashboard" replace />;
  return <>{children ?? <Outlet />}</>;
}
