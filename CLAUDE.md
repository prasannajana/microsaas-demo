# CLAUDE.md - Project Verification Project Rules

> Project-specific rules for Claude Code. This file is read automatically.

---

## Project Overview

**Project Name:** Project Verification
**Description:** Scans a GitHub repository and produces an assessment of what's missing (README, tests, CI, Docker, env template, etc.), with severity, recommended fixes, and a 0-100 readiness score.
**Tech Stack:**
- Backend: FastAPI + Python 3.11+
- Frontend: React + Vite + TypeScript
- Database: PostgreSQL + SQLAlchemy + Alembic
- Auth: JWT (access + refresh) with Email/Password + Google OAuth
- UI: Chakra UI

---

## Project Structure

```
project-verification/
├── backend/
│   ├── app/
│   │   ├── main.py
│   │   ├── config.py
│   │   ├── database.py
│   │   ├── models/
│   │   │   ├── user.py
│   │   │   ├── refresh_token.py
│   │   │   ├── project.py
│   │   │   ├── scan.py
│   │   │   └── finding.py
│   │   ├── schemas/
│   │   │   ├── auth.py, project.py, scan.py, analytics.py, admin.py
│   │   ├── routers/
│   │   │   ├── auth.py, projects.py, scans.py, analytics.py, admin.py
│   │   ├── services/
│   │   │   ├── project_service.py
│   │   │   ├── scan_service.py        # orchestrates a scan run
│   │   │   └── analytics_service.py
│   │   ├── scanner/
│   │   │   ├── cloner.py              # safe shallow git clone into temp dir
│   │   │   ├── registry.py            # list of all checks
│   │   │   ├── scoring.py             # severity weights → score
│   │   │   └── checks/                # one module per check (missing_readme.py, ...)
│   │   └── auth/
│   ├── alembic/
│   ├── tests/
│   │   └── fixtures/repos/            # tiny sample repos for scanner tests
│   └── requirements.txt
├── frontend/
│   ├── src/
│   │   ├── components/                # ScoreBadge, FindingCard, SeverityTag, ...
│   │   ├── pages/
│   │   ├── hooks/                     # useScanStatus (polling), useProjects, ...
│   │   ├── services/
│   │   ├── context/
│   │   └── types/
│   └── package.json
├── .claude/
│   └── commands/
├── skills/
├── agents/
└── PRPs/
```

---

## Code Standards

### Python (Backend)
```python
# ALWAYS use type hints
def get_project(db: Session, project_id: int, user_id: int) -> Project | None:
    pass

# ALWAYS add docstrings for public functions
def create_scan(db: Session, project: Project) -> Scan:
    """
    Create a queued scan for a project.

    Args:
        db: Database session
        project: Project to scan (must belong to the current user)

    Returns:
        Created Scan object with status "queued"
    """
    pass
```

### Scanner checks
```python
# Every check is a pure function over the cloned repo path — no network, no execution.
@dataclass(frozen=True)
class CheckResult:
    check_id: str
    category: Category
    severity: Severity
    title: str
    recommendation: str
    file_path: str | None = None

def check_missing_readme(repo_root: Path) -> CheckResult | None:
    """Return a CheckResult if the repo has no README, else None."""
    ...
```

### TypeScript (Frontend)
```typescript
// ALWAYS define interfaces for props and data
interface Finding {
  id: number;
  checkId: string;
  category: FindingCategory;
  severity: Severity;
  title: string;
  recommendation: string;
  filePath: string | null;
}

// NO any types allowed
const fetchScan = async (scanId: number): Promise<Scan> => {
  // ...
};
```

---

## Forbidden Patterns

### Backend
- ❌ Never use `print()` - use `logging` module
- ❌ Never store passwords in plain text - use bcrypt
- ❌ Never hardcode secrets - use environment variables
- ❌ Never use `SELECT *` - specify columns
- ❌ Never skip input validation
- ❌ Never call git (or any subprocess) with `shell=True` or a string command - always an argument list
- ❌ Never execute, import, or install anything from a scanned repository
- ❌ Never follow symlinks out of the clone directory
- ❌ Never leave cloned repos on disk - clean up in `finally`

### Frontend
- ❌ Never use `any` type
- ❌ Never leave console.log in production
- ❌ Never skip error handling in async operations
- ❌ Never use inline styles - use Chakra UI style props / theme

---

## Module-Specific Rules

