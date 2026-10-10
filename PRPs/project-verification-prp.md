# PRP: Project Verification

> Implementation blueprint for parallel agent execution

---

## METADATA

| Field | Value |
|-------|-------|
| **Product** | Project Verification |
| **Type** | SaaS |
| **Version** | 1.0 |
| **Created** | 2026-10-10 |
| **Complexity** | Medium (standard CRUD + auth, plus a sandboxed background scanner) |
| **Source** | INITIAL.md |

---

## PRODUCT OVERVIEW

**Description:** Users add a public GitHub repository as a project and run a verification scan. The scanner shallow-clones the repo, runs a set of "missing essentials" checks (README, license, tests, CI, Docker, dependency manifest, env template, committed `.env`, ...), and produces an assessment report: a 0-100 readiness score plus one finding per gap with severity and a recommended fix.

**Value Proposition:** A one-click, objective answer to "is this project ready to ship / hand over / open-source, and what exactly do I fix first?" — without reading the whole codebase.

**Target User:** Developers and small software teams.

**MVP Scope:**
- [ ] Registration and login (email/password + Google OAuth)
- [ ] Add a project by public GitHub URL
- [ ] Run a scan in the background and poll its status
- [ ] View the assessment report (score, findings grouped by category, recommendations)

**Post-MVP (built after MVP passes all gates):** scan history UI, Analytics Dashboard, Admin Panel.

---

## TECH STACK

| Layer | Technology | Skill Reference |
|-------|------------|-----------------|
| Backend | FastAPI + Python 3.11+ (sync SQLAlchemy sessions) | skills/BACKEND.md |
| Frontend | React + TypeScript + Vite, React Query | skills/FRONTEND.md |
| Database | PostgreSQL + SQLAlchemy + Alembic | skills/DATABASE.md |
| Auth | JWT (python-jose) + bcrypt (passlib) + Google OAuth (httpx) | skills/BACKEND.md |
| UI | Chakra UI (+ Framer Motion per FRONTEND.md components) | skills/FRONTEND.md |
| Scanner | `git` CLI via `subprocess.run([...])`, `pathlib`, `tempfile` | — (rules in CLAUDE.md) |
| Charts | Recharts (dashboard only, post-MVP) | skills/FRONTEND.md |
| Testing | pytest + pytest-cov, Vitest + React Testing Library | skills/TESTING.md |
| Deployment | Docker + docker-compose + GitHub Actions | skills/DEPLOYMENT.md |

### Deviations from skill files (INITIAL.md / CLAUDE.md win)
- **User admin flag:** use `is_admin: bool` instead of the `role` enum in DATABASE.md. Keep `google_id` and `avatar_url` from DATABASE.md and add `oauth_provider`.
- **Google OAuth callback:** handled by the backend at `/api/v1/auth/google/callback` (`GOOGLE_REDIRECT_URI`). The backend then redirects to `${FRONTEND_URL}/auth/callback` with the tokens in the URL fragment.
- **No `any`:** the React Query example in FRONTEND.md uses `data: any`; replace it with typed payloads.
- **Backend Docker image** must `apt-get install -y git`.

---

## DATABASE MODELS

All models use `TimestampMixin` (created_at, updated_at) from `models/base.py`.

### User (`users`)
- id (PK), email (unique, indexed), hashed_password (nullable), full_name, is_active (default true), is_verified (default false), is_admin (default false), oauth_provider (nullable: `"google"`), google_id (unique, nullable), avatar_url (nullable)
- Relationships: projects (1-N, cascade delete), refresh_tokens (1-N, cascade delete)

### RefreshToken (`refresh_tokens`)
- id, user_id (FK users, indexed, ondelete CASCADE), token (unique, indexed), expires_at, revoked (default false)

### Project (`projects`)
- id, user_id (FK users, indexed, ondelete CASCADE), name (String 100), repo_url (String 500, normalized), default_branch (String 100, nullable → use the remote HEAD), primary_language (nullable), latest_score (Integer, nullable), last_scanned_at (nullable)
- Unique constraint: (user_id, repo_url)
- Relationships: scans (1-N, cascade delete, ordered by created_at desc)

