"""Acceptance-criteria traceability (INITIAL.md -> tests).

Every backend acceptance criterion from INITIAL.md is mapped to at least one test
node below. ``test_every_criterion_is_traced`` fails if a referenced test is
renamed or removed, so the checklist cannot silently rot. A few criteria that had
no direct test elsewhere are verified here (OpenAPI completeness, score weights).

Frontend-only criteria ("Protected routes redirect to login", "Report page shows ...",
"cannot open /admin pages", "Frontend TypeScript strict mode passes") are covered by
the Vitest suite / ``npm run type-check`` and listed in FRONTEND_CRITERIA for
completeness. "Docker builds and runs" is verified by the DevOps pipeline, not pytest.
"""

import importlib

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.models.finding import FindingCategory, Severity
from app.scanner.scoring import compute_score
from app.scanner.types import CheckResult

CRITERIA: dict[str, list[str]] = {
    # ---- Authentication
    "User can register with email/password": [
        "test_auth::test_register_returns_token_pair",
        "test_e2e_flow::test_full_user_flow",
    ],
    "User can login with email/password": ["test_auth::test_login_success"],
    "User can sign up / log in with Google OAuth": [
        "test_auth::test_google_callback_creates_user",
        "test_auth::test_google_callback_links_existing_account",
    ],
    "OAuth state parameter is verified (CSRF protection)": [
        "test_auth::test_google_callback_state_mismatch",
        "test_auth::test_google_callback_missing_cookie",
    ],
    "JWT tokens work correctly with refresh": [
        "test_auth::test_refresh_rotates_tokens",
        "test_auth::test_refresh_expired_jwt",
        "test_service_edges::test_refresh_revoked_token_cannot_be_reused",
    ],
    # ---- Projects
    "User can add a project with a valid public GitHub URL": [
        "test_scanner_api::test_create_normalizes_url",
    ],
    "Non-GitHub, malformed, or non-HTTPS URLs are rejected with 400": [
        "test_scanner_api::test_create_invalid_url_400",
        "test_scanner::test_normalize_github_url_invalid",
    ],
    "User only ever sees and modifies their own projects (404 for others')": [
        "test_scanner_api::test_other_users_project_is_404",
        "test_scanner_api::test_get_scan_ownership",
        "test_e2e_flow::test_flow_other_user_isolation",
    ],
    "User can start a scan; API returns 202 and the scan runs in the background": [
        "test_scanner_api::test_start_scan_202_then_409",
        "test_e2e_flow::test_full_user_flow",
    ],
    "Starting a scan while one is running returns 409": [
        "test_scanner_api::test_start_scan_202_then_409",
        "test_e2e_flow::test_flow_conflict_while_scan_active",
        "test_service_edges::test_start_scan_conflict_while_running",
    ],
    "Scan status moves queued -> running -> completed (or failed with message)": [
        "test_scanner_api::test_run_scan_completed",
        "test_scanner_api::test_run_scan_clone_error",
        "test_e2e_flow::test_flow_failed_clone_then_retry",
    ],
    "Completed scans produce one Finding per missing essential": [
        "test_scanner::test_empty_fixture_findings_and_score",
        "test_scanner::test_every_finding_has_metadata",
        "test_e2e_flow::test_full_user_flow",
    ],
    "Score uses documented weights and is stored on Scan and Project": [
        "test_scanner::test_score_weights",
        "test_acceptance_criteria::test_documented_score_weights",
        "test_scanner_api::test_run_scan_completed",
    ],
    "Missing/private/oversize repos fail gracefully with a clear message": [
        "test_scanner::test_clone_not_found",
        "test_scanner::test_clone_private_prompt_disabled",
        "test_scanner::test_clone_rejects_private_repo_before_cloning",
        "test_scanner::test_clone_rejects_oversized_repo_before_cloning",
        "test_scanner_safety::test_friendly_error_never_leaks_stderr",
    ],
    "Cloned repos are deleted after every scan, success or failure": [
        "test_service_edges::test_run_scan_clone_dir_removed_after_success",
        "test_service_edges::test_run_scan_check_crash_marks_failed_and_cleans_up",
        "test_scanner_api::test_run_scan_clone_error",
    ],
    # ---- Analytics
    "Dashboard summary, trend and common findings for current user only": [
        "test_analytics::test_summary_math_and_latest_scan_selection",
        "test_analytics::test_score_trend_points_window_and_scoping",
        "test_analytics::test_common_findings_counts_latest_scans_only",
    ],
    # ---- Admin
    "Non-admins get 403 on all /admin endpoints": [
        "test_admin::test_admin_endpoints_forbidden_for_non_admin",
    ],
    "Admin can list users, deactivate users, and view platform stats": [
        "test_admin::test_list_users_paginated_newest_first",
        "test_admin::test_update_user_flags",
        "test_admin::test_stats_counts",
    ],
    # ---- Quality
    "All API endpoints documented in OpenAPI": [
        "test_acceptance_criteria::test_openapi_documents_every_contract_endpoint",
    ],
    # ---- Security (SPECIAL REQUIREMENTS)
    "Rate limiting on auth and scan creation": [
        "test_auth::test_login_rate_limited",
        "test_scanner_api::test_start_scan_rate_limited_429",
    ],
    "git invoked with an argument list, URL/branch re-validated": [
        "test_scanner::test_clone_success",
        "test_scanner::test_clone_revalidates_inputs",
        "test_scanner_safety::test_build_clone_command_hardening",
    ],
    "Clone limits: shallow, timeout, max size, GIT_TERMINAL_PROMPT=0": [
        "test_scanner::test_clone_success",
        "test_scanner::test_clone_timeout",
        "test_scanner::test_clone_budget_exhausted_between_steps",
        "test_scanner_safety::test_run_git_timeout_kills_process_group",
        "test_scanner_safety::test_real_clone_oversized_tree_never_checked_out",
    ],
    "Symlinks are not followed outside the clone directory": [
        "test_scanner::test_symlinked_readme_outside_repo_is_ignored",
        "test_scanner::test_symlinked_dir_escape_not_walked",
        "test_scanner_safety::test_safe_is_file_rejects_symlink_escaping_root",
        "test_scanner_safety::test_directory_size_does_not_follow_symlinks",
    ],
}

