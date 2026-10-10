import { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from 'react';
import { useQueryClient } from '@tanstack/react-query';
import api from '../services/api';
import {
  clearTokens,
  getAccessToken,
  getRefreshToken,
  setTokens as storeTokens,
} from '../lib/tokens';
import type { LoginRequest, RegisterRequest, TokenPair, User } from '../types';

export interface AuthContextValue {
  user: User | null;
  isLoading: boolean;
  login: (email: string, password: string) => Promise<void>;
  register: (email: string, password: string, fullName?: string) => Promise<void>;
  logout: () => Promise<void>;
  /** Store a token pair (e.g. from the OAuth callback fragment) and load the current user. */
  setTokens: (accessToken: string, refreshToken: string) => Promise<void>;
  /** Re-fetch /auth/me (e.g. after the profile is updated). */
  refreshUser: () => Promise<void>;
}

const AuthContext = createContext<AuthContextValue | undefined>(undefined);

async function fetchMe(): Promise<User> {
  const { data } = await api.get<User>('/auth/me');
  return data;
}

export function AuthProvider({ children }: { children: ReactNode }) {
  const queryClient = useQueryClient();
  const [user, setUser] = useState<User | null>(null);
  // Snapshot the token present at boot. Child effects (e.g. the OAuth callback) run before
  // this provider's effect and may store fresh tokens; those already load the user themselves.
  const [bootToken] = useState<string | null>(getAccessToken);
  const [isLoading, setIsLoading] = useState<boolean>(bootToken !== null);

  useEffect(() => {
    if (!bootToken) return;
    let cancelled = false;
    fetchMe()
      .then((me) => {
        if (!cancelled) setUser(me);
      })
      .catch(() => {
        if (!cancelled) {
          clearTokens();
          setUser(null);
        }
      })
      .finally(() => {
        if (!cancelled) setIsLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [bootToken]);

  const applyTokens = useCallback(async (accessToken: string, refreshToken: string) => {
    storeTokens(accessToken, refreshToken);
    try {
      const me = await fetchMe();
      setUser(me);
    } catch (err) {
      clearTokens();
      setUser(null);
      throw err;
    }
  }, []);

  const login = useCallback(
    async (email: string, password: string) => {
      const payload: LoginRequest = { email, password };
      const { data } = await api.post<TokenPair>('/auth/login', payload);
      await applyTokens(data.access_token, data.refresh_token);
    },
    [applyTokens],
  );

  const register = useCallback(
    async (email: string, password: string, fullName?: string) => {
      const payload: RegisterRequest = { email, password };
      if (fullName && fullName.trim().length > 0) payload.full_name = fullName.trim();
      const { data } = await api.post<TokenPair>('/auth/register', payload);
      await applyTokens(data.access_token, data.refresh_token);
    },
    [applyTokens],
  );

  const logout = useCallback(async () => {
    const refreshToken = getRefreshToken();
    try {
      if (refreshToken) {
        await api.post('/auth/logout', { refresh_token: refreshToken });
      }
    } catch {
      // Logout is best-effort server-side; always clear local state.
    } finally {
      clearTokens();
      setUser(null);
      queryClient.clear();
    }
  }, [queryClient]);

  const refreshUser = useCallback(async () => {
    const me = await fetchMe();
    setUser(me);
  }, []);

  const value = useMemo<AuthContextValue>(
    () => ({ user, isLoading, login, register, logout, setTokens: applyTokens, refreshUser }),
    [user, isLoading, login, register, logout, applyTokens, refreshUser],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthContextValue {
  const ctx = useContext(AuthContext);
  if (!ctx) {
    throw new Error('useAuth must be used within an AuthProvider');
  }
  return ctx;
}
