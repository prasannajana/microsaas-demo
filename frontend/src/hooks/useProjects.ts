import { keepPreviousData, useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { projectService } from '../services/projectService';
import type { Page, ProjectCreate, ProjectDetail, ProjectOut, ProjectUpdate } from '../types';

export const PROJECTS_PAGE_SIZE = 12;

/** Query keys for the projects module (scan keys live alongside in useScans). */
export const projectKeys = {
  all: ['projects'] as const,
  lists: () => [...projectKeys.all, 'list'] as const,
  list: (page: number, size: number) => [...projectKeys.lists(), { page, size }] as const,
  detail: (id: number) => [...projectKeys.all, 'detail', id] as const,
  scans: (id: number) => [...projectKeys.all, 'detail', id, 'scans'] as const,
};

export function useProjects(page: number, size: number = PROJECTS_PAGE_SIZE) {
  return useQuery<Page<ProjectOut>>({
    queryKey: projectKeys.list(page, size),
    queryFn: () => projectService.list({ page, size }),
    placeholderData: keepPreviousData,
  });
}

export function useProject(id: number | undefined) {
  return useQuery<ProjectDetail>({
    queryKey: projectKeys.detail(id ?? 0),
    queryFn: () => projectService.get(id as number),
    enabled: id !== undefined && Number.isFinite(id) && id > 0,
  });
}

export function useCreateProject() {
  const queryClient = useQueryClient();
  return useMutation<ProjectOut, Error, ProjectCreate>({
    mutationFn: (payload) => projectService.create(payload),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: projectKeys.lists() });
    },
  });
}

export function useUpdateProject(id: number) {
  const queryClient = useQueryClient();
  return useMutation<ProjectOut, Error, ProjectUpdate>({
    mutationFn: (payload) => projectService.update(id, payload),
    onSuccess: (updated) => {
      queryClient.setQueryData<ProjectDetail>(projectKeys.detail(id), (prev) =>
        prev ? { ...prev, ...updated } : prev,
      );
      void queryClient.invalidateQueries({ queryKey: projectKeys.lists() });
    },
  });
}

export function useDeleteProject() {
  const queryClient = useQueryClient();
  return useMutation<void, Error, number>({
    mutationFn: (id) => projectService.remove(id),
    onSuccess: (_data, id) => {
      queryClient.removeQueries({ queryKey: projectKeys.detail(id) });
      void queryClient.invalidateQueries({ queryKey: projectKeys.lists() });
    },
  });
}
