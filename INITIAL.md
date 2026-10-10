# INITIAL.md - Project Verification Product Definition

> Scan a software project from its GitHub repo and get an assessment of what's missing and what to do about it.

---

## PRODUCT

### Name
Project Verification

### Description
Project Verification scans an application's codebase from a public GitHub repository and produces an assessment report. The report lists the essentials the project is missing (README, tests, CI, Docker setup, environment template and similar), rates each gap by severity, gives a recommended fix for each one, and rolls everything into a single 0-100 readiness score. Users can rescan after making changes and watch the score improve.

### Target User
Developers and small software teams who want an automated health check of their codebase before shipping, handing over, or open-sourcing a project.

### Type
- [x] SaaS (Software as a Service)

---

## TECH STACK

### Backend
- [x] FastAPI + Python 3.11+

### Frontend
- [x] React + Vite + TypeScript

### Database
- [x] PostgreSQL + SQLAlchemy + Alembic

### Authentication
- [x] Email/Password + Google OAuth (JWT access + refresh tokens)

### UI Framework
- [x] Chakra UI

### Payments
- [ ] None (free product for now)

### Scan Execution
- [x] `git clone --depth 1` of public GitHub repos into an isolated temp directory
- [x] FastAPI `BackgroundTasks` for running scans (no external queue for MVP)

---

## MODULES

### Module 1: Authentication (Required)

**Description:** User authentication and authorization

**Models:**
- User: id, email, hashed_password (nullable for OAuth users), full_name, is_active, is_verified, is_admin, oauth_provider, created_at, updated_at
- RefreshToken: id, user_id (FK), token, expires_at, revoked, created_at

**API Endpoints:**
- POST /api/v1/auth/register - Create new account
- POST /api/v1/auth/login - Login with email/password
- POST /api/v1/auth/refresh - Refresh access token
- POST /api/v1/auth/logout - Revoke refresh token
- GET /api/v1/auth/me - Get current user profile
- PUT /api/v1/auth/me - Update profile
- GET /api/v1/auth/google - Start Google OAuth flow
- GET /api/v1/auth/google/callback - Handle Google OAuth callback

**Frontend Pages:**
- /login - Login page (email/password + "Continue with Google")
- /register - Registration page
- /forgot-password - Forgot password page
- /profile - User profile page (protected)

---

### Module 2: Projects (Core)

**Description:** Users register GitHub repositories as projects, run verification scans on them, and review the resulting assessment reports. Scans and findings live inside this module.

**Models:**
- Project: id, user_id (FK → users), name, repo_url, default_branch, primary_language (nullable, detected on scan), latest_score (nullable, 0-100), last_scanned_at (nullable), created_at, updated_at
- Scan: id, project_id (FK → projects, cascade delete), status (`queued` | `running` | `completed` | `failed`), score (nullable, 0-100), commit_sha (nullable), error_message (nullable), started_at, completed_at, created_at
- Finding: id, scan_id (FK → scans, cascade delete), check_id (e.g. `missing_readme`), category (`documentation` | `testing` | `ci_cd` | `deployment` | `configuration` | `dependencies`), title, severity (`critical` | `high` | `medium` | `low`), recommendation (text), file_path (nullable), created_at

**Checks performed ("missing essentials"):**

