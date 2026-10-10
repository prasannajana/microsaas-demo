import { useQuery } from '@tanstack/react-query';
import api from '../services/api';
import type { AnalyticsSummary, CommonFinding, Page, ProjectOut, ScoreTrendSeries } from '../types';

export const analyticsKeys = {
  all: ['analytics'] as const,
  summary: () => [...analyticsKeys.all, 'summary'] as const,
  trend: (days: number) => [...analyticsKeys.all, 'score-trend', days] as const,
  commonFindings: (limit: number) => [...analyticsKeys.all, 'common-findings', limit] as const,
  quickProjects: (size: number) => [...analyticsKeys.all, 'quick-projects', size] as const,
};

export function useAnalyticsSummary() {
  return useQuery({
    queryKey: analyticsKeys.summary(),
    queryFn: async (): Promise<AnalyticsSummary> => {
      const { data } = await api.get<AnalyticsSummary>('/analytics/summary');
      return data;
    },
  });
}

export function useScoreTrend(days: number) {
  return useQuery({
    queryKey: analyticsKeys.trend(days),
    queryFn: async (): Promise<ScoreTrendSeries[]> => {
      const { data } = await api.get<ScoreTrendSeries[]>('/analytics/score-trend', { params: { days } });
      return data;
    },
  });
}

export function useCommonFindings(limit = 5) {
  return useQuery({
    queryKey: analyticsKeys.commonFindings(limit),
    queryFn: async (): Promise<CommonFinding[]> => {
      const { data } = await api.get<CommonFinding[]>('/analytics/common-findings', { params: { limit } });
      return data;
    },
  });
}

/** Small "Your projects" list for the dashboard (kept local to avoid coupling with project hooks). */
export function useDashboardProjects(size = 5) {
  return useQuery({
    queryKey: analyticsKeys.quickProjects(size),
    queryFn: async (): Promise<Page<ProjectOut>> => {
      const { data } = await api.get<Page<ProjectOut>>('/projects', { params: { page: 1, size } });
      return data;
    },
  });
}