### Scan (`scans`)
- id, project_id (FK projects, indexed, ondelete CASCADE), status (Enum `ScanStatus`: queued | running | completed | failed, indexed), score (Integer, nullable), commit_sha (String 40, nullable), error_message (Text, nullable), started_at (nullable), completed_at (nullable)
- Relationships: findings (1-N, cascade delete)
- Index: (project_id, created_at)

### Finding (`findings`)
- id, scan_id (FK scans, indexed, ondelete CASCADE), check_id (String 50), category (Enum `FindingCategory`: documentation | testing | ci_cd | deployment | configuration | dependencies), severity (Enum `Severity`: critical | high | medium | low), title (String 200), recommendation (Text), file_path (String 500, nullable)

**Migration:** a single initial Alembic revision `0001_initial` creating all 5 tables and 3 enums.

---

## SCANNER ENGINE (core logic)

**Owner:** BACKEND-AGENT. Lives in `backend/app/scanner/`. It has no DB or HTTP dependencies, so it can be unit-tested against fixture directories.

### `cloner.py`
```python
def clone_repo(repo_url: str, branch: str | None, dest: Path) -> CloneResult:
    """Shallow-clone a validated GitHub URL into dest. Returns commit_sha. Raises CloneError."""
```
- Re-validate the URL with `GITHUB_URL_RE` before cloning, even if the API layer already did.
- Run `subprocess.run(["git", "clone", "--depth", "1", "--single-branch", *(["--branch", branch] if branch else []), "--", url, str(dest)], timeout=settings.SCAN_CLONE_TIMEOUT_SECONDS, env={..., "GIT_TERMINAL_PROMPT": "0", "GIT_LFS_SKIP_SMUDGE": "1"}, capture_output=True, check=False)`.
- Get the commit with `git -C dest rev-parse HEAD`.
- Compute size with `os.walk` (no symlink following). If it exceeds `SCAN_MAX_REPO_SIZE_MB`, raise `CloneError("Repository exceeds size limit")`.
- Map git stderr to friendly errors: repository not found or private, branch not found, timeout.

### `checks/` (one file per check), `registry.py`, `scoring.py`
- Each check is `Callable[[Path], CheckResult | None]` and returns a result only when something is missing.
- Use only `Path.is_file()` / `is_dir()` / `glob` inside the repo root. Skip `.git/`, `node_modules/`, `venv/`, `.venv/`, `dist/`, `build/`.
- Resolve every path and ensure it stays under the repo root (symlink guard).

| check_id | Passes if… | Category | Severity |
|----------|-----------|----------|----------|
| missing_readme | `README*` at root | documentation | high |
| missing_license | `LICENSE*` / `COPYING*` at root | documentation | medium |
| missing_gitignore | `.gitignore` at root | configuration | medium |
| missing_dependency_manifest | any of requirements.txt, pyproject.toml, Pipfile, package.json, go.mod, pom.xml, build.gradle(.kts), Cargo.toml, Gemfile, composer.json (root or one level deep) | dependencies | critical |
| missing_lockfile | a lockfile matching a found manifest (skipped if no manifest or `requirements.txt` only) | dependencies | low |
| missing_tests | `tests/`/`test/`/`__tests__/` dir, or files `test_*.py`, `*_test.py`, `*_test.go`, `*.test.[jt]s(x)`, `*.spec.[jt]s(x)` | testing | critical |
| missing_ci | `.github/workflows/*.y*ml`, `.gitlab-ci.yml`, `.circleci/config.yml`, `azure-pipelines.yml`, `Jenkinsfile` | ci_cd | high |
| missing_dockerfile | `Dockerfile*` or `docker-compose*.y*ml` / `compose*.y*ml` | deployment | low |
| missing_env_example | `.env.example` / `.env.sample` / `.env.template` exists, **or** no source file references env vars (`os.environ`, `os.getenv`, `process.env`, `import.meta.env`; scan ≤ 2,000 source files, ≤ 1 MB each) | configuration | medium |
| committed_env_file | no `.env` / `.env.local` / `.env.production` tracked anywhere (excluding example/sample/template) | configuration | critical |

- `detect_primary_language(repo_root)` counts file extensions and returns the top language, or `None`.
- `compute_score(results)` returns `max(0, 100 - Σ weight)` with weights {critical 25, high 15, medium 8, low 3}.