| check_id | What is checked | Category | Severity |
|----------|-----------------|----------|----------|
| missing_readme | README.md / README.rst at repo root | documentation | high |
| missing_license | LICENSE / LICENSE.md / COPYING | documentation | medium |
| missing_gitignore | .gitignore at repo root | configuration | medium |
| missing_dependency_manifest | requirements.txt / pyproject.toml / package.json / go.mod / pom.xml / Cargo.toml | dependencies | critical |
| missing_lockfile | poetry.lock / package-lock.json / yarn.lock / pnpm-lock.yaml (when a manifest exists) | dependencies | low |
| missing_tests | tests/ or test/ directory, or `*_test.*` / `test_*.*` / `*.spec.*` / `*.test.*` files | testing | critical |
| missing_ci | .github/workflows/*.yml, .gitlab-ci.yml, or similar CI config | ci_cd | high |
| missing_dockerfile | Dockerfile or docker-compose.yml | deployment | low |
| missing_env_example | .env.example / .env.sample when code reads environment variables | configuration | medium |
| committed_env_file | a real `.env` file committed to the repo | configuration | critical |

**Scoring:** Start at 100 and subtract per finding (critical −25, high −15, medium −8, low −3), floored at 0.

**API Endpoints:**
- GET /api/v1/projects - List current user's projects (paginated)
- POST /api/v1/projects - Create project from a GitHub URL (validated: `https://github.com/<owner>/<repo>` only)
- GET /api/v1/projects/{id} - Get project with its latest scan summary
- PUT /api/v1/projects/{id} - Update name / branch
- DELETE /api/v1/projects/{id} - Delete project and all its scans
- POST /api/v1/projects/{id}/scans - Start a scan (returns 202 with scan id; 409 if a scan is already running)
- GET /api/v1/projects/{id}/scans - List scan history for a project
- GET /api/v1/scans/{scan_id} - Get scan status, score and findings

**Frontend Pages:**
- /projects - Project list with latest score badges
- /projects/new - Add project form (GitHub URL, optional branch)
- /projects/{id} - Project detail: "Run scan" button, live status while running, latest assessment report (score, findings grouped by category, severity badges, recommendations)
- /projects/{id}/scans/{scanId} - Report for a specific past scan

---

### Module 3: Analytics Dashboard

**Description:** Overview of the user's projects and how their readiness changes over time.

**API Endpoints:**
- GET /api/v1/analytics/summary - Totals: projects, scans run, average score, critical findings open
- GET /api/v1/analytics/score-trend - Score per project over time
- GET /api/v1/analytics/common-findings - Most frequent missing items across the user's projects

**Frontend Pages:**
- /dashboard - Stat cards, score-over-time chart, top missing items, recent scans
- /settings - User settings and preferences

---

### Module 4: Admin Panel

**Description:** Admin-only management interface (requires `is_admin`).

**API Endpoints:**
- GET /api/v1/admin/users - List all users
- PUT /api/v1/admin/users/{id} - Update user status (activate/deactivate, admin flag)
- GET /api/v1/admin/stats - Platform statistics (users, projects, scans, failure rate)
- GET /api/v1/admin/scans - Recent scans across all users, filterable by status

**Frontend Pages:**
- /admin - Admin dashboard (protected, admin only)
- /admin/users - User management
- /admin/scans - Scan monitoring

---

## MVP SCOPE

### Must Have (MVP)
- [x] User registration and login (email/password + Google)
- [x] Run a scan on a GitHub repo and get the "missing essentials" assessment
- [x] Minimum needed to support scanning: add a project by GitHub URL, and view the resulting report (score + findings + recommendations)

### Nice to Have (Post-MVP)
- [ ] Scan history and score comparison between runs
- [ ] Analytics Dashboard
- [ ] Admin Panel
- [ ] Private repositories (GitHub OAuth/token)
- [ ] Additional check categories: security (secrets, vulnerable dependencies), code quality (lint, complexity)
- [ ] AI-generated "what to do next" plan
- [ ] ZIP upload as an alternative source
- [ ] Email notifications when a scan finishes
- [ ] Paid plans

---

## ACCEPTANCE CRITERIA

### Authentication
- [ ] User can register with email/password
- [ ] User can login with email/password
- [ ] User can sign up / log in with Google OAuth
- [ ] OAuth state parameter is verified (CSRF protection)
- [ ] JWT tokens work correctly with refresh
- [ ] Protected routes redirect to login

### Projects
- [ ] User can add a project with a valid public GitHub URL
- [ ] Non-GitHub, malformed, or non-HTTPS URLs are rejected with 400
- [ ] User only ever sees and modifies their own projects (404 for others')
- [ ] User can start a scan; the API returns 202 immediately and the scan runs in the background
- [ ] Starting a scan while one is running returns 409
- [ ] Scan status moves queued → running → completed (or failed with an error message)
- [ ] Completed scans produce one Finding per missing essential, with severity and recommendation
- [ ] Score is computed with the documented weights and stored on both Scan and Project
- [ ] Repos that don't exist, are private, or exceed the size limit fail gracefully with a clear message
- [ ] Cloned repos are deleted after every scan, success or failure
- [ ] Report page shows score, findings grouped by category, and what to do for each

### Analytics Dashboard
- [ ] Dashboard shows summary stats, score trend, and most common missing items for the current user only

### Admin Panel
- [ ] Non-admins get 403 on all /admin endpoints and cannot open /admin pages
- [ ] Admin can list users, deactivate users, and view platform stats

### Quality
- [ ] All API endpoints documented in OpenAPI
- [ ] Backend test coverage 80%+ (scanner checks tested against fixture repos)
- [ ] Frontend TypeScript strict mode passes
- [ ] Docker builds and runs successfully

---

## SPECIAL REQUIREMENTS

### Security
- [x] Rate limiting on auth endpoints and on scan creation (e.g. 10 scans/hour/user)
- [x] Input validation on all endpoints
- [x] SQL injection prevention (ORM only)
- [x] XSS prevention
- [x] CSRF protection for OAuth (state parameter)
- [x] Repo URL strictly validated against `^https://github\.com/[\w.-]+/[\w.-]+/?$`; git invoked with an argument list (never `shell=True`)
- [x] Scanned code is only read, never executed or installed
- [x] Clone limits: shallow clone, timeout (60s), max repo size (e.g. 200 MB), `GIT_TERMINAL_PROMPT=0`
- [x] Symlinks inside cloned repos are not followed outside the clone directory

### Integrations
- [ ] Email service for notifications
- [ ] Payments
- [ ] File upload service
- [x] GitHub (public HTTPS clone; optional `GITHUB_TOKEN` for higher API rate limits)

---

## AGENTS

> These 6 agents will build your product in parallel:

| Agent | Role | Works On |
|-------|------|----------|
| DATABASE-AGENT | Creates all models and migrations | User, RefreshToken, Project, Scan, Finding |
| BACKEND-AGENT | Builds API endpoints and services | Auth, Projects/Scans, scanner engine, Analytics, Admin |
| FRONTEND-AGENT | Creates UI pages and components | Auth pages, project/report pages, dashboard, admin |
| DEVOPS-AGENT | Sets up Docker, CI/CD, environments | Docker (with git installed), GitHub Actions |
| TEST-AGENT | Writes unit and integration tests | All code, incl. fixture repos for each check |
| REVIEW-AGENT | Security and code quality audit | All code, esp. clone/URL handling |

---

# READY?

```bash
/generate-prp INITIAL.md
```

Then:

```bash
/execute-prp PRPs/project-verification-prp.md
```