FRONTEND_CRITERIA = (
    "Protected routes redirect to login",  # src/__tests__/auth/routes.test.tsx
    "Report page shows score, findings grouped by category",  # projects/*.test.tsx
    "Non-admins cannot open /admin pages",  # src/__tests__/auth/routes.test.tsx
    "Frontend TypeScript strict mode passes",  # npm run type-check
)

CONTRACT_ENDPOINTS = {
    ("post", "/api/v1/auth/register"),
    ("post", "/api/v1/auth/login"),
    ("post", "/api/v1/auth/refresh"),
    ("post", "/api/v1/auth/logout"),
    ("get", "/api/v1/auth/me"),
    ("put", "/api/v1/auth/me"),
    ("get", "/api/v1/auth/google"),
    ("get", "/api/v1/auth/google/callback"),
    ("get", "/api/v1/projects"),
    ("post", "/api/v1/projects"),
    ("get", "/api/v1/projects/{project_id}"),
    ("put", "/api/v1/projects/{project_id}"),
    ("delete", "/api/v1/projects/{project_id}"),
    ("post", "/api/v1/projects/{project_id}/scans"),
    ("get", "/api/v1/projects/{project_id}/scans"),
    ("get", "/api/v1/scans/{scan_id}"),
    ("get", "/api/v1/analytics/summary"),
    ("get", "/api/v1/analytics/score-trend"),
    ("get", "/api/v1/analytics/common-findings"),
    ("get", "/api/v1/admin/users"),
    ("put", "/api/v1/admin/users/{user_id}"),
    ("get", "/api/v1/admin/stats"),
    ("get", "/api/v1/admin/scans"),
    ("get", "/health"),
}


@pytest.mark.parametrize("criterion", sorted(CRITERIA))
def test_every_criterion_is_traced(criterion: str) -> None:
    refs = CRITERIA[criterion]
    assert refs, f"no tests mapped to: {criterion}"
    for ref in refs:
        module_name, func_name = ref.split("::")
        module = importlib.import_module(f"tests.{module_name}")
        func = getattr(module, func_name, None)
        assert callable(func), f"{criterion!r} references missing test {ref}"


def test_openapi_documents_every_contract_endpoint(client: TestClient) -> None:
    spec = client.get("/openapi.json").json()
    documented = {
        (method, path) for path, ops in spec["paths"].items() for method in ops if method != "head"
    }
    missing = CONTRACT_ENDPOINTS - documented
    assert not missing, f"undocumented endpoints: {sorted(missing)}"
    for path, ops in spec["paths"].items():
        for method, op in ops.items():
            assert op.get("summary") or op.get("description"), f"{method} {path} lacks docs"


def test_openapi_routes_match_app() -> None:
    # Derived from the generated OpenAPI schema: recent FastAPI versions wrap included
    # routers, so app.routes no longer lists the individual endpoints.
    app.openapi_schema = None
    paths: dict[str, dict[str, object]] = app.openapi()["paths"]
    routes = {(method, path) for path, ops in paths.items() for method in ops}
    assert routes == CONTRACT_ENDPOINTS


def _result(sev: Severity) -> CheckResult:
    return CheckResult(
        check_id=f"x_{sev.value}",
        category=FindingCategory.documentation,
        severity=sev,
        title="t",
        recommendation="r",
    )


@pytest.mark.parametrize(
    ("severities", "expected"),
    [
        ([], 100),
        ([Severity.critical], 75),
        ([Severity.high], 85),
        ([Severity.medium], 92),
        ([Severity.low], 97),
        ([Severity.critical] * 4, 0),
        ([Severity.critical] * 5, 0),  # floored at 0
    ],
)
def test_documented_score_weights(severities: list[Severity], expected: int) -> None:
    assert compute_score([_result(s) for s in severities]) == expected


def test_protected_endpoints_require_auth(client: TestClient) -> None:
    """Every non-public contract endpoint rejects anonymous requests with 401."""
    public = {
        "/api/v1/auth/register",
        "/api/v1/auth/login",
        "/api/v1/auth/refresh",
        "/api/v1/auth/logout",
        "/api/v1/auth/google",
        "/api/v1/auth/google/callback",
        "/health",
    }
    for method, path in sorted(CONTRACT_ENDPOINTS):
        if path in public:
            continue
        url = path.replace("{project_id}", "1").replace("{scan_id}", "1").replace("{user_id}", "1")
        resp = client.request(method.upper(), url, json={})
        assert resp.status_code == 401, f"{method} {path} -> {resp.status_code}"
