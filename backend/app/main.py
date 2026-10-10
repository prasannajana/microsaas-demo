"""FastAPI application entrypoint.

Runs as a single worker process (see scan_service: the scan executor and the startup
cleanup of interrupted scans / stale clone directories are process-local).
"""

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, Response
from slowapi.errors import RateLimitExceeded

from app.config import settings
from app.exceptions import AppError, app_error_handler
from app.rate_limit import limiter
from app.routers import admin, analytics, auth, projects, scans
from app.services import scan_service

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)

RATE_LIMIT_MESSAGE = "Too many requests, please try again later"


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
    Path(settings.SCAN_WORKDIR).mkdir(parents=True, exist_ok=True)
    try:
        purged = scan_service.purge_stale_workdirs()
        if purged:
            logger.warning("Removed %d stale scan directory(ies)", purged)
    except Exception:
        logger.exception("Failed to purge stale scan directories on startup")
    try:
        failed = scan_service.fail_interrupted_scans()
        if failed:
            logger.warning("Marked %d interrupted scan(s) as failed", failed)
    except Exception:
        logger.exception("Failed to reset interrupted scans on startup")
    try:
        yield
    finally:
        scan_service.shutdown_executor()


async def rate_limit_exceeded_handler(request: Request, exc: Exception) -> Response:
    """Render slowapi's RateLimitExceeded as {"detail": ...} (contract error shape)."""
    assert isinstance(exc, RateLimitExceeded)  # noqa: S101 - registered only for it
    response: Response = JSONResponse(status_code=429, content={"detail": RATE_LIMIT_MESSAGE})
    view_limit = getattr(request.state, "view_rate_limit", None)
    if view_limit is not None:
        response = request.app.state.limiter._inject_headers(response, view_limit)
    return response


app = FastAPI(title=settings.APP_NAME, version="1.0.0", lifespan=lifespan)

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, rate_limit_exceeded_handler)
app.add_exception_handler(AppError, app_error_handler)

# Auth uses Bearer tokens in headers, not cookies, so credentials are not needed cross-origin.
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.ALLOWED_ORIGINS,
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

for module in (auth, projects, scans, analytics, admin):
    app.include_router(module.router, prefix="/api/v1")


@app.get("/health", tags=["health"])
async def health() -> dict[str, str]:
    return {"status": "healthy"}
