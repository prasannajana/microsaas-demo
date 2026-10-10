import { useEffect, useRef } from 'react';
import { useMutation, useQuery, useQueryClient, type Query } from '@tanstack/react-query';
import { projectService } from '../services/projectService';
import type { ScanDetail, ScanStatus, ScanSummary } from '../types';
import { projectKeys } from './useProjects';

export const SCAN_POLL_INTERVAL_MS = 2000;

export const scanKeys = {
  all: ['scans'] as const,
  detail: (scanId: number) => [...scanKeys.all, scanId] as const,
};

/** A scan is "active" while it is queued or running. */
export function isActiveScanStatus(status: ScanStatus | null | undefined): boolean {
  return status === 'queued' || status === 'running';
}

/** refetchInterval for a scan query: poll every 2s while active, otherwise stop. */
export function scanRefetchInterval(query: Query<ScanDetail, Error>): number | false {
  return isActiveScanStatus(query.state.data?.status) ? SCAN_POLL_INTERVAL_MS : false;
}

export function useProjectScans(projectId: number | undefined) {
  return useQuery<ScanSummary[]>({
    queryKey: projectKeys.scans(projectId ?? 0),
    queryFn: () => projectService.listScans(projectId as number),
    enabled: projectId !== undefined && Number.isFinite(projectId) && projectId > 0,
  });
}

/**
 * Fetch a scan with findings. Polls every 2s while queued/running; when the scan
 * transitions to completed/failed, the owning project (and its history) is invalidated.
 */
export function useScan(scanId: number | undefined) {
  const queryClient = useQueryClient();
  const query = useQuery<ScanDetail, Error>({
    queryKey: scanKeys.detail(scanId ?? 0),
    queryFn: () => projectService.getScan(scanId as number),
    enabled: scanId !== undefined && Number.isFinite(scanId) && scanId > 0,
    refetchInterval: scanRefetchInterval,
    staleTime: 0,
  });

  const status = query.data?.status;
  const projectId = query.data?.project_id;
  const previousStatus = useRef<ScanStatus | undefined>(undefined);

  useEffect(() => {
    const prev = previousStatus.current;
    previousStatus.current = status;
    if (projectId === undefined || status === undefined) return;
    if (isActiveScanStatus(prev) && !isActiveScanStatus(status)) {
      void queryClient.invalidateQueries({ queryKey: projectKeys.detail(projectId) });
      void queryClient.invalidateQueries({ queryKey: projectKeys.lists() });
    }
  }, [status, projectId, queryClient]);

  return query;
}

/** Start a scan for a project; refreshes the project and its scan history on success. */
export function useStartScan(projectId: number) {
  const queryClient = useQueryClient();
  return useMutation<ScanSummary, Error, void>({
    mutationFn: () => projectService.startScan(projectId),
    onSuccess: (scan) => {
      queryClient.setQueryData<ScanSummary[]>(projectKeys.scans(projectId), (prev) =>
        prev ? [scan, ...prev.filter((s) => s.id !== scan.id)] : [scan],
      );
      void queryClient.invalidateQueries({ queryKey: projectKeys.detail(projectId) });
    },
  });
}
