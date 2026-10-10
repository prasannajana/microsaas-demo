"""Domain exceptions and the handler that renders them as {"detail": msg}."""

from fastapi import Request
from fastapi.responses import JSONResponse


class AppError(Exception):
    status_code: int = 500
    default_message: str = "Internal server error"

    def __init__(self, message: str | None = None) -> None:
        self.message = message or self.default_message
        super().__init__(self.message)


class BadRequestError(AppError):
    status_code = 400
    default_message = "Bad request"


class UnauthorizedError(AppError):
    status_code = 401
    default_message = "Not authenticated"


class ForbiddenError(AppError):
    status_code = 403
    default_message = "Forbidden"


class NotFoundError(AppError):
    status_code = 404
    default_message = "Not found"


class ConflictError(AppError):
    status_code = 409
    default_message = "Conflict"


class RateLimitError(AppError):
    status_code = 429
    default_message = "Rate limit exceeded"


async def app_error_handler(_request: Request, exc: Exception) -> JSONResponse:
    assert isinstance(exc, AppError)  # noqa: S101 - registered only for AppError
    headers = {"WWW-Authenticate": "Bearer"} if exc.status_code == 401 else None
    return JSONResponse(
        status_code=exc.status_code, content={"detail": exc.message}, headers=headers
    )