### `services/scan_service.py`
```python
def start_scan(db: Session, project: Project) -> Scan            # 409 if active scan exists; creates status=queued
def run_scan(scan_id: int) -> None                               # BackgroundTasks entrypoint
```
`run_scan` must open its own `SessionLocal()`, because the request session is closed by the time it runs. Steps:
1. Set status=running and started_at.
2. Create a `tempfile.mkdtemp(dir=settings.SCAN_WORKDIR)`.
3. Clone, run all registered checks, and detect the language.
4. Insert findings; set score, commit_sha, status=completed and completed_at.
5. Update `Project.latest_score`, `last_scanned_at` and `primary_language`.
6. On any exception: set status=failed with a user-readable `error_message`, and log the full traceback via `logging`.
7. Always run `shutil.rmtree(tmp, ignore_errors=True)` in `finally`.

On startup, scans left in `queued` or `running` (for example after a crash) are marked `failed` with "Scan interrupted, please retry".

---

## MODULES

### Module 1: Authentication — MVP
**Agents:** DATABASE-AGENT + BACKEND-AGENT + FRONTEND-AGENT

**Backend Endpoints:**
| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | /api/v1/auth/register | Create account (409 if email exists) |
| POST | /api/v1/auth/login | Email/password → access + refresh tokens |
| POST | /api/v1/auth/refresh | Rotate refresh token, new access token |
| POST | /api/v1/auth/logout | Revoke refresh token |
| GET | /api/v1/auth/me | Current user |
| PUT | /api/v1/auth/me | Update full_name |
| GET | /api/v1/auth/google | Redirect to Google with signed `state` (stored in an HttpOnly cookie) |
| GET | /api/v1/auth/google/callback | Verify `state`, exchange code, upsert user, redirect to frontend with tokens |

Rate limit (slowapi): register, login and refresh at 5/minute per IP.

**Frontend Pages:**
| Route | Page | Components |
|-------|------|------------|
| /login | LoginPage | MeshBackground, GlassCard, AnimatedInput, GradientButton, GoogleButton |
| /register | RegisterPage | MeshBackground, GlassCard, AnimatedInput, GradientButton |
| /forgot-password | ForgotPasswordPage | GlassCard, AnimatedInput (UI only; email sending is post-MVP, so show "contact support") |
| /auth/callback | OAuthCallbackPage | Reads tokens from URL fragment → AuthContext → redirect /projects |
| /profile | ProfilePage (protected) | PageWrapper, GlassCard, AnimatedInput |

---

### Module 2: Projects (Scans + Findings) — MVP
**Agents:** BACKEND-AGENT + FRONTEND-AGENT

**Backend Endpoints:**
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | /api/v1/projects?page=&size= | List current user's projects with latest score |
| POST | /api/v1/projects | Create `{name, repo_url, default_branch?}`; 400 invalid URL, 409 duplicate |
| GET | /api/v1/projects/{id} | Project + latest scan (with findings) |
| PUT | /api/v1/projects/{id} | Update name / default_branch |
| DELETE | /api/v1/projects/{id} | Delete project + scans (204) |
| POST | /api/v1/projects/{id}/scans | Start scan → 202 `{id, status}`; 409 if active; 429 if over `SCANS_PER_HOUR_PER_USER` |
| GET | /api/v1/projects/{id}/scans | Scan history (no findings, newest first) |
| GET | /api/v1/scans/{scan_id} | Scan status, score, findings (ownership checked via project.user_id) |

All lookups filter by `current_user.id`. A resource owned by someone else returns **404**.

**Key schemas:** `ProjectCreate`, `ProjectUpdate`, `ProjectOut`, `ProjectDetail`, `ScanSummary`, `ScanDetail`, `FindingOut`, `Page[T]`. The `repo_url` validator normalizes the URL (strips trailing `/` and `.git`, lowercases the host) and matches `^https://github\.com/[\w.-]+/[\w.-]+$`.

