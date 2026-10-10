# API Contract — Project Verification

> Single source of truth shared by BACKEND and FRONTEND agents. JSON is **snake_case** on the wire; frontend TypeScript types mirror it exactly (no camelCase mapping). Timestamps are ISO-8601 strings with timezone. Base URL: `${VITE_API_URL}/api/v1`.

## Errors
All non-2xx responses: `{"detail": string}` (FastAPI default; validation errors 422 keep FastAPI's list format).

## Enums
```ts
type ScanStatus = "queued" | "running" | "completed" | "failed";
type Severity = "critical" | "high" | "medium" | "low";
type FindingCategory = "documentation" | "testing" | "ci_cd" | "deployment" | "configuration" | "dependencies";
```

## Shapes
```ts
interface User { id: number; email: string; full_name: string | null; is_active: boolean; is_verified: boolean; is_admin: boolean; oauth_provider: string | null; avatar_url: string | null; created_at: string; }

interface TokenPair { access_token: string; refresh_token: string; token_type: "bearer"; }

interface Page<T> { items: T[]; total: number; page: number; size: number; }

interface FindingOut { id: number; check_id: string; category: FindingCategory; severity: Severity; title: string; recommendation: string; file_path: string | null; }

interface ScanSummary { id: number; project_id: number; status: ScanStatus; score: number | null; commit_sha: string | null; error_message: string | null; started_at: string | null; completed_at: string | null; created_at: string; }

interface ScanDetail extends ScanSummary { findings: FindingOut[]; }

interface ProjectOut { id: number; name: string; repo_url: string; default_branch: string | null; primary_language: string | null; latest_score: number | null; last_scanned_at: string | null; created_at: string; updated_at: string | null; }

interface ProjectDetail extends ProjectOut { latest_scan: ScanDetail | null; }

interface AnalyticsSummary { project_count: number; scan_count: number; avg_latest_score: number | null; open_critical_findings: number; }
interface ScoreTrendSeries { project_id: number; name: string; points: { date: string; score: number }[]; }
interface CommonFinding { check_id: string; title: string; severity: Severity; count: number; }

interface AdminStats { user_count: number; project_count: number; scan_count: number; scans_last_24h: number; failure_rate: number /* fraction 0..1 */; }
interface AdminScan extends ScanSummary { project_name: string; user_email: string; }
```

## Endpoints

| Method | Path | Auth | Request | Response |
|---|---|---|---|---|
| POST | /auth/register | – | `{email, password (min 8), full_name?}` | 201 `TokenPair` (409 email exists) |
| POST | /auth/login | – | JSON `{email, password}` | 200 `TokenPair` (401 bad creds) |
| POST | /auth/refresh | – | `{refresh_token}` | 200 `TokenPair` (old refresh token revoked) |
| POST | /auth/logout | – | `{refresh_token}` | 204 |
| GET | /auth/me | user | – | `User` |
| PUT | /auth/me | user | `{full_name}` | `User` |
| GET | /auth/google | – | `?nonce=` (optional, `[A-Za-z0-9_-]{16,128}`, else 400) | 302 to Google; sets HttpOnly `oauth_state` cookie (`state.nonce`). If Google is not configured: 302 to `${FRONTEND_URL}/auth/callback#error=google_not_configured` |
| GET | /auth/google/callback | – | `?code&state` | 302 to `${FRONTEND_URL}/auth/callback#access_token=…&refresh_token=…&nonce=…` (on error `#error=…[&nonce=…]`); frontend rejects tokens whose nonce ≠ the one it stored in sessionStorage |
| GET | /projects | user | `?page=1&size=20` | `Page<ProjectOut>` |
| POST | /projects | user | `{name, repo_url, default_branch?}` | 201 `ProjectOut` (400 invalid URL, 409 duplicate) |
| GET | /projects/{id} | user | – | `ProjectDetail` |
| PUT | /projects/{id} | user | `{name?, default_branch?}` | `ProjectOut` |
| DELETE | /projects/{id} | user | – | 204 |
| POST | /projects/{id}/scans | user | – | 202 `ScanSummary` (409 active scan, 429 rate limit) |
| GET | /projects/{id}/scans | user | – | `ScanSummary[]` newest first |
| GET | /scans/{scan_id} | user | – | `ScanDetail` |
| GET | /analytics/summary | user | – | `AnalyticsSummary` |
| GET | /analytics/score-trend | user | `?days=30` | `ScoreTrendSeries[]` |
| GET | /analytics/common-findings | user | `?limit=5` | `CommonFinding[]` |
| GET | /admin/users | admin | `?page&size&q` | `Page<User>` |
| PUT | /admin/users/{id} | admin | `{is_active?, is_admin?}` | `User` (400 if self) |
| GET | /admin/stats | admin | – | `AdminStats` |
| GET | /admin/scans | admin | `?status&page&size` | `Page<AdminScan>` |
| GET | /health (no prefix) | – | – | `{"status":"healthy"}` |

Auth header: `Authorization: Bearer <access_token>`. Frontend stores tokens in `localStorage` keys `pv_access_token`, `pv_refresh_token`; on 401 it calls `/auth/refresh` once, then logs out.

Rate limits: register/login 5/minute per IP, refresh 30/minute; 429 body is `{"detail": …}`. Refresh tokens are single-use: presenting a previously-rotated token revokes all of the user's sessions.
