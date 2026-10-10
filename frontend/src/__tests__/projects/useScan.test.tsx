import type { ReactNode } from 'react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { act, renderHook, waitFor } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { projectKeys } from '../../hooks/useProjects';
import { SCAN_POLL_INTERVAL_MS, useScan } from '../../hooks/useScans';
import { projectService } from '../../services/projectService';
import type { ScanDetail, ScanStatus } from '../../types';

vi.mock('../../services/projectService', () => ({
  projectService: { getScan: vi.fn() },
}));

function scanWith(status: ScanStatus): ScanDetail {
  return {
    id: 5,
    project_id: 9,
    status,
    score: status === 'completed' ? 90 : null,
    commit_sha: null,
    error_message: null,
    started_at: null,
    completed_at: null,
    created_at: '2026-10-01T10:00:00Z',
    findings: [],
  };
}

describe('useScan polling', () => {
  let client: QueryClient;

  beforeEach(() => {
    vi.useFakeTimers({ shouldAdvanceTime: true });
    client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    vi.mocked(projectService.getScan).mockReset();
  });

  afterEach(() => {
    client.clear();
    vi.useRealTimers();
  });

  function wrapper({ children }: { children: ReactNode }) {
    return <QueryClientProvider client={client}>{children}</QueryClientProvider>;
  }

  it('polls while running and stops once completed, invalidating the project', async () => {
    vi.mocked(projectService.getScan)
      .mockResolvedValueOnce(scanWith('queued'))
      .mockResolvedValueOnce(scanWith('running'))
      .mockResolvedValue(scanWith('completed'));
    const invalidate = vi.spyOn(client, 'invalidateQueries');

    const { result } = renderHook(() => useScan(5), { wrapper });

    await waitFor(() => expect(result.current.data?.status).toBe('queued'));

    await act(async () => {
      await vi.advanceTimersByTimeAsync(SCAN_POLL_INTERVAL_MS);
    });
    await waitFor(() => expect(result.current.data?.status).toBe('running'));

    await act(async () => {
      await vi.advanceTimersByTimeAsync(SCAN_POLL_INTERVAL_MS);
    });
    await waitFor(() => expect(result.current.data?.status).toBe('completed'));
    const callsAtCompletion = vi.mocked(projectService.getScan).mock.calls.length;
    expect(callsAtCompletion).toBe(3);

    await act(async () => {
      await vi.advanceTimersByTimeAsync(SCAN_POLL_INTERVAL_MS * 5);
    });
    expect(projectService.getScan).toHaveBeenCalledTimes(callsAtCompletion);
    expect(invalidate).toHaveBeenCalledWith({ queryKey: projectKeys.detail(9) });
  });

  it('does not poll a scan that is already completed', async () => {
    vi.mocked(projectService.getScan).mockResolvedValue(scanWith('completed'));
    const { result } = renderHook(() => useScan(5), { wrapper });
    await waitFor(() => expect(result.current.data?.status).toBe('completed'));

    await act(async () => {
      await vi.advanceTimersByTimeAsync(SCAN_POLL_INTERVAL_MS * 3);
    });
    expect(projectService.getScan).toHaveBeenCalledTimes(1);
  });
});