**Frontend Pages:**
| Route | Page | Components |
|-------|------|------------|
| /projects | ProjectsListPage | PageWrapper, AnimatedList, ProjectCard, ScoreBadge, EmptyState |
| /projects/new | NewProjectPage | GlassCard, AnimatedInput, GradientButton (client-side URL validation mirrors backend) |
| /projects/:id | ProjectDetailPage | ScanButton, ScanStatusBanner, ScoreGauge, FindingsByCategory, FindingCard, SeverityTag, ScanHistoryTable (post-MVP) |
| /projects/:id/scans/:scanId | ScanReportPage | ScoreGauge, FindingsByCategory, FindingCard |

**Hooks:** `useProjects`, `useProject(id)`, `useCreateProject`, `useDeleteProject`, `useStartScan`, and `useScan(scanId)`. `useScan` uses `refetchInterval: 2000` while the status is `queued` or `running` and stops otherwise. The report shows a "No issues found 🎉" state when the score is 100.

---

### Module 3: Analytics Dashboard — Post-MVP
**Agents:** BACKEND-AGENT + FRONTEND-AGENT

**Backend Endpoints:**
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | /api/v1/analytics/summary | project_count, scan_count, avg_latest_score, open_critical_findings |
| GET | /api/v1/analytics/score-trend?days=30 | `[{project_id, name, points: [{date, score}]}]` from completed scans |
| GET | /api/v1/analytics/common-findings?limit=5 | Most frequent check_ids in each project's latest scan |

All analytics use aggregate SQL queries scoped to the current user, with no N+1 queries.

**Frontend Pages:**
| Route | Page | Components |
|-------|------|------------|
| /dashboard | DashboardPage | StatCard ×4, ScoreTrendChart (Recharts), CommonFindingsList, RecentScansList |
| /settings | SettingsPage | GlassCard (profile link, sign out everywhere) |

Until this module ships, `/` redirects to `/projects`. After that it redirects to `/dashboard`.

---

### Module 4: Admin Panel — Post-MVP
**Agents:** BACKEND-AGENT + FRONTEND-AGENT

**Backend Endpoints** (all use the `get_current_admin` dependency, which returns 403 for non-admins):
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | /api/v1/admin/users?page=&q= | List/search users |
| PUT | /api/v1/admin/users/{id} | Update is_active / is_admin (cannot change self) |
| GET | /api/v1/admin/stats | users, projects, scans (24h / total), failure rate |
| GET | /api/v1/admin/scans?status= | Recent scans across all users |

The first admin is created with the CLI `python -m app.cli make-admin <email>`.

**Frontend Pages:**
| Route | Page | Components |
|-------|------|------------|
| /admin | AdminDashboardPage | AdminRoute guard, StatCard |
| /admin/users | AdminUsersPage | Table, Switch (active/admin) |
| /admin/scans | AdminScansPage | Table, status filter |

---

## TOTALS

| | Count |
|--|------|
| Modules | 4 (2 MVP + 2 post-MVP) |
| Models | 5 |
| API endpoints | 23 (+ `/health`) |
| Pages | 16 |
| Scanner checks | 10 |

---

## PHASE EXECUTION PLAN

**Phase 1: Foundation (4 agents in parallel)**
- DATABASE-AGENT: `database.py`, `models/base.py`, all 5 models + enums, Alembic setup + `0001_initial`
- BACKEND-AGENT: `main.py` (CORS, `/health`, router includes, startup "interrupted scans" cleanup), `config.py` with all env vars from CLAUDE.md, `exceptions.py`, `requirements.txt`, empty routers
- FRONTEND-AGENT: Vite + TS strict, Chakra provider + theme, React Query, axios client with refresh interceptor, AuthContext, ProtectedRoute, router skeleton, shared components (PageWrapper, GlassCard, GradientButton, AnimatedInput, AnimatedList, MeshBackground)
- DEVOPS-AGENT: backend Dockerfile (with git), frontend Dockerfile + nginx, docker-compose (db, backend, frontend, `scan_tmp` volume), `.env.example`, `.github/workflows/ci.yml`

**Validation Gate 1:** `pip install -r backend/requirements.txt`, `alembic upgrade head`, `npm install`, `docker-compose config`

**Phase 2a: MVP modules (backend + frontend in parallel per module)**
- Auth: JWT + Google OAuth endpoints ↔ login / register / callback / profile pages
- Projects: scanner engine + project/scan endpoints ↔ projects list / new / detail / report pages
  - Contract first: BACKEND-AGENT publishes the Pydantic schemas in `schemas/project.py` and `schemas/scan.py` before FRONTEND-AGENT writes `types/`. Backend naming wins on conflicts.

