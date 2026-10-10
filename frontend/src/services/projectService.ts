import api from './api';
import type {
  Page,
  PaginationParams,
  ProjectCreate,
  ProjectDetail,
  ProjectOut,
  ProjectUpdate,
  ScanDetail,
  ScanSummary,
} from '../types';

export const projectService = {
  async list(params: PaginationParams = {}): Promise<Page<ProjectOut>> {
    const { data } = await api.get<Page<ProjectOut>>('/projects', { params });
    return data;
  },

  async get(id: number): Promise<ProjectDetail> {
    const { data } = await api.get<ProjectDetail>(`/projects/${id}`);
    return data;
  },

  async create(payload: ProjectCreate): Promise<ProjectOut> {
    const { data } = await api.post<ProjectOut>('/projects', payload);
    return data;
  },

  async update(id: number, payload: ProjectUpdate): Promise<ProjectOut> {
    const { data } = await api.put<ProjectOut>(`/projects/${id}`, payload);
    return data;
  },

  async remove(id: number): Promise<void> {
    await api.delete(`/projects/${id}`);
  },

  async startScan(projectId: number): Promise<ScanSummary> {
    const { data } = await api.post<ScanSummary>(`/projects/${projectId}/scans`);
    return data;
  },

  async listScans(projectId: number): Promise<ScanSummary[]> {
    const { data } = await api.get<ScanSummary[]>(`/projects/${projectId}/scans`);
    return data;
  },

  async getScan(scanId: number): Promise<ScanDetail> {
    const { data } = await api.get<ScanDetail>(`/scans/${scanId}`);
    return data;
  },
};
