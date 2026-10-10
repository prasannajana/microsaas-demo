import { AxiosError, AxiosHeaders, type AxiosResponse, type InternalAxiosRequestConfig } from 'axios';
import type { AuthContextValue } from '../context/AuthContext';
import type { FindingOut, ProjectDetail, ProjectOut, ScanDetail, ScanSummary, User } from '../types';

export function makeUser(overrides: Partial<User> = {}): User {
  return {
    id: 1,
    email: 'dev@example.com',
    full_name: 'Dev User',
    is_active: true,
    is_verified: true,
    is_admin: false,
    oauth_provider: null,
    avatar_url: null,
    created_at: '2026-10-01T00:00:00Z',
    ...overrides,
  };
}

export function makeScan(overrides: Partial<ScanSummary> = {}): ScanSummary {
  return {
    id: 1,
    project_id: 7,
    status: 'completed',
    score: 80,
    commit_sha: 'abcdef1234567890abcdef1234567890abcdef12',
    error_message: null,
    started_at: '2026-10-01T10:00:00Z',
    completed_at: '2026-10-01T10:00:05Z',
    created_at: '2026-10-01T10:00:00Z',
    ...overrides,
  };
}

export function makeFinding(overrides: Partial<FindingOut> = {}): FindingOut {
  return {
    id: 1,
    check_id: 'missing_readme',
    category: 'documentation',
    severity: 'high',
    title: 'No README',
    recommendation: 'Add a README.md describing the project.',
    file_path: null,
    ...overrides,
  };
}

export function makeScanDetail(overrides: Partial<ScanDetail> = {}): ScanDetail {
  return { ...makeScan(), findings: [makeFinding()], ...overrides };
}

export function makeProject(overrides: Partial<ProjectOut> = {}): ProjectOut {
  return {
    id: 7,
    name: 'Hello World',
    repo_url: 'https://github.com/octocat/Hello-World',
    default_branch: null,
    primary_language: 'Python',
    latest_score: 80,
    last_scanned_at: '2026-10-01T10:00:05Z',
    created_at: '2026-09-30T00:00:00Z',
    updated_at: null,
    ...overrides,
  };
}

export function makeProjectDetail(overrides: Partial<ProjectDetail> = {}): ProjectDetail {
  return { ...makeProject(), latest_scan: makeScanDetail(), ...overrides };
}

/** Build an AxiosError carrying an HTTP response (what the real client rejects with). */
export function httpError(status: number, detail: unknown = 'error'): AxiosError {
  const config = { headers: new AxiosHeaders() } as InternalAxiosRequestConfig;
  const response: AxiosResponse = {
    data: { detail },
    status,
    statusText: String(status),
    headers: {},
    config,
  };
  return new AxiosError(`Request failed with status code ${status}`, 'ERR_BAD_REQUEST', config, null, response);
}

export function authValue(user: User | null, overrides: Partial<AuthContextValue> = {}): AuthContextValue {
  const noop = () => Promise.resolve();
  return {
    user,
    isLoading: false,
    login: noop,
    register: noop,
    logout: noop,
    setTokens: noop,
    refreshUser: noop,
    ...overrides,
  };
}