**Validation Gate 2a:** `ruff check backend/`, `mypy backend/app`, `npm run lint`, `npm run type-check`, plus a manual smoke test: register, add `https://github.com/tiangolo/fastapi`, scan, and see the report

**Phase 2b: Post-MVP modules (parallel)**
- Analytics: endpoints ↔ dashboard / settings
- Admin: endpoints + make-admin CLI ↔ admin pages
- Projects: ScanHistoryTable on the project detail page

**Validation Gate 2b:** same as 2a

**Phase 3: Quality (parallel)**
- TEST-AGENT:
  - Scanner unit tests: `tests/fixtures/repos/` holds `complete/` (passes every check), `empty/`, and one fixture per check. Assert exact check_ids and the score.
  - Cloner tests mock `subprocess.run` for success, not found, timeout and oversize. No network calls in tests.
  - API integration tests: auth flow; project CRUD; ownership isolation (user B gets 404 on user A's project); 409 for an active scan; 400 for a bad URL; 403 on admin endpoints; `run_scan` with a patched cloner (completed and failed paths, temp dir removed).
  - Frontend: Vitest + RTL for LoginForm, NewProjectPage validation, FindingsByCategory, and polling in `useScan`.
- REVIEW-AGENT: security audit focused on subprocess/URL handling, path traversal and symlinks, OAuth state, token storage, rate limits, and authorization on every endpoint
- RESEARCH-AGENT (optional): validate the check list against common repo-health standards (e.g. OpenSSF Scorecard, GitHub community profile)

**Final Validation:** full test suite, Docker build, health check, and an end-to-end scan inside Docker

---

## VALIDATION GATES

| Gate | Commands |
|------|----------|
| 1 | `alembic upgrade head`, `npm install`, `docker-compose config` |
| 2a / 2b | `ruff check backend/`, `mypy backend/app`, `npm run lint`, `npm run type-check` |
| 3 | `pytest backend/tests --cov=app --cov-fail-under=80`, `cd frontend && npm test -- --run` |
| Final | `docker-compose up -d --build`, `curl -f localhost:8000/health`, register → create project → `POST /scans` → poll until `completed` |

---

## ENVIRONMENT VARIABLES

```env
# Database
DATABASE_URL=postgresql://user:password@localhost:5432/project_verification

# Auth
SECRET_KEY=your-secret-key-change-in-production
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=30
REFRESH_TOKEN_EXPIRE_DAYS=7
FRONTEND_URL=http://localhost:5173
ALLOWED_ORIGINS=["http://localhost:5173"]

# Google OAuth
GOOGLE_CLIENT_ID=your-client-id
GOOGLE_CLIENT_SECRET=your-client-secret
GOOGLE_REDIRECT_URI=http://localhost:8000/api/v1/auth/google/callback

# Scanner
SCAN_WORKDIR=/tmp/project-verification
SCAN_CLONE_TIMEOUT_SECONDS=60
SCAN_MAX_REPO_SIZE_MB=200
SCANS_PER_HOUR_PER_USER=10
GITHUB_TOKEN=

# Frontend
VITE_API_URL=http://localhost:8000
```

---

## RISKS & NOTES

| Risk | Mitigation |
|------|-----------|
| Command injection or SSRF through `repo_url` | Strict regex validation at the API and again in the cloner; argument-list subprocess call with `--` separator; HTTPS GitHub only |
| Malicious repos (huge, symlinks, git hooks) | Shallow clone, size cap, timeout, no checkout hooks run on clone, symlink guard, never execute repo code |
| BackgroundTasks lost on restart | Mark stale queued/running scans as failed on startup. Move to a real queue (RQ/Celery) post-MVP if volume grows |
| Disk filling with clones | `finally: rmtree`, dedicated `SCAN_WORKDIR` volume |
| Missing agent definitions | Only `ORCHESTRATOR`, `backend-agent`, `database-agent` and `frontend-agent` exist in `agents/`. DEVOPS, TEST and REVIEW roles run as general agents using the matching skill file and this PRP |

---

## NEXT STEP

Execute with parallel agents:
/execute-prp PRPs/project-verification-prp.md
