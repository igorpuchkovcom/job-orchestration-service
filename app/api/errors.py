from typing import Any

from fastapi import HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette import status

from app.api.schemas.errors import ApiError

HTTP_STATUS_CODE_TO_ERROR_CODE: dict[int, str] = {
    status.HTTP_400_BAD_REQUEST: "bad_request",
    status.HTTP_401_UNAUTHORIZED: "unauthorized",
    status.HTTP_403_FORBIDDEN: "forbidden",
    status.HTTP_404_NOT_FOUND: "not_found",
    status.HTTP_409_CONFLICT: "conflict",
    status.HTTP_422_UNPROCESSABLE_CONTENT: "validation_error",
    status.HTTP_500_INTERNAL_SERVER_ERROR: "internal_error",
}


def make_api_error(
    *,
    code: str,
    message: str,
    details: Any | None = None,
) -> dict[str, Any]:
    return ApiError(code=code, message=message, details=details).model_dump()


def _normalize_http_exception(exc: HTTPException) -> ApiError:
    if isinstance(exc.detail, dict):
        code = exc.detail.get("code")
        message = exc.detail.get("message")
        if isinstance(code, str) and isinstance(message, str):
            return ApiError(
                code=code,
                message=message,
                details=exc.detail.get("details"),
            )

    if isinstance(exc.detail, str):
        return ApiError(
            code=HTTP_STATUS_CODE_TO_ERROR_CODE.get(exc.status_code, "http_error"),
            message=exc.detail,
        )

    return ApiError(
        code=HTTP_STATUS_CODE_TO_ERROR_CODE.get(exc.status_code, "http_error"),
        message="Request failed.",
        details=exc.detail,
    )


async def http_exception_handler(_: Request, exc: HTTPException) -> JSONResponse:
    payload = _normalize_http_exception(exc)
    return JSONResponse(status_code=exc.status_code, content=payload.model_dump())


async def validation_exception_handler(_: Request, exc: RequestValidationError) -> JSONResponse:
    payload = ApiError(
        code="validation_error",
        message="Request validation failed.",
        details=exc.errors(),
    )
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
        content=payload.model_dump(),
    )


async def unhandled_exception_handler(_: Request, exc: Exception) -> JSONResponse:
    payload = ApiError(code="internal_error", message="Internal server error.")
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content=payload.model_dump(),
    )