### Projects Module
- Every Project belongs to a user (`user_id` FK); all queries filter by the current user - return 404 (not 403) for other users' projects
- `repo_url` must match `^https://github\.com/[\w.-]+/[\w.-]+/?$`; normalize by stripping trailing `/` and `.git`
- Only one active scan per project: reject with 409 if a scan is `queued` or `running`
- Scan `status` must be one of: `queued`, `running`, `completed`, `failed`
- Finding `severity` must be one of: `critical`, `high`, `medium`, `low`
- Finding `category` must be one of: `documentation`, `testing`, `ci_cd`, `deployment`, `configuration`, `dependencies`
- Score = 100 − (critical 25, high 15, medium 8, low 3 per finding), floored at 0; store on Scan and copy to `Project.latest_score`
- Clone limits: `--depth 1`, 60s timeout, 200 MB max size, `GIT_TERMINAL_PROMPT=0`; failures set `status=failed` with a user-readable `error_message`
- Adding a new check = new file in `scanner/checks/` + register it + fixture-based test

### Analytics Module
- All analytics are scoped to the current user's data

### Admin Module
- All `/admin` endpoints require `is_admin`; return 403 otherwise
- Admins cannot deactivate themselves

---

## API Conventions

- All endpoints prefixed with `/api/v1/`
- Use plural nouns for resources: `/projects`, `/scans`
- Return appropriate HTTP status codes:
  - 200: Success
  - 201: Created
  - 202: Accepted (scan started)
  - 400: Bad Request
  - 401: Unauthorized
  - 403: Forbidden (admin only)
  - 404: Not Found
  - 409: Conflict (scan already running, email taken)
  - 429: Too Many Requests

---

## Authentication

Email/Password + Google OAuth, both issuing the same JWT pair.

### JWT Configuration
- Access token expires: 30 minutes
- Refresh token expires: 7 days
- Algorithm: HS256

### OAuth Providers
- Google OAuth 2.0 enabled
- Always verify state parameter for CSRF protection
- OAuth users may have `hashed_password = NULL`

---

## Environment Variables

```env
# Database
DATABASE_URL=postgresql://user:password@localhost:5432/project_verification

# Auth
SECRET_KEY=your-secret-key-change-in-production
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=30
REFRESH_TOKEN_EXPIRE_DAYS=7

# Google OAuth
GOOGLE_CLIENT_ID=your-client-id
GOOGLE_CLIENT_SECRET=your-client-secret
GOOGLE_REDIRECT_URI=http://localhost:8000/api/v1/auth/google/callback

# Scanner
SCAN_WORKDIR=/tmp/project-verification
SCAN_CLONE_TIMEOUT_SECONDS=60
SCAN_MAX_REPO_SIZE_MB=200
SCANS_PER_HOUR_PER_USER=10
GITHUB_TOKEN=            # optional, raises GitHub API rate limits

# Frontend
VITE_API_URL=http://localhost:8000
```

---

## Development Commands

```bash
# Backend
cd backend
pip install -r requirements.txt
alembic upgrade head
uvicorn app.main:app --reload

# Frontend
cd frontend
npm install
npm run dev

# Docker (backend image must include git)
docker-compose up -d

# Tests
pytest backend/tests -v
cd frontend && npm test

# Linting
ruff check backend/
cd frontend && npm run lint && npm run type-check
```

---

## Commit Message Format

```
feat([module]): add [feature]
fix([module]): fix [bug]
refactor([module]): refactor [component]
test([module]): add tests for [feature]
docs: update [documentation]
```

Modules: `auth`, `projects`, `scanner`, `analytics`, `admin`, `ui`, `infra`

---

## Skills Reference

| Task | Skill to Read |
|------|---------------|
| Database models | skills/DATABASE.md |
| API + Auth | skills/BACKEND.md |
| React + UI | skills/FRONTEND.md |
| Testing | skills/TESTING.md |
| Deployment | skills/DEPLOYMENT.md |

---

## Agent Coordination

For complex tasks, the ORCHESTRATOR coordinates:
- DATABASE-AGENT → Backend models
- BACKEND-AGENT → API development + scanner engine
- FRONTEND-AGENT → UI components
- TEST-AGENT → Testing (fixture repos per check)
- REVIEW-AGENT → Code review (focus: clone/URL/subprocess safety)
- DEVOPS-AGENT → Deployment

Read agent definitions in `/agents/` folder.
