import { keepPreviousData, useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import api from '../services/api';
import type {
  AdminScan,
  AdminScansParams,
  AdminStats,
  AdminUserUpdate,
  AdminUsersParams,
  Page,
  User,
} from '../types';

export const adminKeys = {
  all: ['admin'] as const,
  stats: () => [...adminKeys.all, 'stats'] as const,
  users: () => [...adminKeys.all, 'users'] as const,
  userList: (params: AdminUsersParams) => [...adminKeys.users(), params] as const,
  scans: (params: AdminScansParams) => [...adminKeys.all, 'scans', params] as const,
};

/** Drop undefined / empty-string values so they are not sent as query params. */
function cleanParams<T extends object>(params: T): Partial<T> {
  return Object.fromEntries(
    Object.entries(params).filter(([, v]) => v !== undefined && v !== ''),
  ) as Partial<T>;
}

export function useAdminStats() {
  return useQuery({
    queryKey: adminKeys.stats(),
    queryFn: async (): Promise<AdminStats> => {
      const { data } = await api.get<AdminStats>('/admin/stats');
      return data;
    },
  });
}

export function useAdminUsers(params: AdminUsersParams) {
  return useQuery({
    queryKey: adminKeys.userList(params),
    queryFn: async (): Promise<Page<User>> => {
      const { data } = await api.get<Page<User>>('/admin/users', { params: cleanParams(params) });
      return data;
    },
    placeholderData: keepPreviousData,
  });
}

export interface UpdateAdminUserVariables {
  id: number;
  update: AdminUserUpdate;
}

export function useUpdateAdminUser() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async ({ id, update }: UpdateAdminUserVariables): Promise<User> => {
      const { data } = await api.put<User>(`/admin/users/${id}`, update);
      return data;
    },
    onSettled: () => {
      void queryClient.invalidateQueries({ queryKey: adminKeys.users() });
      void queryClient.invalidateQueries({ queryKey: adminKeys.stats() });
    },
  });
}

export function useAdminScans(params: AdminScansParams) {
  return useQuery({
    queryKey: adminKeys.scans(params),
    queryFn: async (): Promise<Page<AdminScan>> => {
      const { data } = await api.get<Page<AdminScan>>('/admin/scans', { params: cleanParams(params) });
      return data;
    },
    placeholderData: keepPreviousData,
  });
}
