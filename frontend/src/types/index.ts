/**
 * Types mirroring PRPs/api-contract.md exactly (snake_case on the wire).
 */

// ---- Enums ----
export type ScanStatus = 'queued' | 'running' | 'completed' | 'failed';
export type Severity = 'critical' | 'high' | 'medium' | 'low';
export type FindingCategory =
  | 'documentation'
  | 'testing'
  | 'ci_cd'
  | 'deployment'
  | 'configuration'
  | 'dependencies';

export const SCAN_STATUSES: readonly ScanStatus[] = ['queued', 'running', 'completed', 'failed'];
export const SEVERITIES: readonly Severity[] = ['critical', 'high', 'medium', 'low'];
export const FINDING_CATEGORIES: readonly FindingCategory[] = [
  'documentation',
  'testing',
  'ci_cd',
  'deployment',
  'configuration',
  'dependencies',
];

// ---- Errors ----
export interface ApiError {
  detail: string;
}

export interface ValidationErrorItem {
  loc: (string | number)[];
  msg: string;
  type: string;
}

export interface ApiValidationError {
  detail: ValidationErrorItem[];
}

// ---- Shapes ----
export interface User {
  id: number;
  email: string;
  full_name: string | null;
  is_active: boolean;
  is_verified: boolean;
  is_admin: boolean;
  oauth_provider: string | null;
  avatar_url: string | null;
  created_at: string;
}

export interface TokenPair {
  access_token: string;
  refresh_token: string;
  token_type: 'bearer';
}

export interface Page<T> {
  items: T[];
  total: number;
  page: number;
  size: number;
}

export interface FindingOut {
  id: number;
  check_id: string;
  category: FindingCategory;
  severity: Severity;
  title: string;
  recommendation: string;
  file_path: string | null;
}

export interface ScanSummary {
  id: number;
  project_id: number;
  status: ScanStatus;
  score: number | null;
  commit_sha: string | null;
  error_message: string | null;
  started_at: string | null;
  completed_at: string | null;
  created_at: string;
}

export interface ScanDetail extends ScanSummary {
  findings: FindingOut[];
}

export interface ProjectOut {
  id: number;
  name: string;
  repo_url: string;
  default_branch: string | null;
  primary_language: string | null;
  latest_score: number | null;
  last_scanned_at: string | null;
  created_at: string;
  updated_at: string | null;
}

export interface ProjectDetail extends ProjectOut {
  latest_scan: ScanDetail | null;
}

export interface AnalyticsSummary {
  project_count: number;
  scan_count: number;
  avg_latest_score: number | null;
  open_critical_findings: number;
}

export interface ScoreTrendPoint {
  date: string;
  score: number;
}

export interface ScoreTrendSeries {
  project_id: number;
  name: string;
  points: ScoreTrendPoint[];
}

export interface CommonFinding {
  check_id: string;
  title: string;
  severity: Severity;
  count: number;
}

export interface AdminStats {
  user_count: number;
  project_count: number;
  scan_count: number;
  scans_last_24h: number;
  failure_rate: number;
}

export interface AdminScan extends ScanSummary {
  project_name: string;
  user_email: string;
}

// ---- Request payloads ----
export interface RegisterRequest {
  email: string;
  password: string;
  full_name?: string;
}

export interface LoginRequest {
  email: string;
  password: string;
}

export interface RefreshRequest {
  refresh_token: string;
}

export interface LogoutRequest {
  refresh_token: string;
}

export interface UpdateMeRequest {
  full_name: string;
}

export interface ProjectCreate {
  name: string;
  repo_url: string;
  default_branch?: string;
}

export interface ProjectUpdate {
  name?: string;
  default_branch?: string;
}

export interface AdminUserUpdate {
  is_active?: boolean;
  is_admin?: boolean;
}

export interface PaginationParams {
  page?: number;
  size?: number;
}

export interface AdminUsersParams extends PaginationParams {
  q?: string;
}

export interface AdminScansParams extends PaginationParams {
  status?: ScanStatus;
}

export interface HealthResponse {
  status: 'healthy';
}
